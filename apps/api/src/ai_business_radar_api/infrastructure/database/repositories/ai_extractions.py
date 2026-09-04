from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AIExtraction


class AIExtractionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def find_completed_identity(
        self,
        *,
        source_id: UUID,
        task_type: str,
        prompt_version: str,
        model: str,
        input_hash: str,
    ) -> AIExtraction | None:
        return await self.session.scalar(
            select(AIExtraction)
            .where(
                AIExtraction.source_type == "video",
                AIExtraction.source_id == source_id,
                AIExtraction.task_type == task_type,
                AIExtraction.prompt_version == prompt_version,
                AIExtraction.model == model,
                AIExtraction.input_hash == input_hash,
                AIExtraction.status == "completed",
            )
            .order_by(AIExtraction.attempt_number.desc())
        )

    async def create_pending(self, **values: Any) -> AIExtraction:
        identity = (
            AIExtraction.source_type == values["source_type"],
            AIExtraction.source_id == values["source_id"],
            AIExtraction.task_type == values["task_type"],
            AIExtraction.prompt_version == values["prompt_version"],
            AIExtraction.model == values["model"],
            AIExtraction.input_hash == values["input_hash"],
        )
        attempt = (
            await self.session.scalar(
                select(func.max(AIExtraction.attempt_number)).where(*identity)
            )
        ) or 0
        previous = await self.session.scalar(
            select(AIExtraction)
            .where(*identity)
            .order_by(AIExtraction.attempt_number.desc())
            .limit(1)
        )
        statement = (
            insert(AIExtraction)
            .values(
                **values,
                attempt_number=attempt + 1,
                supersedes_extraction_id=previous.id if previous else None,
                status="pending",
            )
            .returning(AIExtraction)
        )
        return (await self.session.execute(statement)).scalar_one()

    async def mark_running(self, extraction_id: UUID, started_at: datetime) -> None:
        await self._update(extraction_id, status="running", started_at=started_at)

    async def mark_completed(
        self,
        extraction_id: UUID,
        *,
        completed_at: datetime,
        raw_output: dict,
        parsed_output: dict,
        confidence: Decimal,
        **usage: Any,
    ) -> None:
        await self._update(
            extraction_id,
            status="completed",
            completed_at=completed_at,
            raw_output=raw_output,
            parsed_output=parsed_output,
            confidence=confidence,
            error_message=None,
            **usage,
        )

    async def mark_failed(self, extraction_id: UUID, *, completed_at: datetime, error: str) -> None:
        await self._update(
            extraction_id, status="failed", completed_at=completed_at, error_message=error
        )

    async def mark_invalid(
        self,
        extraction_id: UUID,
        *,
        completed_at: datetime,
        error: str,
        raw_output: dict | None,
    ) -> None:
        await self._update(
            extraction_id,
            status="invalid_output",
            completed_at=completed_at,
            error_message=error,
            raw_output=raw_output,
        )

    async def _update(self, extraction_id: UUID, **values: Any) -> None:
        await self.session.execute(
            update(AIExtraction).where(AIExtraction.id == extraction_id).values(**values)
        )
