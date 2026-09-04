"""Minimal admin authorization verification endpoint."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from ...infrastructure.auth import RequiredAdmin

router = APIRouter(prefix="/admin", tags=["admin"])


class AdminHealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


@router.get("/health", response_model=AdminHealthResponse)
async def admin_health(_: RequiredAdmin) -> AdminHealthResponse:
    return AdminHealthResponse()
