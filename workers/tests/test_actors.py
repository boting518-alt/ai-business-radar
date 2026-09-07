import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from ai_business_radar_api.services.youtube_discovery import SearchQueryDisabled

from ai_business_radar_workers.actors import (
    comment_pain,
    recover_stale_collection_claims,
    relevance,
    run_comment_pain_mining,
    run_opportunity_normalization,
    run_opportunity_scoring,
    run_relevance_filter,
    run_signal_extraction,
    run_trend_aggregation,
    run_youtube_comment_collection,
    run_youtube_discovery,
    run_youtube_metadata_collection,
    translate_batch,
    translate_opportunity,
    translate_signal,
    youtube_comments,
    youtube_discovery,
    youtube_metadata,
)
from ai_business_radar_workers.actors.runtime import run_async


def test_actor_queues_and_payloads_are_serializable() -> None:
    actors = {
        run_youtube_discovery: "youtube_discovery",
        run_youtube_metadata_collection: "youtube_metadata",
        run_youtube_comment_collection: "youtube_comments",
        recover_stale_collection_claims: "maintenance",
        run_relevance_filter: "ai_relevance",
        run_comment_pain_mining: "ai_extraction",
        run_signal_extraction: "ai_extraction",
        run_opportunity_normalization: "ai_extraction",
        run_trend_aggregation: "aggregation",
        run_opportunity_scoring: "aggregation",
        translate_signal: "intelligence_translation",
        translate_opportunity: "intelligence_translation",
        translate_batch: "intelligence_translation",
    }
    for actor, queue in actors.items():
        assert actor.queue_name == queue
        assert actor.options["max_retries"] == 2
    payload = {
        "search_query_id": str(uuid4()),
        "published_after": datetime.now(UTC).isoformat(),
        "max_pages": 1,
    }
    assert json.loads(json.dumps(payload)) == payload


def test_permanent_errors_do_not_escape_for_actor_retry() -> None:
    async def permanent():
        raise SearchQueryDisabled("disabled")

    assert run_async(permanent) is None


def test_retryable_infrastructure_error_escapes_and_partial_result_does_not() -> None:
    async def retryable():
        raise ConnectionError("safe")

    with pytest.raises(ConnectionError):
        run_async(retryable)

    class Partial:
        status = "partial"

    async def partial():
        return Partial()

    assert run_async(partial).status == "partial"


def test_validation_error_is_permanent() -> None:
    async def invalid():
        from ai_business_radar_api.services.youtube_discovery import DiscoveryRequest

        DiscoveryRequest(search_query_id=uuid4(), max_pages=99)

    assert run_async(invalid) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("module", "execute_name", "service_name", "method", "payload"),
    [
        (
            youtube_discovery,
            "execute_discovery",
            "YouTubeDiscoveryService",
            "discover",
            {"search_query_id": str(uuid4())},
        ),
        (
            youtube_metadata,
            "execute_metadata",
            "YouTubeMetadataCollectionService",
            "collect",
            {"limit": 1},
        ),
        (
            youtube_comments,
            "execute_comments",
            "YouTubeCommentCollectionService",
            "collect",
            {"limit_videos": 1},
        ),
    ],
)
async def test_execute_functions_invoke_application_services(
    monkeypatch, module, execute_name, service_name, method, payload
) -> None:
    called = []

    @asynccontextmanager
    async def dependencies(_settings):
        yield "sessions", "youtube"

    class Service:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def __getattribute__(self, name):
            if name == method:

                async def invoke(request):
                    called.append(request)
                    return SimpleNamespace(status="completed")

                return invoke
            return object.__getattribute__(self, name)

    settings = SimpleNamespace(
        youtube_metadata_batch_size=50,
        youtube_comment_batch_size=20,
        youtube_discovery_max_quota_units_per_run=500,
        youtube_comment_max_quota_units_per_run=500,
    )
    monkeypatch.setattr(module, "collection_dependencies", dependencies)
    monkeypatch.setattr(module, service_name, Service)
    result = await getattr(module, execute_name)(payload, settings)
    assert result.status == "completed" and len(called) == 1


@pytest.mark.asyncio
async def test_relevance_actor_delegates_to_service(monkeypatch) -> None:
    called = []

    @asynccontextmanager
    async def dependencies(_settings):
        yield "sessions", "ai"

    class Service:
        def __init__(self, *_args, **_kwargs):
            pass

        async def analyze_batch(self, request):
            called.append(request)
            return SimpleNamespace(status="completed")

    settings = SimpleNamespace(ai_provider="openai", ai_model_relevance="test")
    monkeypatch.setattr(relevance, "relevance_dependencies", dependencies)
    monkeypatch.setattr(relevance, "VideoRelevanceService", Service)
    result = await relevance.execute_relevance({"limit": 3}, settings)
    assert result.status == "completed"
    assert called[0].limit == 3


