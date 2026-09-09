"""Strict business-case transport contract; application code validates grounding."""

from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from .common import SchemaModel


class BusinessCaseField(SchemaModel):
    text: str | None = Field(max_length=3000)
    evidence_signal_ids: list[UUID] = Field(max_length=100)
    information_class: Literal["source_grounded", "editorial_synthesis", "hypothesis", "unknown"]
    support_level: Literal[
        "supported", "partially_supported", "insufficient_evidence", "hypothesis"
    ]
    uncertainty: str | None = Field(max_length=1500)

    @model_validator(mode="after")
    def require_grounding(self):
        if self.support_level in {"supported", "partially_supported"}:
            if not self.text or not self.text.strip() or not self.evidence_signal_ids:
                raise ValueError("Supported fields require text and evidence references")
            if self.information_class not in {"source_grounded", "editorial_synthesis"}:
                raise ValueError("Support and information class disagree")
        elif self.support_level == "insufficient_evidence":
            if (
                self.text is not None
                or self.evidence_signal_ids
                or self.information_class != "unknown"
            ):
                raise ValueError("Unknown fields must have null text and no evidence references")
        elif self.information_class != "hypothesis" or not self.uncertainty:
            raise ValueError("Hypotheses require explicit uncertainty")
        if len(set(self.evidence_signal_ids)) != len(self.evidence_signal_ids):
            raise ValueError("Duplicate evidence reference")
        return self


class OpportunityConsolidationOutput(SchemaModel):
    customer_summary: BusinessCaseField
    problem_summary: BusinessCaseField
    workflow_summary: BusinessCaseField
    solution_pattern: BusinessCaseField
    business_model_summary: BusinessCaseField
    pricing_summary: BusinessCaseField
    revenue_summary: BusinessCaseField
    distribution_summary: BusinessCaseField
    competition_summary: BusinessCaseField
    adoption_summary: BusinessCaseField
    build_complexity_summary: BusinessCaseField
    validation_gaps: list[str] = Field(min_length=1, max_length=30)
