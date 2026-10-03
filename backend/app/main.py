import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException

from app.core.config import CORS_ORIGINS
from app.core.errors import NotFound
from app.modules.bills.routes import router as bills
from app.modules.calendar.routes import router as calendar
from app.modules.dashboard.routes import router as dashboard
from app.modules.groceries.routes import router as groceries
from app.modules.settings.routes import router as settings
from app.modules.tasks.routes import router as tasks

app = FastAPI(title="Daybook", version="0.1.0", description="Local single-user life dashboard")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)
for router in [tasks, calendar, groceries, bills, settings, dashboard]:
    app.include_router(router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.exception_handler(NotFound)
async def not_found(request: Request, exc: NotFound):
    return JSONResponse(
        status_code=404, content={"error": {"code": "not_found", "message": str(exc)}}
    )


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
