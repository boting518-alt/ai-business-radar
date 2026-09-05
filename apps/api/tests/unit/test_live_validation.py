import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from pydantic import SecretStr

from ai_business_radar_api.config import Settings
from ai_business_radar_api.tools.live_validation import (
    QUALITY_CHECKLIST,
    LiveValidationError,
    LiveValidationRunner,
    ReportWriter,
    ServiceBundle,
    ValidationLimits,
    ValidationReport,
    configuration_status,
    configured,
    database_identity,
    preflight_ready,
    safe_error,
)


class Result(SimpleNamespace):
    def model_dump(self, **_kwargs):
        return dict(self.__dict__)


def services(*, relevant: bool = True) -> ServiceBundle:
    video_id = uuid4()
    extraction_id = uuid4()
    opportunity_id = uuid4()
    return ServiceBundle(
        discovery=SimpleNamespace(
            discover=AsyncMock(
                return_value=Result(collection_run_id=uuid4(), status="completed")
            )
        ),
        metadata=SimpleNamespace(collect=AsyncMock(return_value=Result(status="completed"))),
        comments=SimpleNamespace(collect=AsyncMock(return_value=Result(status="completed"))),
        relevance=SimpleNamespace(
            analyze=AsyncMock(
                return_value=Result(
                    video_id=video_id,
                    extraction_id=extraction_id,
                    status="completed",
                    relevant=relevant,
                    relevance_score=0.9,
                    reused=False,
                )
            )
        ),
        signals=SimpleNamespace(
            extract=AsyncMock(
                return_value=Result(
                    extraction_id=extraction_id,
                    status="completed",
                    signals_created=1,
                    reused=False,
                )
            )
        ),
        comment_pain=SimpleNamespace(
            mine=AsyncMock(
                return_value=Result(
                    extraction_id=extraction_id,
                    status="completed",
                    signals_created=1,
                    reused=False,
                )
            )
        ),
        normalization=SimpleNamespace(
            normalize=AsyncMock(
                return_value=Result(
                    extraction_id=extraction_id,
                    status="completed",
                    action="CREATE",
                    opportunity_id=opportunity_id,
                )
            )
        ),
        trends=SimpleNamespace(aggregate=AsyncMock(return_value=Result(status="completed"))),
        scoring=SimpleNamespace(score=AsyncMock(return_value=Result(status="completed"))),
    )


def runner(tmp_path: Path, bundle: ServiceBundle) -> LiveValidationRunner:
    instance = LiveValidationRunner(
        Settings(_env_file=None),
        sessions=Mock(),
        services=bundle,
        writer=ReportWriter(tmp_path),
    )
    video_id = uuid4()
    signal_id = uuid4()
    comment_id = uuid4()
    opportunity_id = bundle.normalization.normalize.return_value.opportunity_id
    instance._get_or_create_query = AsyncMock(return_value=uuid4())
    instance._run_video_ids = AsyncMock(return_value=[video_id])
    instance._raw_counts = AsyncMock(
        return_value={"videos": 1, "channels": 1, "snapshots": 1, "comments": 1}
    )
    instance._raw_sample = AsyncMock(return_value={"video_titles": [], "comment_excerpts": []})
    instance._select_ai_videos = AsyncMock(return_value=[video_id])
    instance._select_comments = AsyncMock(return_value=[comment_id])
    instance._signals_for_extractions = AsyncMock(return_value=[signal_id])
    instance._track_extraction = AsyncMock()
    instance._relevance_row = AsyncMock(return_value={"video_title": "Example"})
    instance._signal_rows = AsyncMock(return_value=[{"signal_type": "pain"}])
    instance._comment_pain_row = AsyncMock(return_value={"signal": True})
    instance._opportunity_rows = AsyncMock(return_value=[{"name": "Example"}])
    instance._score_row = AsyncMock(
        return_value={
            "opportunity_id": str(opportunity_id),
            "opportunity": "Example",
            "score": 60,
            "confidence": 40,
            "hype_risk": 20,
            "momentum_7d": 50,
        }
    )
    return instance


def run_kwargs(**overrides):
    values = {
        "command": "full",
        "query": "AI dental receptionist",
        "limits": ValidationLimits(),
        "stop_after": None,
        "force_ai": False,
        "dry_run": False,
        "show_sample": False,
        "identity": {"host": "localhost", "database": "ai_business_radar_live_test"},
    }
    values.update(overrides)
    return values


def test_database_safety_accepts_only_dedicated_local_database() -> None:
    _, identity = database_identity(
        "postgresql+asyncpg://user:secret@localhost/ai_business_radar_live_test"
    )
    assert identity == {"host": "localhost", "database": "ai_business_radar_live_test"}
    with pytest.raises(LiveValidationError):
        database_identity("postgresql://user:secret@db.supabase.co/ai_business_radar_live_test")
    with pytest.raises(LiveValidationError):
        database_identity("postgresql://localhost/postgres")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_videos", 26),
        ("max_comments_per_video", 51),
        ("max_pages", 3),
        ("max_ai_videos", 11),
        ("max_ai_comments", 51),
        ("max_normalization_signals", 21),
    ],
)
def test_hard_limits_are_enforced(field: str, value: int) -> None:
    values = dict(ValidationLimits().__dict__)
    values[field] = value
    with pytest.raises(LiveValidationError):
        ValidationLimits(**values).validate()


def test_configuration_presence_and_errors_never_reveal_secret() -> None:
    secret = "do-not-print-this-secret"
    assert configured(SecretStr(secret))
    assert secret not in safe_error(RuntimeError(secret))


