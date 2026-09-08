"""FastAPI application factory and ASGI entry point."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.v1.router import router as v1_router
from .config import Settings, get_settings
from .infrastructure.database import create_database_engine, create_session_factory
from .logging import configure_logging
from .middleware.request_id import RequestIdMiddleware
from .runtime_config import log_runtime_target

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    configure_logging(app_settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        log_runtime_target(logger, "api", app_settings.runtime_target)
        logger.info(
            "application_start name=%s version=%s environment=%s",
            app_settings.app_name,
            app_settings.app_version,
            app_settings.app_env,
        )
        database_url = (
            app_settings.database_url.get_secret_value() if app_settings.database_url else None
        )
        if database_url:
            engine = create_database_engine(database_url)
            app.state.database_engine = engine
            app.state.database_session_factory = create_session_factory(engine)
        yield
        engine = getattr(app.state, "database_engine", None)
        if engine is not None:
            await engine.dispose()

    application = FastAPI(
        title=app_settings.app_name,
        version=app_settings.app_version,
        lifespan=lifespan,
    )
    application.state.settings = app_settings

    application.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_middleware(RequestIdMiddleware)
    application.include_router(v1_router)
    return application


app = create_app()
