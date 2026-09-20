from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api.batches import router as batches_router
from app.api.mappings import router as mappings_router
from app.api.workflow import router as workflow_router
from app.api.records import router as records_router
from app.api.mock_target import router as mock_target_router
from app.api.events import router as events_router
from app.api.audit import router as audit_router
from app.api.system import router as system_router
from app.api.pipeline import router as pipeline_router
from app.observability import correlation_middleware
from app.db.database import init_db


def create_app() -> FastAPI:
    settings = get_settings()
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        from app.agent.jobs import JobRunner
        runner = JobRunner()
        runner.start()
        yield
        runner.stop()

    application = FastAPI(title="MigrateFlow API", version="0.1.0", lifespan=lifespan)
    if settings.auto_create_schema:
        init_db()
    application.middleware("http")(correlation_middleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[item.strip() for item in settings.cors_origins.split(",") if item.strip()],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": f"HTTP_{exc.status_code}", "message": str(exc.detail), "retryable": exc.status_code >= 500, "details": None}},
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "VALIDATION_ERROR", "message": "Request validation failed", "retryable": False, "details": exc.errors()}},
        )

    @application.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "migrateflow"}

    @application.get("/api/health", tags=["system"])
    def api_health() -> dict[str, str]:
        return {"status": "ok"}

    application.include_router(batches_router)
    application.include_router(mappings_router)
    application.include_router(workflow_router)
    application.include_router(records_router)
    application.include_router(mock_target_router)
    application.include_router(events_router)
    application.include_router(audit_router)
    application.include_router(system_router)
    application.include_router(pipeline_router)

    return application


app = create_app()
