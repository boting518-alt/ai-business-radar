import copy
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from ai_business_radar_api.domain.scoring.components import (
    calculate_build_feasibility,
    calculate_competition_white_space,
    calculate_demand_evidence,
    calculate_distribution_ease,
    calculate_revenue_evidence,
)
from ai_business_radar_api.domain.scoring.constants import COMPONENT_WEIGHTS
from ai_business_radar_api.domain.scoring.engine import score_opportunity
from ai_business_radar_api.services.opportunity_scoring import OpportunityScoringService

NOW = datetime(2026, 9, 5, tzinfo=UTC)


def inputs() -> dict:
    return {
        "scoring_version": "score-v001",
        "calculated_at": NOW,
        "opportunity_id": "00000000-0000-0000-0000-000000000001",
        "trend": {
            "snapshot_id": "00000000-0000-0000-0000-000000000002",
            "aggregation_version": "trend-v001",
            "window_type": "7d",
            "period_start": NOW - timedelta(days=7),
            "period_end": NOW,
            "video_count": 3,
            "new_video_count": 2,
            "unique_channel_count": 3,
            "total_views": 10000,
            "comment_count": 4,
            "pain_signal_count": 1,
            "demand_signal_count": 1,
            "purchase_intent_signal_count": 1,
            "revenue_signal_count": 1,
            "competitor_signal_count": 1,
            "momentum_score": Decimal(70),
        },
        "counts": {"pain": 1, "demand": 1, "purchase_intent": 1, "revenue": 1},
        "claim_status_counts": {"fact": 4},
        "relationship_counts": {"supporting": 4, "contradicting": 0},
        "signals": [
            {"signal_id": str(index), "signal_type": kind, "claim_status": "fact"}
            for index, kind in enumerate(("pain", "demand", "purchase_intent", "revenue"))
        ],
        "video_count": 3,
        "channel_count": 3,
        "source_types": ["comment", "video"],
        "latest_signal_at": NOW,
        "explicit_numeric_count": 1,
        "spend_evidence_count": 1,
        "primary_technology": None,
        "technologies": [],
        "industry": None,
        "business_model": None,
        "customer_type": None,
        "distribution_channels": [],
    }


def test_weights_sum_to_one_and_outputs_are_bounded_deterministic() -> None:
    assert sum(COMPONENT_WEIGHTS.values()) == Decimal(1)
    first = score_opportunity(inputs())
    second = score_opportunity(inputs())
    assert first == second
    values = [*first.components.model_dump().values(), first.opportunity_score]
    assert all(Decimal(0) <= value <= Decimal(100) for value in values)


def test_trend_momentum_is_used_and_missing_is_neutral() -> None:
    high = inputs()
    missing = inputs()
    missing["trend"]["momentum_score"] = None
    assert score_opportunity(high).components.trend_velocity_score == Decimal("70.00")
    assert score_opportunity(missing).components.trend_velocity_score == Decimal("50.00")


def test_demand_saturates_and_purchase_intent_and_diversity_help() -> None:
    base = inputs()
    low = copy.deepcopy(base)
    low["counts"] = {"demand": 1}
    low["video_count"] = low["channel_count"] = 1
    high = copy.deepcopy(low)
    high["counts"] = {"demand": 50}
    purchase = copy.deepcopy(low)
    purchase["counts"] = {"purchase_intent": 1}
    diverse = copy.deepcopy(low)
    diverse["video_count"] = diverse["channel_count"] = 5
    assert calculate_demand_evidence(high) < calculate_demand_evidence(low) * 10
    assert calculate_demand_evidence(purchase) > calculate_demand_evidence(low)
    assert calculate_demand_evidence(diverse) > calculate_demand_evidence(low)


def test_revenue_claim_quality_and_numeric_evidence_are_respected() -> None:
    fact = inputs()
    fact["signals"] = [{"signal_type": "revenue", "claim_status": "fact"}]
    fact["explicit_numeric_count"] = 1
    creator = copy.deepcopy(fact)
    creator["signals"][0]["claim_status"] = "creator_claim"
    speculation = copy.deepcopy(fact)
    speculation["signals"][0]["claim_status"] = "speculation"
    no_number = copy.deepcopy(fact)
    no_number["explicit_numeric_count"] = 0
    assert calculate_revenue_evidence(fact) > calculate_revenue_evidence(creator)
    assert calculate_revenue_evidence(creator) > calculate_revenue_evidence(speculation)
    assert calculate_revenue_evidence(fact) > calculate_revenue_evidence(no_number)


def test_competition_curve_and_conservative_rules() -> None:
    no_competition = inputs()
    moderate = inputs()
    moderate["counts"] = {"competition": 3}
    extreme = inputs()
    extreme["counts"] = {"competition": 50}
    assert calculate_competition_white_space(no_competition) < calculate_competition_white_space(
        moderate
    )
    assert calculate_competition_white_space(extreme) < calculate_competition_white_space(moderate)
    assert calculate_build_feasibility(inputs()) == Decimal(50)
    assert calculate_distribution_ease(inputs()) == Decimal(50)
    easy = {**inputs(), "primary_technology": "API software automation", "business_model": "SaaS"}
    hard = {**inputs(), "primary_technology": "hardware robotics device", "industry": "healthcare"}
    assert calculate_build_feasibility(easy) > Decimal(50)
    assert calculate_build_feasibility(hard) < Decimal(50)


def test_confidence_freshness_hype_and_final_score_separation() -> None:
    strong = inputs()
    stale = copy.deepcopy(strong)
    stale["latest_signal_at"] = NOW - timedelta(days=200)
    viral = copy.deepcopy(strong)
    viral["trend"].update(momentum_score=Decimal(100), video_count=20, total_views=5_000_000)
    viral["counts"] = {}
    viral["signals"] = []
    viral["explicit_numeric_count"] = viral["spend_evidence_count"] = 0
    strong_result = score_opportunity(strong)
    stale_result = score_opportunity(stale)
    viral_result = score_opportunity(viral)
    assert strong_result.confidence_score > stale_result.confidence_score
    assert viral_result.hype_risk_score > strong_result.hype_risk_score
    changed = copy.deepcopy(strong)
    changed["source_types"] = ["video"]
    assert score_opportunity(changed).opportunity_score == strong_result.opportunity_score
    assert score_opportunity(changed).confidence_score != strong_result.confidence_score


def test_input_hash_is_canonical_and_changes_with_evaluation_time() -> None:
    first = OpportunityScoringService._json_value(inputs())
    reordered = dict(reversed(list(first.items())))
    assert OpportunityScoringService.input_hash(first) == OpportunityScoringService.input_hash(
        reordered
    )
    changed = copy.deepcopy(first)
    changed["calculated_at"] = "2026-09-05T01:00:00+00:00"
    assert OpportunityScoringService.input_hash(first) != OpportunityScoringService.input_hash(
        changed
    )
