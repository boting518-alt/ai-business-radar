"""Public schema API for YouTube AI Business Radar v0.1."""

from .ai_outputs import (
    AI_OUTPUT_MODELS,
    BusinessSignalExtractorOutput,
    CommentPainMinerOutput,
    HypeDetectorOutput,
    IntelligenceTranslationOutput,
    OpportunityNormalizerOutput,
    RelevanceFilterOutput,
    TranslationField,
)
from .common import (
    AIConfidence,
    AINonNegativeNumber,
    AIPriceRange,
    AIScore100,
    NonNegativeDecimal,
    NonNegativeInt,
    NormalizedConfidence,
    Score100,
)
from .opportunities import OpportunityCreate, OpportunityRead, OpportunitySummary
from .reviews import ReviewDecisionRequest, ReviewTaskRead
from .scoring import (
    OpportunityScoreComponents,
    OpportunityScoreResult,
    OpportunityScoringInput,
)
from .signals import SignalCreate, SignalExtractionCandidate, SignalRead
from .sources import (
    CommentSourceRef,
    OpportunitySourceRef,
    SignalSourceRef,
    VideoSourceRef,
)

__all__ = [
    "AI_OUTPUT_MODELS",
    "AIConfidence",
    "AINonNegativeNumber",
    "AIPriceRange",
    "AIScore100",
    "BusinessSignalExtractorOutput",
    "CommentPainMinerOutput",
    "CommentSourceRef",
    "HypeDetectorOutput",
    "IntelligenceTranslationOutput",
    "NonNegativeDecimal",
    "NonNegativeInt",
    "NormalizedConfidence",
    "OpportunityCreate",
    "OpportunityNormalizerOutput",
    "OpportunityRead",
    "OpportunityScoreComponents",
    "OpportunityScoreResult",
    "OpportunityScoringInput",
    "OpportunitySourceRef",
    "OpportunitySummary",
    "RelevanceFilterOutput",
    "ReviewDecisionRequest",
    "ReviewTaskRead",
    "Score100",
    "SignalCreate",
    "SignalExtractionCandidate",
    "SignalRead",
    "SignalSourceRef",
    "TranslationField",
    "VideoSourceRef",
]
