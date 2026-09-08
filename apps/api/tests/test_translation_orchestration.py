from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from ai_business_radar_api.services.translation_orchestration import (
    TranslationCoverage,
    TranslationCoverageReconciliationService,
    TranslationReconciliationRequest,
    current_translation_version,
)


class Enqueuer:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls = []

    def enqueue(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("redis unavailable")
        return "translation-job"


def coverage(status="missing", *, eligible=True, entity_type="signal"):
    fields = ["statement", "evidence_text"]
    return TranslationCoverage(
        entity_type=entity_type,
        entity_id=uuid4(),
        required_fields=fields,
        translated_fields=fields if status == "complete" else [],
        missing_fields=fields if status == "missing" else [],
        stale_fields=fields if status == "stale" else [],
        failed_fields=fields if status == "failed" else [],
        status=status,
        eligible=eligible,
        translation_version=current_translation_version(),
    )


@pytest.mark.asyncio
async def test_missing_eligible_entity_enqueues_dedicated_translation_job():
    queue = Enqueuer()
    service = TranslationCoverageReconciliationService(None, queue)  # type: ignore[arg-type]
    item = coverage()
    service.coverage = AsyncMock(return_value=item)

    assert await service.enqueue_if_required("signal", item.entity_id, reason="signal_review")
    assert queue.calls == [
        {
            "queue": "intelligence_translation",
            "actor": "translate_signal",
            "payload": {
                "entity_type": "signal",
                "entity_id": str(item.entity_id),
                "locale": "zh-CN",
            },
        }
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("item", [coverage("complete"), coverage(eligible=False)])
async def test_current_or_ineligible_entity_does_not_enqueue(item):
    queue = Enqueuer()
    service = TranslationCoverageReconciliationService(None, queue)  # type: ignore[arg-type]
    service.coverage = AsyncMock(return_value=item)

    assert not await service.enqueue_if_required("signal", item.entity_id, reason="reconciliation")
    assert queue.calls == []


@pytest.mark.asyncio
async def test_best_effort_enqueue_absorbs_queue_failure():
    queue = Enqueuer(fail=True)
    service = TranslationCoverageReconciliationService(None, queue)  # type: ignore[arg-type]
    item = coverage()
    service.coverage = AsyncMock(return_value=item)

    assert not await service.best_effort_enqueue("signal", item.entity_id, reason="signal_review")


@pytest.mark.asyncio
async def test_reconciliation_is_bounded_and_dry_run_enqueues_nothing():
    queue = Enqueuer()
    service = TranslationCoverageReconciliationService(None, queue)  # type: ignore[arg-type]
    missing = coverage()
    current = coverage("complete")
    service._eligible_targets = AsyncMock(  # type: ignore[method-assign]
        return_value=[("signal", missing.entity_id), ("signal", current.entity_id)]
    )
    service.coverage = AsyncMock(side_effect=[missing, current])

    result = await service.reconcile(
        TranslationReconciliationRequest(locale="zh-CN", limit=2, dry_run=True)
    )

    assert result.eligible == 2
    assert result.would_enqueue == 1
    assert result.enqueued == 0
    assert queue.calls == []
    service._eligible_targets.assert_awaited_once_with(2)


def test_reconciliation_limit_and_runtime_version_are_registry_governed():
    assert current_translation_version() == "translation-zh-CN-v001"
    with pytest.raises(ValidationError):
        TranslationReconciliationRequest(limit=501)
