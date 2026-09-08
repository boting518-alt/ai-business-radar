"""Minimal admin authorization verification endpoint."""

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel

from ...infrastructure.ai import RUNTIME_PROMPT_DEFAULTS, resolve_prompt
from ...infrastructure.auth import RequiredAdmin

router = APIRouter(prefix="/admin", tags=["admin"])


class AdminHealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


@router.get("/health", response_model=AdminHealthResponse)
async def admin_health(_: RequiredAdmin) -> AdminHealthResponse:
    return AdminHealthResponse()


class RuntimePromptVersion(BaseModel):
    version: str
    prompt_hash: str


class RuntimeAIVersionsResponse(BaseModel):
    prompts: dict[str, RuntimePromptVersion]
    hybrid_retrieval: Literal["offline_only"] = "offline_only"
    scoring: Literal["score-v001"] = "score-v001"
    trend: Literal["trend-v001"] = "trend-v001"


@router.get("/runtime/ai-versions", response_model=RuntimeAIVersionsResponse)
async def runtime_ai_versions(request: Request, _: RequiredAdmin) -> RuntimeAIVersionsResponse:
    versions = dict(RUNTIME_PROMPT_DEFAULTS)
    versions["signal-extractor"] = request.app.state.settings.signal_extractor_prompt_version
    return RuntimeAIVersionsResponse(
        prompts={
            family.replace("-", "_").replace("/", "_"): RuntimePromptVersion(
                version=version, prompt_hash=resolve_prompt(family, version).sha256
            )
            for family, version in versions.items()
        }
    )
