"""Small, domain-oriented repositories sharing a caller-owned session."""

from .channels import ChannelRepository
from .comments import CommentRepository
from .discovery import (
    CollectionRunRepository,
    SearchQueryRepository,
    YouTubeDiscoveryItemRepository,
)
from .opportunities import OpportunityRepository
from .profiles import UserProfileRepository
from .reviews import ReviewTaskRepository
from .signals import SignalRepository
from .videos import VideoRepository
from .watchlists import WatchlistRepository

__all__ = [
    "ChannelRepository",
    "CommentRepository",
    "CollectionRunRepository",
    "OpportunityRepository",
    "UserProfileRepository",
    "ReviewTaskRepository",
    "SignalRepository",
    "SearchQueryRepository",
    "VideoRepository",
    "WatchlistRepository",
    "YouTubeDiscoveryItemRepository",
]
