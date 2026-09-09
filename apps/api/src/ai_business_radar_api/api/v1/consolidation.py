# ruff: noqa: B008
"""Explicit async business-case actions and safe read projections."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ...infrastructure.auth import RequiredAdmin, RequiredUser
from ...infrastructure.queue import JobEnqueuer
from ...services.candidate_workspace import (
    CandidateConflict,
    CandidateNotFound,
    CandidateWorkspaceService,
)
from ...services.opportunity_consolidation import (
    DIMENSIONS,
    AcceptProposal,
    OpportunityConsolidationService,
)
from ...services.translation_orchestration import TranslationCoverageReconciliationService

router = APIRouter(tags=["Business case"])


def get_service(request: Request):
    sessions = getattr(request.app.state, "database_session_factory", None)
    if sessions is None:
        raise HTTPException(503, "Database is not configured")
    redis = request.app.state.settings.redis_url
    return OpportunityConsolidationService(
        sessions, JobEnqueuer(redis.get_secret_value()) if redis else None
    )


Service = Annotated[OpportunityConsolidationService, Depends(get_service)]


async def guarded(work):
    try:
        return await work
    except CandidateNotFound as error:
        raise HTTPException(404, str(error)) from error
    except CandidateConflict as error:
        raise HTTPException(409, str(error)) from error


@router.post("/admin/opportunities/{identity}/consolidation", status_code=202)
async def refresh(identity: UUID, admin: RequiredAdmin, service: Service):
    if service.enqueuer is None:
        raise HTTPException(503, "Consolidation queue is not configured")
    return await guarded(service.request(identity, admin.user_profile_id))


@router.get("/admin/opportunities/{identity}/consolidation/current")
@router.get("/admin/opportunities/{identity}/consolidations")
async def current(identity: UUID, _: RequiredAdmin, service: Service):
    return await guarded(service.current(identity))


@router.post("/admin/opportunities/{identity}/consolidations/{case_id}/approve")
async def approve(identity: UUID, case_id: UUID, admin: RequiredAdmin, service: Service):
    return await guarded(service.approve(identity, case_id, admin.user_profile_id))


@router.post("/admin/opportunities/{identity}/consolidations/{case_id}/accept")
async def accept(
    identity: UUID, case_id: UUID, body: AcceptProposal, admin: RequiredAdmin, service: Service
):
    result = await guarded(service.accept(identity, case_id, admin.user_profile_id, body))
    if result["changed"]:
        await TranslationCoverageReconciliationService(
            service.sessions, service.enqueuer
        ).best_effort_enqueue("opportunity", identity, reason="consolidation_accept")
    return result


@router.get("/opportunities/{identity}/business-case")
async def public_case(identity: UUID, _: RequiredUser, service: Service):
    return await guarded(service.current(identity, public=True))


async def dimension_evidence(identity, dimension, service, public, locale, offset, limit):
    if dimension not in DIMENSIONS:
        raise HTTPException(422, "Unknown business-case dimension")
    current = await guarded(service.current(identity, public=public))
    case = current["case"]
    if not case or current["state"] != "current":
        raise HTTPException(409, "Current business case is unavailable")
    ids = [UUID(i) for i in case["parsed_output"][dimension]["evidence_signal_ids"]]
    return await CandidateWorkspaceService(service.sessions).evidence(
        identity, offset, limit, locale, signal_ids=ids
    )


@router.get("/opportunities/{identity}/business-case/evidence/{dimension}")
async def public_evidence(
    identity: UUID,
    dimension: str,
    _: RequiredUser,
    service: Service,
    locale: Literal["en-US", "zh-CN"] = "en-US",
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    return await dimension_evidence(identity, dimension, service, True, locale, offset, limit)


@router.get("/admin/opportunities/{identity}/consolidation/evidence/{dimension}")
async def admin_evidence(
    identity: UUID,
    dimension: str,
    _: RequiredAdmin,
    service: Service,
    locale: Literal["en-US", "zh-CN"] = "en-US",
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    return await dimension_evidence(identity, dimension, service, False, locale, offset, limit)
