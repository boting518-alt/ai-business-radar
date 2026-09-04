"""Human-review boundary contracts without workflow implementation."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import model_validator

from .common import NonNegativeDecimal, SchemaModel
from .enums import ReviewDecision, ReviewStatus, ReviewTargetType, ReviewType


class ReviewTaskRead(SchemaModel):
    id: UUID
    review_type: ReviewType
    target_type: ReviewTargetType
    target_id: UUID
    status: ReviewStatus
    priority: NonNegativeDecimal
    assigned_to: UUID | None = None
    decision: ReviewDecision | None = None
    decision_notes: str | None = None
    context: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None


class ReviewDecisionRequest(SchemaModel):
    decision: ReviewDecision
    merge_target_opportunity_id: UUID | None = None
    decision_notes: str | None = None

    @model_validator(mode="after")
    def validate_merge_target(self) -> "ReviewDecisionRequest":
        if self.decision == ReviewDecision.MERGE:
            if self.merge_target_opportunity_id is None:
                raise ValueError("merge_target_opportunity_id is required for merge")
        elif self.merge_target_opportunity_id is not None:
            raise ValueError("merge_target_opportunity_id is only valid for merge")
        return self
