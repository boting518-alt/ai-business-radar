"""Strict, provider-neutral AI structured-output contracts."""

from uuid import UUID

from pydantic import model_validator

from .common import (
    NonNegativeDecimal,
    NormalizedConfidence,
    PriceRange,
    SchemaModel,
    Score100,
)
from .enums import (
    ClaimStatus,
    HypeClassification,
    OpportunityNormalizationAction,
    SignalType,
)


class RelevanceFilterOutput(SchemaModel):
    relevant: bool
    relevance_score: NormalizedConfidence
    content_type: str | None
    primary_topic: str | None
    reason: str


class ExtractedBusinessSignal(SchemaModel):
    type: SignalType
    statement: str
    evidence: str
    claim_status: ClaimStatus
    confidence: NormalizedConfidence


class BusinessSignalExtractorOutput(SchemaModel):
    industry: str | None
    customer: str | None
    problem: str | None
    solution: str | None
    business_model: str | None
    technology: list[str]
    distribution: list[str]
    pricing: PriceRange | None
    signals: list[ExtractedBusinessSignal]


class CommentPainSignal(SchemaModel):
    category: str
    pain: str
    current_solution: str | None
    requested_solution: str | None
    spend: NonNegativeDecimal | None
    purchase_intent: bool
    evidence_strength: NormalizedConfidence
    comment_id: UUID


class CommentPainMinerOutput(SchemaModel):
    signals: list[CommentPainSignal]


class OpportunityNormalizerOutput(SchemaModel):
    action: OpportunityNormalizationAction
    opportunity_id: UUID | None
    canonical_name: str
    confidence: NormalizedConfidence
    reason: str

    @model_validator(mode="after")
    def validate_action_target(self) -> "OpportunityNormalizerOutput":
        if self.action == OpportunityNormalizationAction.MATCH:
            if self.opportunity_id is None:
                raise ValueError("opportunity_id is required when action is MATCH")
        elif self.action == OpportunityNormalizationAction.CREATE:
            if self.opportunity_id is not None:
                raise ValueError("opportunity_id must be null when action is CREATE")
        return self


class HypeDetectorOutput(SchemaModel):
    content_hype_score: Score100
    real_demand_score: Score100
    classification: HypeClassification
    reason: str


AI_OUTPUT_MODELS = {
    "relevance_filter": RelevanceFilterOutput,
    "signal_extractor": BusinessSignalExtractorOutput,
    "comment_pain_miner": CommentPainMinerOutput,
    "opportunity_normalizer": OpportunityNormalizerOutput,
    "hype_detector": HypeDetectorOutput,
}