def test_preflight_configuration_status_detects_missing_keys_without_values() -> None:
    checks = configuration_status(Settings(_env_file=None))
    assert checks["YOUTUBE_API_KEY"] == "missing"
    assert checks["OPENAI_API_KEY"] == "missing"
    configured_checks = configuration_status(
        Settings(
            _env_file=None,
            youtube_api_key="youtube-secret",
            openai_api_key="openai-secret",
        )
    )
    serialized = json.dumps(configured_checks)
    assert configured_checks["YOUTUBE_API_KEY"] == "configured"
    assert configured_checks["OPENAI_API_KEY"] == "configured"
    assert "youtube-secret" not in serialized and "openai-secret" not in serialized


def test_preflight_requires_keys_models_database_and_redis() -> None:
    checks = {
        **configuration_status(
            Settings(
                _env_file=None,
                youtube_api_key="youtube-secret",
                openai_api_key="openai-secret",
                ai_provider="openai",
                ai_model_relevance="model",
                ai_model_signal_extraction="model",
                ai_model_comment_pain_mining="model",
                ai_model_opportunity_normalization="model",
            )
        ),
        "migrations": "ready",
        "redis": "reachable",
    }
    assert preflight_ready(checks)
    checks["OPENAI_API_KEY"] = "missing"
    assert not preflight_ready(checks)


def test_report_has_token_totals_checklist_and_no_supplied_secret(tmp_path: Path) -> None:
    secret = "do-not-print-this-secret"
    report = ValidationReport(
        run_id=str(uuid4()),
        command="full",
        query="test",
        limits=dict(ValidationLimits().__dict__),
        database={"host": "localhost", "database": "ai_business_radar_live_test"},
        started_at="2026-09-05T00:00:00+00:00",
    )
    report.token_usage = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
    directory = ReportWriter(tmp_path).write(report)
    content = "\n".join(path.read_text() for path in directory.iterdir())
    assert "total_tokens" in content
    assert all(name in content for name in QUALITY_CHECKLIST)
    assert secret not in content


@pytest.mark.asyncio
async def test_dry_run_calls_no_services_and_writes_report(tmp_path: Path) -> None:
    bundle = services()
    instance = runner(tmp_path, bundle)
    report, directory = await instance.run(**run_kwargs(dry_run=True))
    assert report.stages_completed == []
    assert directory.exists()
    for service in (
        bundle.discovery,
        bundle.metadata,
        bundle.comments,
        bundle.relevance,
        bundle.signals,
        bundle.comment_pain,
        bundle.normalization,
        bundle.trends,
        bundle.scoring,
    ):
        for value in vars(service).values():
            value.assert_not_awaited()


@pytest.mark.asyncio
async def test_youtube_flow_is_bounded_and_can_stop_after_comments(tmp_path: Path) -> None:
    bundle = services()
    instance = runner(tmp_path, bundle)
    report, _ = await instance.run(**run_kwargs(command="youtube", stop_after="comments"))
    assert report.stages_completed == ["discovery", "metadata", "comments"]
    request = bundle.discovery.discover.await_args.args[0]
    comment_request = bundle.comments.collect.await_args.args[0]
    assert request.max_results == 10 and request.max_pages == 1
    assert comment_request.max_comments_per_video == 20
    bundle.relevance.analyze.assert_not_awaited()


@pytest.mark.asyncio
async def test_full_flow_invokes_existing_services_and_passes_force(tmp_path: Path) -> None:
    bundle = services(relevant=True)
    instance = runner(tmp_path, bundle)
    report, _ = await instance.run(**run_kwargs(force_ai=True))
    assert report.stages_completed == list(
        (
            "discovery",
            "metadata",
            "comments",
            "relevance",
            "signals",
            "comment-pain",
            "normalization",
            "trend",
            "scoring",
        )
    )
    assert bundle.relevance.analyze.await_args.kwargs["force"] is True
    assert bundle.signals.extract.await_count == 1
    assert bundle.comment_pain.mine.await_count == 1
    assert bundle.normalization.normalize.await_count <= 20
    assert bundle.trends.aggregate.await_count == 3
    assert bundle.scoring.score.await_count == 1


@pytest.mark.asyncio
async def test_signal_extraction_only_runs_for_relevant_videos(tmp_path: Path) -> None:
    bundle = services(relevant=False)
    instance = runner(tmp_path, bundle)
    await instance.run(**run_kwargs(stop_after="signals"))
    bundle.signals.extract.assert_not_awaited()


@pytest.mark.asyncio
async def test_stop_after_relevance_prevents_paid_downstream_stages(tmp_path: Path) -> None:
    bundle = services()
    instance = runner(tmp_path, bundle)
    report, _ = await instance.run(**run_kwargs(stop_after="relevance"))
    assert report.stages_completed[-1] == "relevance"
    bundle.signals.extract.assert_not_awaited()
    bundle.comment_pain.mine.assert_not_awaited()


@pytest.mark.asyncio
async def test_partial_failure_still_generates_report(tmp_path: Path) -> None:
    bundle = services()
    bundle.metadata.collect.side_effect = RuntimeError("secret provider detail")
    instance = runner(tmp_path, bundle)
    report, directory = await instance.run(**run_kwargs())
    assert report.stages_completed == ["discovery"]
    assert report.failures == [{"stage": "metadata", "error": "RuntimeError"}]
    persisted = json.loads((directory / "summary.json").read_text())
    assert persisted["failures"] == report.failures
    assert "secret provider detail" not in (directory / "summary.md").read_text()


def test_runner_module_has_no_scheduler_dependency() -> None:
    source = Path(
        "src/ai_business_radar_api/tools/live_validation.py"
    ).read_text(encoding="utf-8")
    assert "apscheduler" not in source.lower()
    assert "ai_business_radar_workers" not in source
