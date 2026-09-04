import json
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from ai_business_radar_api.services.trend_aggregation import (
    OpportunityTrendAggregationService,
    TrendAggregationRequest,
)


@pytest.mark.parametrize(("window", "days"), [("7d", 7), ("30d", 30), ("90d", 90)])
def test_frozen_window_boundaries_are_end_exclusive_utc(window: str, days: int) -> None:
    local_end = datetime(2026, 9, 4, 10, 30, tzinfo=timezone(timedelta(hours=8)))
    start, end = OpportunityTrendAggregationService.period_boundaries(window, local_end)
    assert end == datetime(2026, 9, 4, 2, 30, tzinfo=UTC)
    assert start == end - timedelta(days=days)


def test_omitted_period_end_rounds_down_to_utc_hour() -> None:
    start, end = OpportunityTrendAggregationService.period_boundaries("7d", None)
    assert end.tzinfo is UTC and end.minute == end.second == end.microsecond == 0
    assert end - start == timedelta(days=7)


def test_naive_period_end_is_rejected() -> None:
    with pytest.raises(ValueError):
        TrendAggregationRequest(period_end=datetime(2026, 1, 1))


def test_growth_is_bounded_neutral_monotonic_and_deterministic() -> None:
    normalize = OpportunityTrendAggregationService.normalize_growth
    assert normalize(0, 0) == Decimal("50.00")
    assert normalize(4, 0) == normalize(4, 0)
    assert Decimal(0) <= normalize(1000, 0) <= Decimal(100)
    assert normalize(1, 4) < normalize(4, 4) < normalize(9, 4)


def test_deterministic_fixture_growth_orders_declining_flat_accelerating() -> None:
    fixture = json.loads((Path(__file__).parents[1] / "fixtures/trend_scenarios.json").read_text())
    scenarios = {item["id"]: item for item in fixture["scenarios"]}
    normalize = OpportunityTrendAggregationService.normalize_growth
    scores = {
        name: normalize(item["current_signals"], item["previous_signals"])
        for name, item in scenarios.items()
        if name in {"accelerating", "flat", "declining"}
    }
    assert scores["declining"] < scores["flat"] < scores["accelerating"]
