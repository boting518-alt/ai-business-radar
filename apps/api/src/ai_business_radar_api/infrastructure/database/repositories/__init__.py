"""Small, domain-oriented repositories sharing a caller-owned session."""

from .ai_extractions import AIExtractionRepository
from .channels import ChannelRepository
from .comments import CommentRepository
from .discovery import (
    CollectionRunRepository,
    SearchQueryRepository,
    YouTubeDiscoveryItemRepository,
)
from .opportunities import OpportunityRepository
from .profiles import UserProfileRepository
from .radar_queries import RadarQueryRepository
from .reviews import ReviewTaskRepository
from .scores import OpportunityScoreRepository, ScoringSignalRow
from .signals import SignalRepository
from .trends import LinkedSignalRow, TrendRepository
from .videos import VideoRepository
from .watchlists import WatchlistRepository

__all__ = [
    "ChannelRepository",
    "AIExtractionRepository",
    "CommentRepository",
    "CollectionRunRepository",
    "OpportunityRepository",
    "RadarQueryRepository",
    "UserProfileRepository",
    "ReviewTaskRepository",
    "OpportunityScoreRepository",
    "ScoringSignalRow",
    "SignalRepository",
    "LinkedSignalRow",
    "TrendRepository",
    "SearchQueryRepository",
    "VideoRepository",
    "WatchlistRepository",
    "YouTubeDiscoveryItemRepository",
]
