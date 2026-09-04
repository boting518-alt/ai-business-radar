from types import SimpleNamespace
from uuid import uuid4

import pytest
from ai_business_radar_schemas import RelevanceFilterOutput
from fastapi.testclient import TestClient

from ai_business_radar_api.api.v1.ai_relevance import get_relevance_service
from ai_business_radar_api.config import Settings
from ai_business_radar_api.infrastructure.ai import (
    AIStructuredOutputError,
    OpenAIClient,
    load_prompt,
)
from ai_business_radar_api.infrastructure.auth.dependencies import get_current_user
from ai_business_radar_api.infrastructure.auth.models import CurrentUser
from ai_business_radar_api.main import create_app
from ai_business_radar_api.services.relevance_filter import (
    RelevanceBatchResult,
    RelevanceItemResult,
    canonical_input_hash,
)


def admin():
    return CurrentUser(auth_user_id=uuid4(), user_profile_id=uuid4(), role="admin", email=None)


class ServiceStub:
    async def analyze(self, video_id, *, force=False):
        return RelevanceItemResult(
            video_id=video_id,
            extraction_id=uuid4(),
            status="completed",
            relevant=True,
            relevance_score=0.9,
        )

    async def analyze_batch(self, request):
        return RelevanceBatchResult(
            requested=0,
            processed=0,
            relevant=0,
            irrelevant=0,
            failed=0,
            reused=0,
            items=[],
        )


def test_hash_is_deterministic_and_model_independent() -> None:
    first = canonical_input_hash({"b": 2, "a": 1}, prompt_version="v001", task_type="x")
    second = canonical_input_hash({"a": 1, "b": 2}, prompt_version="v001", task_type="x")
    assert first == second and len(first) == 64
    assert first != canonical_input_hash({"a": 1, "b": 2}, prompt_version="v002", task_type="x")


def test_versioned_prompt_is_available() -> None:
    prompt = load_prompt("relevance-filter", "v001")
    assert "business" in prompt.lower()
    assert "summarize" in prompt.lower()


def test_relevance_routes_require_admin_and_return_safe_result() -> None:
    app = create_app(Settings(_env_file=None))
    app.dependency_overrides[get_relevance_service] = ServiceStub
    video_id = uuid4()
    with TestClient(app) as client:
        assert client.post(f"/api/v1/admin/ai/relevance/{video_id}", json={}).status_code == 401
        app.dependency_overrides[get_current_user] = admin
        response = client.post(f"/api/v1/admin/ai/relevance/{video_id}", json={})
    assert response.status_code == 200
    assert response.json()["relevant"] is True
    assert "raw_output" not in response.json()


@pytest.mark.asyncio
async def test_openai_adapter_parses_schema_and_captures_usage() -> None:
    parsed = RelevanceFilterOutput(
        relevant=True,
        relevance_score=0.8,
        content_type="case_study",
        primary_topic="ai automation",
        reason="Evidence",
    )
    response = SimpleNamespace(
        id="resp_1",
        output_parsed=parsed,
        output_text='{"relevant":true}',
        usage=SimpleNamespace(input_tokens=10, output_tokens=5, total_tokens=15),
    )

    class Responses:
        async def parse(self, **kwargs):
            assert kwargs["store"] is False
            assert kwargs["text_format"] is RelevanceFilterOutput
            return response

    client = OpenAIClient("test", client=SimpleNamespace(responses=Responses()))
    result = await client.structured_generate(
        task_type="relevance_filter",
        model="test-model",
        system_prompt="prompt",
        input_data={"title": "test"},
        output_model=RelevanceFilterOutput,
    )
    assert result.parsed == parsed
    assert result.provider_request_id == "resp_1"
    assert result.total_tokens == 15


@pytest.mark.asyncio
async def test_openai_adapter_rejects_missing_parsed_output() -> None:
    class Responses:
        async def parse(self, **_kwargs):
            return SimpleNamespace(id="resp_bad", output_parsed=None, output_text="no", usage=None)

    client = OpenAIClient("test", client=SimpleNamespace(responses=Responses()))
    with pytest.raises(AIStructuredOutputError):
        await client.structured_generate(
            task_type="relevance_filter",
            model="test-model",
            system_prompt="prompt",
            input_data={},
            output_model=RelevanceFilterOutput,
        )
