"""Application factory and health routes."""

from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.config import Settings
from app.database import make_engine
from app.diagnostic_routes import router as diagnostic_router
from app.diagnostics import FindingNotFound, RunNotFound
from app.inventory import DuplicateService, ServiceNotFound
from app.log_ingestion import BatchNotFound
from app.log_routes import router as log_router
from app.log_search import EventNotFound
from app.logging import configure_logging
from app.models import (
    CheckResult,
    CheckTarget,
    DiagnosticRun,
    Finding,
    FindingEvent,
    IngestionError,
    LogBatch,
    LogEvent,
    Service,
)
from app.network_routes import router as network_router
from app.network_targets import ResultNotFound, TargetDisabled, TargetInvalid, TargetNotFound
from app.routes import router
from app.search_routes import router as search_router


class HealthResponse(BaseModel):
    status: str


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else Settings()
    logger = configure_logging(settings.log_level)
    engine = make_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        engine.dispose()

    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    app.state.engine = engine
    app.include_router(router)
    app.include_router(log_router)
    app.include_router(search_router)
    app.include_router(diagnostic_router)
    app.include_router(network_router)

    @app.exception_handler(TargetNotFound)
    async def missing_target(request, exc):
        return JSONResponse(status_code=404, content={"detail": "Check target not found"})

    @app.exception_handler(ResultNotFound)
    async def missing_result(request, exc):
        return JSONResponse(status_code=404, content={"detail": "Check result not found"})

    @app.exception_handler(TargetInvalid)
    async def invalid_target(request, exc):
        return JSONResponse(
            status_code=409, content={"detail": "Stored target configuration is invalid"}
        )

    @app.exception_handler(TargetDisabled)
    async def disabled_target(request, exc):
        return JSONResponse(status_code=409, content={"detail": "Check target is disabled"})

    @app.exception_handler(RunNotFound)
    async def missing_run(request, exc):
        return JSONResponse(status_code=404, content={"detail": "Diagnostic run not found"})

    @app.exception_handler(FindingNotFound)
    async def missing_finding(request, exc):
        return JSONResponse(status_code=404, content={"detail": "Finding not found"})

    @app.exception_handler(DuplicateService)
    async def duplicate_service(request, exc):
        return JSONResponse(
            status_code=409, content={"detail": "Service already exists in environment"}
        )

    @app.exception_handler(EventNotFound)
    async def missing_event(request, exc):
        return JSONResponse(status_code=404, content={"detail": "Log event not found"})

    @app.exception_handler(BatchNotFound)
    async def missing_batch(request, exc):
        return JSONResponse(status_code=404, content={"detail": "Log batch not found"})

    @app.exception_handler(ServiceNotFound)
    async def missing_service(request, exc):
        return JSONResponse(status_code=404, content={"detail": "Service not found"})

    app.state.settings = settings

    @app.middleware("http")
    async def log_request(request: Request, call_next):
        started = perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "request_failed",
                extra={"method": request.method, "path": request.url.path},
            )
            raise
        logger.info(
            "request_completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round((perf_counter() - started) * 1000, 2),
            },
        )
        return response

    @app.get("/health/live", response_model=HealthResponse)
    async def live() -> HealthResponse:
        return HealthResponse(status="alive")

    @app.get("/health/ready", response_model=HealthResponse)
    def ready():
        try:
            with engine.connect() as connection:
                for model in (
                    Service,
                    LogBatch,
                    LogEvent,
                    IngestionError,
                    DiagnosticRun,
                    Finding,
                    FindingEvent,
                    CheckTarget,
                    CheckResult,
                ):
                    connection.execute(select(model).limit(1))
        except SQLAlchemyError:
            return JSONResponse(status_code=503, content={"status": "not_ready"})
        return HealthResponse(status="ready")

    return app
