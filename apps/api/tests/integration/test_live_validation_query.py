from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock

import pytest
from sqlalchemy import func, select

from ai_business_radar_api.config import Settings
from ai_business_radar_api.infrastructure.database import (
    create_database_engine,
    create_session_factory,
)
from ai_business_radar_api.infrastructure.database.models import SearchQuery
from ai_business_radar_api.tools.live_validation import LiveValidationRunner, ServiceBundle


@pytest.mark.asyncio
async def test_validation_query_uses_legal_taxonomy_and_is_reused(postgres_url: str) -> None:
    engine = create_database_engine(postgres_url)
    sessions = create_session_factory(engine)
    query = "AI dental receptionist"
    now = datetime.now(UTC)
    try:
        async with sessions() as session, session.begin():
            unrelated = SearchQuery(
                query=query,
                query_group="business",
                language="en",
                region=None,
                enabled=True,
                priority=Decimal("5"),
                discovery_mode="monitoring",
                last_run_at=None,
                created_at=now,
                updated_at=now,
            )
            session.add(unrelated)
            await session.flush()
            unrelated_id = unrelated.id

        runner = LiveValidationRunner(
            Settings(_env_file=None),
            sessions,
            ServiceBundle(discovery=Mock(), metadata=Mock(), comments=Mock()),
        )
        first_id = await runner._get_or_create_query(query)
        second_id = await runner._get_or_create_query(query)

        assert first_id == second_id
        async with sessions() as session:
            compatible = list(
                await session.scalars(
                    select(SearchQuery).where(
                        SearchQuery.query == query,
                        SearchQuery.query_group == "discovery",
                        SearchQuery.discovery_mode == "discovery",
                    )
                )
            )
            unrelated = await session.get(SearchQuery, unrelated_id)
            total = await session.scalar(
                select(func.count(SearchQuery.id)).where(SearchQuery.query == query)
            )

        assert len(compatible) == 1
        assert compatible[0].id == first_id
        assert compatible[0].enabled is True
        assert compatible[0].priority == Decimal("0")
        assert unrelated is not None
        assert unrelated.query_group == "business"
        assert unrelated.discovery_mode == "monitoring"
        assert unrelated.priority == Decimal("5")
        assert total == 2
    finally:
        await engine.dispose()
