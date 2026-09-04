from decimal import Decimal

from ai_business_radar_schemas import OpportunityScoreComponents, OpportunityScoreResult

from .components import (
    calculate_build_feasibility,
    calculate_competition_white_space,
    calculate_demand_evidence,
    calculate_distribution_ease,
    calculate_freshness,
    calculate_pain_severity,
    calculate_revenue_evidence,
    calculate_trend_velocity,
)
from .constants import CLAIM_WEIGHTS, COMPONENT_WEIGHTS, SCORING_VERSION
from .normalization import clamp, count_score, round_score, weighted_average


def score_opportunity(inputs: dict) -> OpportunityScoreResult:
    components_raw = {
        "trend_velocity_score": calculate_trend_velocity(inputs["trend"]["momentum_score"]),
        "demand_evidence_score": calculate_demand_evidence(inputs),
        "revenue_evidence_score": calculate_revenue_evidence(inputs),
        "pain_severity_score": calculate_pain_severity(inputs),
        "competition_white_space_score": calculate_competition_white_space(inputs),
        "build_feasibility_score": calculate_build_feasibility(inputs),
        "distribution_ease_score": calculate_distribution_ease(inputs),
    }
    final = sum(
        (components_raw[name] * weight for name, weight in COMPONENT_WEIGHTS.items()), Decimal(0)
    )
    claim_quality = (
        sum((CLAIM_WEIGHTS[item["claim_status"]] for item in inputs["signals"]), Decimal(0))
        / len(inputs["signals"])
        * 100
        if inputs["signals"]
        else Decimal(0)
    )
    source_diversity = (
        count_score(inputs["video_count"], 4) + count_score(inputs["channel_count"], 3)
    ) / 2
    if inputs["source_types"] == ["comment", "video"]:
        source_diversity = min(Decimal(100), source_diversity + Decimal(10))
    links = inputs["relationship_counts"]
    agreement = (
        Decimal(100) * links["supporting"] / (links["supporting"] + links["contradicting"])
        if links["contradicting"]
        else Decimal(50)
    )
    confidence = weighted_average(
        [
            (count_score(len(inputs["signals"]), 8), Decimal("0.25")),
            (source_diversity, Decimal("0.25")),
            (
                calculate_freshness(inputs["latest_signal_at"], inputs["calculated_at"]),
                Decimal("0.20"),
            ),
            (claim_quality, Decimal("0.15")),
            (agreement, Decimal("0.15")),
        ]
    )
    attention = weighted_average(
        [
            (components_raw["trend_velocity_score"], Decimal("0.40")),
            (count_score(inputs["trend"]["video_count"], 5), Decimal("0.30")),
            (count_score(inputs["trend"]["total_views"], 100000), Decimal("0.30")),
        ]
    )
    commercial = weighted_average(
        [
            (components_raw["demand_evidence_score"], Decimal("0.40")),
            (components_raw["revenue_evidence_score"], Decimal("0.30")),
            (components_raw["pain_severity_score"], Decimal("0.30")),
        ]
    )
    hype = clamp(Decimal(50) + Decimal("0.60") * (attention - commercial))
    components = OpportunityScoreComponents(
        **{name: round_score(value) for name, value in components_raw.items()}
    )
    return OpportunityScoreResult(
        scoring_version=SCORING_VERSION,
        components=components,
        opportunity_score=round_score(final),
        confidence_score=round_score(confidence),
        hype_risk_score=round_score(hype),
        inputs_snapshot=inputs,
    )
