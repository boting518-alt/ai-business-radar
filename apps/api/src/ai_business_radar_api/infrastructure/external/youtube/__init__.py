"""Official YouTube Data API v3 adapter."""

from .client import YouTubeClient
from .errors import (
    YouTubeAPIError,
    YouTubeAuthenticationError,
    YouTubeNotFoundError,
    YouTubeQuotaExceededError,
    YouTubeRateLimitError,
    YouTubeResponseValidationError,
)
from .models import (
    YouTubeChannel,
    YouTubeComment,
    YouTubeCommentPage,
    YouTubeSearchItem,
    YouTubeSearchPage,
    YouTubeVideo,
)
from .quota import YouTubeQuotaCost

__all__ = [
    "YouTubeAPIError",
    "YouTubeAuthenticationError",
    "YouTubeChannel",
    "YouTubeClient",
    "YouTubeComment",
    "YouTubeCommentPage",
    "YouTubeNotFoundError",
    "YouTubeQuotaCost",
    "YouTubeQuotaExceededError",
    "YouTubeRateLimitError",
    "YouTubeResponseValidationError",
    "YouTubeSearchItem",
    "YouTubeSearchPage",
    "YouTubeVideo",
]
