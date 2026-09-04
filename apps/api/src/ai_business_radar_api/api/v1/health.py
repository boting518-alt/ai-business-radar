"""Application-level health endpoints."""

from typing import Literal

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: Literal["api"] = "api"
    version: str


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"] = "ready"
    dependencies: dict[str, Literal["ready", "not_ready", "not_configured"]]


@router.get("", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    settings = request.app.state.settings
    return HealthResponse(version=settings.app_version)


@router.get("/ready", response_model=ReadinessResponse)
async def readiness(request: Request, response: Response) -> ReadinessResponse:
    factory = getattr(request.app.state, "database_session_factory", None)
    if factory is None:
        return ReadinessResponse(dependencies={"database": "not_configured"})
    try:
        async with factory() as session:
            await session.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(status="not_ready", dependencies={"database": "not_ready"})
    return ReadinessResponse(dependencies={"database": "ready"})
