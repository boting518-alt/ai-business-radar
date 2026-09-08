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
    DiscoveryTopic,
    SearchQuery,
    UserProfile,
    Video,
    VideoSnapshot,
    YouTubeDiscoveryItem,
)
from .taxonomy import (
    CustomerTaxonomyNode,
    IndustryTaxonomyNode,
    OpportunityTaxonomyMapping,
    SignalTaxonomyMapping,
    TaxonomyAlias,
    TaxonomyLocalization,
)

__all__ = [
    "AIExtraction",
    "Base",
    "Channel",
    "CollectionRun",
    "Comment",
    "DiscoveryTopic",
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
    "CustomerTaxonomyNode",
    "IndustryTaxonomyNode",
    "OpportunityTaxonomyMapping",
    "SignalTaxonomyMapping",
    "TaxonomyAlias",
    "TaxonomyLocalization",
]
