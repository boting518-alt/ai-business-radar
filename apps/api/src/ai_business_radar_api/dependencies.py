"""FastAPI dependency aliases owned by the application boundary."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from .config import Settings, get_settings

SettingsDependency = Annotated[Settings, Depends(get_settings)]


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    factory = getattr(request.app.state, "database_session_factory", None)
    if factory is None:
        from .infrastructure.database import DatabaseConfigurationError

        raise DatabaseConfigurationError("DATABASE_URL is not configured")
    async with factory() as session:
        yield session


DatabaseSessionDependency = Annotated[AsyncSession, Depends(get_db_session)]
