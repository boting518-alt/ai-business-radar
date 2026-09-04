import asyncio
import logging
from collections.abc import Awaitable, Callable

from ai_business_radar_api.infrastructure.ai import AIConfigurationError, PromptNotFoundError
from ai_business_radar_api.services.youtube_discovery import (
    InvalidDiscoveryMode,
    SearchQueryDisabled,
    SearchQueryNotFound,
)
from pydantic import ValidationError

logger = logging.getLogger(__name__)
PermanentErrors = (
    ValidationError,
    SearchQueryNotFound,
    SearchQueryDisabled,
    InvalidDiscoveryMode,
    AIConfigurationError,
    PromptNotFoundError,
)


def run_async(factory: Callable[[], Awaitable[object]]) -> object:
    try:
        return asyncio.run(factory())
    except PermanentErrors as error:
        logger.error("permanent_collection_job_failure error_type=%s", type(error).__name__)
        return None
