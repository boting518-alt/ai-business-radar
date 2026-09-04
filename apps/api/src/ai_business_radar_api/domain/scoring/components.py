from datetime import datetime
from decimal import Decimal

from .constants import CLAIM_WEIGHTS, WHITE_SPACE_CURVE
from .normalization import clamp, count_score, interpolate, weighted_average


def calculate_trend_velocity(momentum_score: Decimal | None) -> Decimal:
    return Decimal(str(momentum_score)) if momentum_score is not None else Decimal(50)


def calculate_demand_evidence(data: dict) -> Decimal:
    diversity = (count_score(data["video_count"], 4) + count_score(data["channel_count"], 3)) / 2
    return weighted_average(
        [
            (count_score(data["counts"].get("purchase_intent", 0), 2), Decimal("0.30")),
            (count_score(data["counts"].get("demand", 0), 3), Decimal("0.25")),
            (count_score(data["counts"].get("adoption", 0), 3), Decimal("0.15")),
            (count_score(data["counts"].get("feature_request", 0), 3), Decimal("0.10")),
            (
                count_score(
                    data["counts"].get("workflow", 0) + data["counts"].get("complaint", 0), 4
                ),
                Decimal("0.10"),
            ),
            (diversity, Decimal("0.10")),
        ]
    )


def calculate_revenue_evidence(data: dict) -> Decimal:
    type_weights = {
        "revenue": Decimal("1.0"),
        "pricing": Decimal("0.7"),
        "customer": Decimal("0.6"),
        "adoption": Decimal("0.5"),
    }
    weighted = sum(
        (
            type_weights.get(item["signal_type"], Decimal(0)) * CLAIM_WEIGHTS[item["claim_status"]]
            for item in data["signals"]
        ),
        Decimal(0),
    )
    diversity = (count_score(data["video_count"], 4) + count_score(data["channel_count"], 3)) / 2
    return weighted_average(
        [
            (count_score(weighted, 3), Decimal("0.70")),
            (count_score(data["explicit_numeric_count"], 2), Decimal("0.15")),
            (diversity, Decimal("0.15")),
        ]
    )


def calculate_pain_severity(data: dict) -> Decimal:
    counts = data["counts"]
    purchase_with_pain = counts.get("purchase_intent", 0) if counts.get("pain", 0) else 0
    return weighted_average(
        [
            (count_score(counts.get("pain", 0), 4), Decimal("0.30")),
            (count_score(counts.get("workflow", 0), 4), Decimal("0.20")),
            (count_score(data["spend_evidence_count"], 3), Decimal("0.20")),
            (count_score(counts.get("complaint", 0), 3), Decimal("0.15")),
            (count_score(purchase_with_pain, 2), Decimal("0.15")),
        ]
    )


def calculate_competition_white_space(data: dict) -> Decimal:
    pressure_count = data["counts"].get("competition", 0) + data["counts"].get("product_launch", 0)
    return interpolate(count_score(pressure_count, 5), WHITE_SPACE_CURVE)


def calculate_build_feasibility(data: dict) -> Decimal:
    values = [
        data.get("primary_technology"),
        data.get("industry"),
        data.get("business_model"),
        *data.get("technologies", []),
    ]
    text = " ".join(str(value).lower() for value in values if value)
    if not text:
        return Decimal(50)
    score = Decimal(50)
    positive = ("api", "software", "saas", "automation", "cloud", "no-code", "llm")
    negative = ("hardware", "robotics", "device", "manufacturing", "proprietary data")
    score += min(Decimal(30), Decimal(10 * sum(token in text for token in positive)))
    score -= min(Decimal(40), Decimal(20 * sum(token in text for token in negative)))
    if any(token in text for token in ("healthcare", "finance", "legal", "government")):
        score -= Decimal(10)
    return clamp(score)


def calculate_distribution_ease(data: dict) -> Decimal:
    customer = (data.get("customer_type") or "").lower()
    business = (data.get("business_model") or "").lower()
    channels = " ".join(data.get("distribution_channels", [])).lower()
    if not customer and not business and not channels:
        return Decimal(50)
    score = Decimal(50)
    if any(token in customer for token in ("smb", "small business", "local business")):
        score += Decimal(15)
    if "enterprise" in customer:
        score -= Decimal(15)
    if "government" in customer:
        score -= Decimal(25)
    if any(token in business for token in ("self-serve", "saas", "subscription")):
        score += Decimal(10)
    if any(token in business for token in ("agency", "marketplace")):
        score += Decimal(10)
    channel_tokens = ("marketplace", "community", "outbound", "partner", "agency")
    score += min(Decimal(20), Decimal(5 * sum(token in channels for token in channel_tokens)))
    return clamp(score)


def calculate_freshness(latest_signal_at: datetime | None, calculated_at: datetime) -> Decimal:
    if isinstance(latest_signal_at, str):
        latest_signal_at = datetime.fromisoformat(latest_signal_at.replace("Z", "+00:00"))
    if isinstance(calculated_at, str):
        calculated_at = datetime.fromisoformat(calculated_at.replace("Z", "+00:00"))
    if latest_signal_at is None:
        return Decimal(0)
    age_days = max(0, (calculated_at - latest_signal_at).total_seconds() / 86400)
    if age_days <= 7:
        return Decimal(100)
    if age_days <= 30:
        return Decimal(70)
    if age_days <= 90:
        return Decimal(40)
    if age_days <= 180:
        return Decimal(20)
    return Decimal(10)
