"""Strict, provider-neutral AI structured-output contracts."""

from uuid import UUID

from pydantic import Field, field_validator, model_validator

from .common import (
    AIConfidence,
    AINonNegativeNumber,
    AIPriceRange,
    AIScore100,
    SchemaModel,
)
from .consolidation import OpportunityConsolidationOutput
from .enums import (
    ClaimStatus,
    HypeClassification,
    OpportunityNormalizationAction,
    SignalType,
)


class RelevanceFilterOutput(SchemaModel):
    relevant: bool
    relevance_score: AIConfidence
    content_type: str | None
    primary_topic: str | None
    reason: str


class ExtractedBusinessSignal(SchemaModel):
    type: SignalType
    statement: str
    evidence: str
    claim_status: ClaimStatus
    confidence: AIConfidence


class BusinessSignalExtractorOutput(SchemaModel):
    industry: str | None
    customer: str | None
    problem: str | None
    solution: str | None
    business_model: str | None
    technology: list[str]
    distribution: list[str]
    pricing: AIPriceRange | None
    signals: list[ExtractedBusinessSignal]


class CommentPainSignal(SchemaModel):
    category: str
    pain: str
    current_solution: str | None
    requested_solution: str | None
    spend: AINonNegativeNumber | None
    purchase_intent: bool
    evidence_strength: AIConfidence
    comment_id: UUID


class CommentPainMinerOutput(SchemaModel):
    signals: list[CommentPainSignal]


class OpportunityNormalizerOutput(SchemaModel):
    action: OpportunityNormalizationAction
    opportunity_id: UUID | None
    canonical_name: str
    confidence: AIConfidence
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
    content_hype_score: AIScore100
    real_demand_score: AIScore100
    classification: HypeClassification
    reason: str


class TranslationField(SchemaModel):
    field_name: str
    translated_text: str

    @field_validator("field_name", "translated_text")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("translation fields must not be blank")
        return value


class IntelligenceTranslationOutput(SchemaModel):
    translations: list[TranslationField] = Field(min_length=1, max_length=4)
    preserved_terms: list[str] = Field(max_length=50)
    warnings: list[str] = Field(max_length=20)

    @field_validator("translations")
    @classmethod
    def unique_fields(cls, value: list[TranslationField]) -> list[TranslationField]:
        names = [item.field_name for item in value]
        if len(names) != len(set(names)):
            raise ValueError("translation field names must be unique")
        return value


AI_OUTPUT_MODELS = {
    "opportunity_consolidation": OpportunityConsolidationOutput,
    "relevance_filter": RelevanceFilterOutput,
    "signal_extractor": BusinessSignalExtractorOutput,
    "comment_pain_miner": CommentPainMinerOutput,
    "opportunity_normalizer": OpportunityNormalizerOutput,
    "hype_detector": HypeDetectorOutput,
    "intelligence_translation": IntelligenceTranslationOutput,
}
