from contextlib import asynccontextmanager

from ai_business_radar_api.infrastructure.ai import AIConfigurationError, OpenAIClient
from ai_business_radar_api.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from ai_business_radar_api.infrastructure.external.youtube import YouTubeClient

from .config import WorkerSettings


@asynccontextmanager
async def collection_dependencies(settings: WorkerSettings):
    engine = create_database_engine(settings.database_url.get_secret_value())
    youtube = YouTubeClient(
        settings.youtube_api_key.get_secret_value(),
        base_url=settings.youtube_api_base_url,
        timeout_seconds=settings.youtube_http_timeout_seconds,
        max_retries=settings.youtube_max_retries,
    )
    try:
        async with youtube:
            yield create_session_factory(engine), youtube
    finally:
        await engine.dispose()


@asynccontextmanager
async def relevance_dependencies(settings: WorkerSettings):
    if settings.ai_provider != "openai" or not settings.ai_model_relevance:
        raise AIConfigurationError("AI relevance provider and model are not configured")
    if settings.openai_api_key is None:
        raise AIConfigurationError("OPENAI_API_KEY is not configured")
    engine = create_database_engine(settings.database_url.get_secret_value())
    try:
        yield (
            create_session_factory(engine),
            OpenAIClient(
                settings.openai_api_key.get_secret_value(), max_retries=settings.ai_max_retries
            ),
        )
    finally:
        await engine.dispose()


@asynccontextmanager
async def signal_extraction_dependencies(settings: WorkerSettings):
    if settings.ai_provider != "openai" or not settings.ai_model_signal_extraction:
        raise AIConfigurationError("AI signal extraction provider and model are not configured")
    if settings.openai_api_key is None:
        raise AIConfigurationError("OPENAI_API_KEY is not configured")
    engine = create_database_engine(settings.database_url.get_secret_value())
    try:
        yield (
            create_session_factory(engine),
            OpenAIClient(
                settings.openai_api_key.get_secret_value(), max_retries=settings.ai_max_retries
            ),
        )
    finally:
        await engine.dispose()


@asynccontextmanager
async def comment_pain_dependencies(settings: WorkerSettings):
    if settings.ai_provider != "openai" or not settings.ai_model_comment_pain_mining:
        raise AIConfigurationError("AI comment pain provider and model are not configured")
    if settings.openai_api_key is None:
        raise AIConfigurationError("OPENAI_API_KEY is not configured")
    engine = create_database_engine(settings.database_url.get_secret_value())
    try:
        yield (
            create_session_factory(engine),
            OpenAIClient(
                settings.openai_api_key.get_secret_value(), max_retries=settings.ai_max_retries
            ),
        )
    finally:
        await engine.dispose()
