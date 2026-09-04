from types import SimpleNamespace
from uuid import uuid4

import pytest
from ai_business_radar_schemas import OpportunityNormalizerOutput

from ai_business_radar_api.services.opportunity_normalization import (
    InvalidOpportunityNormalizationOutput,
    OpportunityNormalizationService,
)


def test_match_must_reference_supplied_eligible_candidate() -> None:
    supplied = SimpleNamespace(id=uuid4(), status="active")
    output = OpportunityNormalizerOutput(
        action="MATCH",
        opportunity_id=uuid4(),
        canonical_name="AI workflow",
        confidence="0.9",
        reason="Fits",
    )
    with pytest.raises(InvalidOpportunityNormalizationOutput):
        OpportunityNormalizationService._validate_match(output, [supplied])


def test_lexical_candidate_order_is_deterministic_and_slug_has_no_random_suffix() -> None:
    signal = SimpleNamespace(
        statement="Dental AI receptionist automation",
        industry="Dental",
        customer_type="Clinic",
        problem=None,
        solution=None,
    )
    assert OpportunityNormalizationService._lexical_terms(signal) == sorted(
        OpportunityNormalizationService._lexical_terms(signal)
    )
    assert OpportunityNormalizationService._slugify("AI Dental Receptionist!") == (
        "ai-dental-receptionist"
    )
    assert OpportunityNormalizationService._slugify("中文") == "opportunity"
