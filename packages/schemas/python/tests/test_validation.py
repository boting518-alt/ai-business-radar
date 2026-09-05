from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from ai_business_radar_schemas.ai_outputs import (
    BusinessSignalExtractorOutput,
    HypeDetectorOutput,
    OpportunityNormalizerOutput,
    RelevanceFilterOutput,
)
from ai_business_radar_schemas.enums import (
    ClaimStatus,
    HypeClassification,
    MarketStage,
    OpportunityNormalizationAction,
    ReviewDecision,
    SignalSourceType,
    SignalType,
)
from ai_business_radar_schemas.opportunities import OpportunityCreate
from ai_business_radar_schemas.reviews import ReviewDecisionRequest
from ai_business_radar_schemas.scoring import OpportunityScoreComponents
from ai_business_radar_schemas.signals import SignalCreate, SignalExtractionCandidate
from pydantic import ValidationError


def candidate_data() -> dict[str, object]:
    return {
        "signal_type": SignalType.PAIN,
        "statement": "Teams repeatedly copy data between tools.",
        "claim_status": ClaimStatus.CREATOR_CLAIM,
        "confidence": Decimal("0.8"),
    }


@pytest.mark.parametrize("value", [Decimal("0"), Decimal("1")])
def test_confidence_boundaries_are_inclusive(value: Decimal) -> None:
    candidate = SignalExtractionCandidate(**{**candidate_data(), "confidence": value})
    assert candidate.confidence == value


@pytest.mark.parametrize("value", [Decimal("-0.01"), Decimal("1.01")])
def test_confidence_outside_bounds_is_rejected(value: Decimal) -> None:
    with pytest.raises(ValidationError):
        SignalExtractionCandidate(**{**candidate_data(), "confidence": value})


@pytest.mark.parametrize("value", [Decimal("0"), Decimal("100")])
def test_score_boundaries_are_inclusive(value: Decimal) -> None:
    components = OpportunityScoreComponents(
        trend_velocity_score=value,
        demand_evidence_score=value,
        revenue_evidence_score=value,
        pain_severity_score=value,
        competition_white_space_score=value,
        build_feasibility_score=value,
        distribution_ease_score=value,
    )
    assert components.trend_velocity_score == value


@pytest.mark.parametrize("value", [Decimal("-0.01"), Decimal("100.01")])
def test_score_outside_bounds_is_rejected(value: Decimal) -> None:
    with pytest.raises(ValidationError):
        OpportunityScoreComponents(
            trend_velocity_score=value,
            demand_evidence_score=50,
            revenue_evidence_score=50,
            pain_severity_score=50,
            competition_white_space_score=50,
            build_feasibility_score=50,
            distribution_ease_score=50,
        )


def test_signal_price_range_is_validated() -> None:
    with pytest.raises(ValidationError, match="price_min"):
        SignalExtractionCandidate(
            **candidate_data(),
            price_min=Decimal("20"),
            price_max=Decimal("10"),
            price_currency="USD",
        )


def test_signal_source_reference_must_match() -> None:
    source_id = uuid4()
    signal = SignalCreate(
        **candidate_data(),
        source_type=SignalSourceType.VIDEO,
        source_id=source_id,
        video_id=source_id,
    )
    assert signal.video_id == source_id

    with pytest.raises(ValidationError, match="source_type"):
        SignalCreate(
            **candidate_data(),
            source_type=SignalSourceType.VIDEO,
            source_id=source_id,
            comment_id=source_id,
        )


def test_opportunity_normalizer_match_requires_target() -> None:
    with pytest.raises(ValidationError, match="required"):
        OpportunityNormalizerOutput(
            action=OpportunityNormalizationAction.MATCH,
            opportunity_id=None,
            canonical_name="AI Dental Receptionist",
            confidence=Decimal("0.9"),
            reason="Strong semantic match",
        )

    target = uuid4()
    output = OpportunityNormalizerOutput(
        action=OpportunityNormalizationAction.MATCH,
        opportunity_id=target,
        canonical_name="AI Dental Receptionist",
        confidence=Decimal("0.9"),
        reason="Strong semantic match",
    )
    assert output.opportunity_id == target


def test_opportunity_normalizer_create_forbids_target() -> None:
    with pytest.raises(ValidationError, match="must be null"):
        OpportunityNormalizerOutput(
            action=OpportunityNormalizationAction.CREATE,
            opportunity_id=uuid4(),
            canonical_name="AI Dental Receptionist",
            confidence=Decimal("0.7"),
            reason="No suitable candidate",
        )


def test_review_merge_requires_target_and_other_decisions_forbid_it() -> None:
    with pytest.raises(ValidationError, match="required"):
        ReviewDecisionRequest(decision=ReviewDecision.MERGE)

    target = uuid4()
    request = ReviewDecisionRequest(
        decision=ReviewDecision.MERGE,
        merge_target_opportunity_id=target,
        decision_notes="Duplicate opportunity",
    )
    assert request.merge_target_opportunity_id == target

    with pytest.raises(ValidationError, match="only valid"):
        ReviewDecisionRequest(
            decision=ReviewDecision.APPROVE,
            merge_target_opportunity_id=target,
        )


def test_invalid_enum_and_extra_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        OpportunityNormalizerOutput(
            action="DELETE",
            opportunity_id=None,
            canonical_name="Invalid",
            confidence=Decimal("0.5"),
            reason="Invalid action",
        )

    with pytest.raises(ValidationError):
        RelevanceFilterOutput(
            relevant=True,
            relevance_score=Decimal("0.8"),
            content_type=None,
            primary_topic=None,
            reason="Relevant",
            unexpected="not allowed",
        )


def test_valid_ai_output_serializes() -> None:
    output = BusinessSignalExtractorOutput(
        industry="Healthcare",
        customer="Dental practices",
        problem="Missed calls",
        solution="AI receptionist",
        business_model="SaaS",
        technology=["voice AI"],
        distribution=["direct sales"],
        pricing={"min": 99, "max": 299, "currency": "USD", "period": "month"},
        signals=[
            {
                "type": SignalType.DEMAND,
                "statement": "Practice owners ask for automated call handling.",
                "evidence": "Direct statement in source material.",
                "claim_status": ClaimStatus.CREATOR_CLAIM,
                "confidence": Decimal("0.82"),
            }
        ],
    )
    serialized = output.model_dump(mode="json")
    assert serialized["signals"][0]["type"] == "demand"
    assert serialized["pricing"]["currency"] == "USD"


def test_hype_output_uses_explicit_taxonomy() -> None:
    output = HypeDetectorOutput(
        content_hype_score=75,
        real_demand_score=40,
        classification=HypeClassification.MIXED,
        reason="Attention and demand evidence are both present.",
    )
    assert output.classification == HypeClassification.MIXED


def test_opportunity_base_model_has_no_score_columns() -> None:
    now = datetime.now(UTC)
    OpportunityCreate(
        slug="ai-dental-receptionist",
        name="AI Dental Receptionist",
        market_stage=MarketStage.EMERGING,
        first_detected_at=now,
        last_activity_at=now,
    )
    assert "opportunity_score" not in OpportunityCreate.model_fields
    assert "confidence_score" not in OpportunityCreate.model_fields
    assert "hype_risk_score" not in OpportunityCreate.model_fields
