import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException

from app.core.config import CORS_ORIGINS
from app.core.errors import Conflict, NotFound
from app.modules.auth.routes import router as auth
from app.modules.auth.service import AuthError
from app.modules.bills.routes import router as bills
from app.modules.bills.routes import series_router as bill_series
from app.modules.budget.routes import router as budget
from app.modules.calendar.routes import router as calendar
from app.modules.dashboard.routes import router as dashboard
from app.modules.groceries.routes import router as groceries
from app.modules.meals.routes import router as meals
from app.modules.settings.routes import router as settings
from app.modules.tasks.routes import router as tasks
from app.modules.tasks.routes import series_router as task_series

app = FastAPI(title="Daybook", version="0.3.0", description="Personal life dashboard")
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


@app.exception_handler(AuthError)
async def auth_error(request: Request, exc: AuthError):
    return JSONResponse(
        status_code=exc.status,
        content={"error": {"code": exc.code, "message": exc.message}},
        headers={"Cache-Control": "no-store"},
    )


@app.middleware("http")
async def private_no_store(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


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
