"""All migration-aligned persistence mappings."""

from .base import Base
from .fact import AIExtraction, Signal
from .intelligence import (
    IntelligenceLocalization,
    Opportunity,
    OpportunityEvidence,
    OpportunityMergeHistory,
    OpportunityScore,
    OpportunitySignalLink,
    ReviewTask,
    TrendSnapshot,
    Watchlist,
    WatchlistItem,
)
from .raw import (
    Channel,
    CollectionRun,
    Comment,
    SearchQuery,
    UserProfile,
    Video,
    VideoSnapshot,
    YouTubeDiscoveryItem,
)

__all__ = [
    "AIExtraction",
    "Base",
    "Channel",
    "CollectionRun",
    "Comment",
    "IntelligenceLocalization",
    "Opportunity",
    "OpportunityEvidence",
    "OpportunityMergeHistory",
    "OpportunityScore",
    "OpportunitySignalLink",
    "ReviewTask",
    "SearchQuery",
    "Signal",
    "TrendSnapshot",
    "UserProfile",
    "Video",
    "VideoSnapshot",
    "Watchlist",
    "WatchlistItem",
    "YouTubeDiscoveryItem",
]
