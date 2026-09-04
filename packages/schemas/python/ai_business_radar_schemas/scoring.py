"""Scoring input/output contracts; this module contains no formulas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import model_validator

from .common import NonNegativeInt, SchemaModel, Score100
from .enums import TrendWindowType


class OpportunityScoreComponents(SchemaModel):
    trend_velocity_score: Score100
    demand_evidence_score: Score100
    revenue_evidence_score: Score100
    pain_severity_score: Score100
    competition_white_space_score: Score100
    build_feasibility_score: Score100
    distribution_ease_score: Score100


class OpportunityScoringInput(SchemaModel):
    opportunity_id: UUID
    window_type: TrendWindowType
    period_start: datetime
    period_end: datetime
    video_count: NonNegativeInt
    new_video_count: NonNegativeInt
    unique_channel_count: NonNegativeInt
    total_views: NonNegativeInt
    comment_count: NonNegativeInt
    pain_signal_count: NonNegativeInt
    demand_signal_count: NonNegativeInt
    purchase_intent_signal_count: NonNegativeInt
    revenue_signal_count: NonNegativeInt
    competitor_signal_count: NonNegativeInt
    momentum_score: Score100 | None = None

    @model_validator(mode="after")
    def validate_period(self) -> "OpportunityScoringInput":
        if self.period_start >= self.period_end:
            raise ValueError("period_start must be before period_end")
        return self


class OpportunityScoreResult(SchemaModel):
    scoring_version: str
    components: OpportunityScoreComponents
    opportunity_score: Score100
    confidence_score: Score100 | None = None
    hype_risk_score: Score100 | None = None
    inputs_snapshot: dict[str, Any]
