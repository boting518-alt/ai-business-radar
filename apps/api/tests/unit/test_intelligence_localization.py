from datetime import UTC, datetime
from inspect import getsource
from types import SimpleNamespace
from uuid import uuid4

import pytest

from ai_business_radar_api.services.intelligence_localization import (
    IntelligenceLocalizationService,
    source_text_hash,
)
from ai_business_radar_api.services.intelligence_translation import IntelligenceTranslationService


class Result:
    def __init__(self, rows):
        self.rows = rows

    def __iter__(self):
        return iter(self.rows)


class Session:
    def __init__(self, rows=()):
        self.rows = rows
        self.executed = 0

    async def scalars(self, _statement):
        self.executed += 1
        return Result(self.rows)


def row(*, text="牙科工作流", digest=None, status="current"):
    return SimpleNamespace(
        id=uuid4(),
        field_name="statement",
        translated_text=text,
        source_text_hash=digest or source_text_hash("Dental workflow"),
        status=status,
        updated_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_missing_projection_falls_back_without_query_for_canonical_locale():
    session = Session()
    result = await IntelligenceLocalizationService(session).localize(
        "signal", uuid4(), "en-US", {"statement": "Dental workflow"}
    )
    assert result["statement"].text == "Dental workflow"
    assert result["statement"].original_text == "Dental workflow"
    assert result["statement"].localized is False
    assert session.executed == 0


@pytest.mark.asyncio
async def test_current_projection_is_returned_and_original_is_preserved():
    result = await IntelligenceLocalizationService(Session([row()])).localize(
        "signal", uuid4(), "zh-CN", {"statement": "Dental workflow"}
    )
    assert result["statement"].text == "牙科工作流"
    assert result["statement"].original_text == "Dental workflow"
    assert result["statement"].localized is True
    assert result["statement"].stale is False


@pytest.mark.asyncio
async def test_changed_source_or_stale_status_falls_back_and_marks_stale():
    for projection in (row(digest=source_text_hash("old source")), row(status="stale")):
        result = await IntelligenceLocalizationService(Session([projection])).localize(
            "signal", uuid4(), "zh-CN", {"statement": "Dental workflow"}
        )
        assert result["statement"].text == "Dental workflow"
        assert result["statement"].localized is False
        assert result["statement"].stale is True


def test_localization_read_service_has_no_ai_provider_dependency():
    import ai_business_radar_api.services.intelligence_localization as module

    source = getsource(module).lower()
    assert "openai" not in source
    assert "structured_generate" not in source


def test_translation_plan_skips_null_and_empty_canonical_text() -> None:
    plan = IntelligenceTranslationService._plan(
        {"name": "Actual text", "problem": None, "solution": ""}, [], False
    )
    assert [item.field_name for item in plan] == ["name"]
