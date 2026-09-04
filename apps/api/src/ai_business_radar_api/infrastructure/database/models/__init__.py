"""All migration-aligned persistence mappings."""

from .base import Base
from .fact import AIExtraction, Signal
from .intelligence import (
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
from .raw import Channel, CollectionRun, Comment, SearchQuery, UserProfile, Video, VideoSnapshot

__all__ = [
    "AIExtraction",
    "Base",
    "Channel",
    "CollectionRun",
    "Comment",
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
]
