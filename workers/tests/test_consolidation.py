from contextlib import asynccontextmanager
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from ai_business_radar_workers.actors import consolidation


@pytest.mark.asyncio
async def test_business_case_worker_reuses_configured_ai_and_separate_queue(monkeypatch):
    sessions, ai = object(), object()
    @asynccontextmanager
    async def dependencies(settings):
        yield sessions, ai
    execute = AsyncMock(return_value={"status": "completed"})
    monkeypatch.setattr(consolidation, "opportunity_normalization_dependencies", dependencies)
    monkeypatch.setattr(consolidation.OpportunityConsolidationService, "execute", execute)
    from types import SimpleNamespace
    settings = SimpleNamespace(ai_provider="test", ai_model_opportunity_normalization="model")
    identity = uuid4()
    await consolidation.execute_consolidation(str(identity), settings)
    execute.assert_awaited_once_with(identity, ai, provider="test", model="model")
    assert consolidation.consolidate_opportunity.queue_name == "opportunity_consolidation"
    assert consolidation.consolidate_opportunity.options["max_retries"] == 2
