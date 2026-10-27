"""Application factory and health routes."""

from time import perf_counter

from fastapi import FastAPI, Request
from pydantic import BaseModel

from app.config import Settings
from app.logging import configure_logging


class HealthResponse(BaseModel):
    status: str


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else Settings()
    logger = configure_logging(settings.log_level)
    app = FastAPI(title=settings.app_name, version="0.1.0")
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
    async def ready() -> HealthResponse:
        # No external dependencies exist in milestone 1.
        return HealthResponse(status="ready")

    return app