@pytest.mark.asyncio
async def test_signal_actor_delegates_to_service(monkeypatch) -> None:
    from ai_business_radar_workers.actors import signals

    called = []

    @asynccontextmanager
    async def dependencies(_settings):
        yield "sessions", "ai"

    class Service:
        def __init__(self, *_args, **_kwargs):
            pass

        async def extract_batch(self, request):
            called.append(request)
            return SimpleNamespace(status="completed")

    settings = SimpleNamespace(ai_provider="openai", ai_model_signal_extraction="model")
    monkeypatch.setattr(signals, "signal_extraction_dependencies", dependencies)
    monkeypatch.setattr(signals, "BusinessSignalExtractionService", Service)
    result = await signals.execute_signal_extraction({"limit": 4}, settings)
    assert result.status == "completed" and called[0].limit == 4


@pytest.mark.asyncio
async def test_comment_pain_actor_delegates_to_service(monkeypatch) -> None:
    called = []

    @asynccontextmanager
    async def dependencies(_settings):
        yield "sessions", "ai"

    class Service:
        def __init__(self, *_args, **_kwargs):
            pass

        async def mine_batch(self, request):
            called.append(request)
            return SimpleNamespace(status="completed")

    settings = SimpleNamespace(ai_provider="openai", ai_model_comment_pain_mining="model")
    monkeypatch.setattr(comment_pain, "comment_pain_dependencies", dependencies)
    monkeypatch.setattr(comment_pain, "CommentPainMiningService", Service)
    result = await comment_pain.execute_comment_pain({"limit": 5}, settings)
    assert result.status == "completed" and called[0].limit == 5


@pytest.mark.asyncio
async def test_opportunity_normalization_actor_delegates_to_service(monkeypatch) -> None:
    from ai_business_radar_workers.actors import opportunities

    called = []

    @asynccontextmanager
    async def dependencies(_settings):
        yield "sessions", "ai"

    class Service:
        def __init__(self, *_args, **_kwargs):
            pass

        async def normalize_batch(self, request):
            called.append(request)
            return SimpleNamespace(status="completed")

    settings = SimpleNamespace(
        ai_provider="openai",
        ai_model_opportunity_normalization="model",
        ai_opportunity_match_threshold=0.70,
        ai_opportunity_create_threshold=0.75,
    )
    monkeypatch.setattr(opportunities, "opportunity_normalization_dependencies", dependencies)
    monkeypatch.setattr(opportunities, "OpportunityNormalizationService", Service)
    result = await opportunities.execute_opportunity_normalization({"limit": 5}, settings)
    assert result.status == "completed" and called[0].limit == 5


@pytest.mark.asyncio
async def test_trend_actor_delegates_without_ai(monkeypatch) -> None:
    from ai_business_radar_workers.actors import trends

    called = []

    class Engine:
        async def dispose(self):
            pass

    class Service:
        def __init__(self, _sessions):
            pass

        async def aggregate_batch(self, request):
            called.append(request)
            return SimpleNamespace(status="completed")

    monkeypatch.setattr(trends, "create_database_engine", lambda _url: Engine())
    monkeypatch.setattr(trends, "create_session_factory", lambda _engine: "sessions")
    monkeypatch.setattr(trends, "OpportunityTrendAggregationService", Service)
    settings = SimpleNamespace(
        database_url=SimpleNamespace(get_secret_value=lambda: "postgresql://safe")
    )
    result = await trends.execute_trend_aggregation({"window_type": "7d", "limit": 3}, settings)
    assert result.status == "completed" and called[0].limit == 3


@pytest.mark.asyncio
async def test_scoring_actor_delegates_without_ai(monkeypatch) -> None:
    from ai_business_radar_workers.actors import scoring

    called = []

    class Engine:
        async def dispose(self):
            pass

    class Service:
        def __init__(self, _sessions):
            pass

        async def score_batch(self, request):
            called.append(request)
            return SimpleNamespace(status="completed")

    monkeypatch.setattr(scoring, "create_database_engine", lambda _url: Engine())
    monkeypatch.setattr(scoring, "create_session_factory", lambda _engine: "sessions")
    monkeypatch.setattr(scoring, "OpportunityScoringService", Service)
    settings = SimpleNamespace(
        database_url=SimpleNamespace(get_secret_value=lambda: "postgresql://safe")
    )
    result = await scoring.execute_opportunity_scoring({"limit": 4}, settings)
    assert result.status == "completed" and called[0].limit == 4


@pytest.mark.asyncio
async def test_translation_actor_delegates_to_bounded_service(monkeypatch) -> None:
    from ai_business_radar_workers.actors import intelligence_translation

    called = []

    @asynccontextmanager
    async def dependencies(_settings):
        yield "sessions", "ai"

    class Service:
        def __init__(self, *_args, **_kwargs):
            pass

        async def translate_batch(self, request):
            called.append(request)
            return SimpleNamespace(status="completed")

    settings = SimpleNamespace(
        ai_provider="openai", intelligence_translation_model="translation-model"
    )
    monkeypatch.setattr(
        intelligence_translation, "intelligence_translation_dependencies", dependencies
    )
    monkeypatch.setattr(intelligence_translation, "IntelligenceTranslationService", Service)
    result = await intelligence_translation.execute_batch_translation(
        {"entity_type": "all", "limit": 5}, settings
    )
    assert result.status == "completed" and called[0].limit == 5
