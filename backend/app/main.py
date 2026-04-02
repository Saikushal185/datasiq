from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from backend.app.core.config import get_settings
try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
except ImportError:  # pragma: no cover - local environments may lag dependency installation.
    sentry_sdk = None
    FastApiIntegration = None

from backend.app.routers import curriculum, flashcards, progress, quiz, streak
from backend.app.services.local_dev import ensure_local_dev_environment

_sentry_initialized = False


def _configure_sentry() -> None:
    global _sentry_initialized

    if _sentry_initialized or sentry_sdk is None or FastApiIntegration is None:
        return

    settings = get_settings()
    if not settings.sentry_dsn:
        return

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        send_default_pii=True,
        integrations=[FastApiIntegration()],
    )
    _sentry_initialized = True


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        _configure_sentry()
        await ensure_local_dev_environment()
        yield

    app = FastAPI(title="datisiq-backend", lifespan=lifespan)

    @app.middleware("http")
    async def sentry_request_tags(request: Request, call_next):
        if sentry_sdk is not None:
            sentry_sdk.set_tag("service", "backend")
            sentry_sdk.set_tag("http.method", request.method)
            sentry_sdk.set_tag("http.path", request.url.path)
            if request.url.path.startswith("/api/v1"):
                sentry_sdk.set_tag("api.version", "v1")

        response = await call_next(request)

        if sentry_sdk is not None:
            sentry_sdk.set_tag("http.status_code", str(response.status_code))

        return response

    @app.get("/healthz")
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(flashcards.router, prefix="/api/v1")
    app.include_router(quiz.router, prefix="/api/v1")
    app.include_router(progress.router, prefix="/api/v1")
    app.include_router(streak.router, prefix="/api/v1")
    app.include_router(curriculum.router, prefix="/api/v1")

    return app


app = create_app()
