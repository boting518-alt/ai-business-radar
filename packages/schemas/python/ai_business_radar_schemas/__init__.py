"""Public schema API for YouTube AI Business Radar v0.1."""

from .ai_outputs import (
    AI_OUTPUT_MODELS,
    BusinessSignalExtractorOutput,
    CommentPainMinerOutput,
    HypeDetectorOutput,
    OpportunityNormalizerOutput,
    RelevanceFilterOutput,
)
from .common import NonNegativeDecimal, NonNegativeInt, NormalizedConfidence, Score100
from .opportunities import OpportunityCreate, OpportunityRead, OpportunitySummary
from .reviews import ReviewDecisionRequest, ReviewTaskRead
from .scoring import OpportunityScoreComponents, OpportunityScoreResult, OpportunityScoringInput
from .signals import SignalCreate, SignalExtractionCandidate, SignalRead
from .sources import CommentSourceRef, OpportunitySourceRef, VideoSourceRef

__all__ = [
    "AI_OUTPUT_MODELS",
    "BusinessSignalExtractorOutput",
    "CommentPainMinerOutput",
    "CommentSourceRef",
    "HypeDetectorOutput",
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
    "VideoSourceRef",
]
