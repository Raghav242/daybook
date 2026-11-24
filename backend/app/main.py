import logging
import os
import re
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException

from app.core import config
from app.core.config import CORS_ORIGINS
from app.core.errors import Conflict, Invalid, NotFound
from app.modules.auth.routes import router as auth
from app.modules.auth.service import AuthError
from app.modules.bills.routes import router as bills
from app.modules.bills.routes import series_router as bill_series
from app.modules.budget.routes import router as budget
from app.modules.calendar.routes import router as calendar
from app.modules.categories.routes import router as categories
from app.modules.dashboard.routes import router as dashboard
from app.modules.groceries.routes import router as groceries
from app.modules.meals.routes import router as meals
from app.modules.settings.routes import router as settings
from app.modules.tasks.routes import router as tasks
from app.modules.tasks.routes import series_router as task_series

app = FastAPI(title="Daybook", version="0.4.0", description="Personal life dashboard")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
    allow_credentials=True,
)
app.include_router(auth, prefix="/api")
# Root auth endpoints are available for clients following the /auth contract.
app.include_router(auth, include_in_schema=False)
for router in [
    tasks,
    task_series,
    calendar,
    groceries,
    bills,
    bill_series,
    meals,
    budget,
    categories,
    settings,
    dashboard,
]:
    app.include_router(router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.exception_handler(NotFound)
async def not_found(request: Request, exc: NotFound):
    return JSONResponse(
        status_code=404, content={"error": {"code": "not_found", "message": str(exc)}}
    )


@app.exception_handler(Conflict)
async def conflict(request: Request, exc: Conflict):
    return JSONResponse(
        status_code=409, content={"error": {"code": "conflict", "message": str(exc)}}
    )


@app.exception_handler(Invalid)
async def invalid(request: Request, exc: Invalid):
    return JSONResponse(
        status_code=422, content={"error": {"code": "validation", "message": str(exc)}}
    )


@app.exception_handler(AuthError)
async def auth_error(request: Request, exc: AuthError):
    return JSONResponse(
        status_code=exc.status,
        content={"error": {"code": exc.code, "message": exc.message}},
        headers={"Cache-Control": "no-store"},
    )


# Vite names build output "<name>-<content hash>.<ext>", so these never change.
FINGERPRINTED_ASSET = re.compile(r"^/assets/[^/]+-[A-Za-z0-9_-]{8}\.[A-Za-z0-9]+$")


@app.middleware("http")
async def cache_policy(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if response.status_code in (200, 304) and FINGERPRINTED_ASSET.match(path):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    elif response.status_code in (200, 304) and path in ("/", "/index.html"):
        # Always revalidate the entry page so a deploy picks up new asset names.
        response.headers["Cache-Control"] = "no-cache"
    else:
        # API data is private; everything else is never stored either.
        response.headers["Cache-Control"] = "no-store"
    return response


def mount_frontend(dist):
    """Serve the built single-page app from the API's origin.

    Only "/" (the entry page) and "/assets/*" are served. The app uses hash
    routes, so no catch-all is needed, and unknown /api paths stay API 404s.
    """
    root = Path(dist)
    if not (root / "index.html").is_file():
        raise RuntimeError(f"FRONTEND_DIST={dist} does not contain index.html.")
    if not CORS_ORIGINS:
        # Same-origin writes still send Origin, which the CSRF check must accept.
        raise RuntimeError("Set CORS_ORIGINS to the public origin, e.g. https://app.example.")
    files = StaticFiles(directory=root)
    index = str(root / "index.html")

    @app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
    @app.api_route("/index.html", methods=["GET", "HEAD"], include_in_schema=False)
    async def frontend_index(request: Request):
        # StaticFiles adds ETag/Last-Modified and answers conditional requests with 304.
        return files.file_response(index, os.stat(index), request.scope)

    app.mount("/assets", StaticFiles(directory=root / "assets"), name="assets")


if config.FRONTEND_DIST:
    mount_frontend(config.FRONTEND_DIST)


@app.exception_handler(RequestValidationError)
async def validation(request: Request, exc: RequestValidationError):
    details = [
        {"field": ".".join(map(str, e["loc"][1:])), "message": e["msg"]} for e in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation",
                "message": "Please check the entered values.",
                "details": details,
            }
        },
    )


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": "http_error", "message": str(exc.detail)}},
    )


@app.exception_handler(SQLAlchemyError)
async def database_error(request: Request, exc: SQLAlchemyError):
    logging.getLogger(__name__).exception("Database request failed")
    return JSONResponse(
        status_code=503,
        content={
            "error": {
                "code": "database_unavailable",
                "message": "The database is unavailable. Please try again.",
            }
        },
    )
