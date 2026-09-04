from types import SimpleNamespace

import pytest

from ai_business_radar_workers.scheduler import schedules


@pytest.mark.asyncio
async def test_scheduler_enqueues_only_loaded_bounded_discovery_queries(monkeypatch) -> None:
    queries = [SimpleNamespace(id="enabled-1"), SimpleNamespace(id="enabled-2")]

    class Repository:
        def __init__(self, _session) -> None:
            pass

        async def list_enabled_discovery(self, *, limit: int):
            assert limit == 2
            return queries

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            pass

    class Engine:
        async def dispose(self):
            pass

    sent = []
    monkeypatch.setattr(schedules, "create_database_engine", lambda _url: Engine())
    monkeypatch.setattr(schedules, "create_session_factory", lambda _engine: Session)
    monkeypatch.setattr(schedules, "SearchQueryRepository", Repository)
    from ai_business_radar_workers.actors.youtube_discovery import run_youtube_discovery

    monkeypatch.setattr(run_youtube_discovery, "send", lambda **payload: sent.append(payload))
    settings = SimpleNamespace(
        database_url=SimpleNamespace(get_secret_value=lambda: "postgresql://safe"),
        youtube_discovery_schedule_batch_size=2,
    )
    assert await schedules.enqueue_scheduled_discovery(settings) == 2
    assert sent == [{"search_query_id": "enabled-1"}, {"search_query_id": "enabled-2"}]


def test_daily_trend_schedule_enqueues_three_bounded_windows(monkeypatch) -> None:
    from ai_business_radar_workers.actors.trends import run_trend_aggregation

    sent = []
    monkeypatch.setattr(run_trend_aggregation, "send", lambda **payload: sent.append(payload))
    settings = SimpleNamespace(trend_aggregation_batch_size=75)
    assert schedules.enqueue_scheduled_trends(settings) == 3
    assert sent == [
        {"window_type": "7d", "limit": 75},
        {"window_type": "30d", "limit": 75},
        {"window_type": "90d", "limit": 75},
    ]
