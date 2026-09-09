from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ...infrastructure.auth import RequiredAdmin
from ...services.candidate_workspace import (
    CandidateConflict,
    CandidateDetail,
    CandidateEdit,
    CandidateFilters,
    CandidateNotFound,
    CandidatePage,
    CandidateWorkspaceService,
)
from ...services.radar_query import EvidencePage

router = APIRouter(prefix="/admin/opportunities/candidates", tags=["admin", "candidates"])


def get_candidate_service(request: Request):
    sessions = getattr(request.app.state, "database_session_factory", None)
    if sessions is None:
        raise HTTPException(503, "Database is not configured")
    return CandidateWorkspaceService(sessions)


Service = Annotated[CandidateWorkspaceService, Depends(get_candidate_service)]


@router.get("", response_model=CandidatePage)
async def candidates(
    _: RequiredAdmin,
    service: Service,
    filters: Annotated[CandidateFilters, Query()],
):
    return await service.list(filters, filters.locale)


@router.get("/{identity}", response_model=CandidateDetail)
async def detail(
    identity: UUID, _: RequiredAdmin, service: Service, locale: Literal["en-US", "zh-CN"] = "en-US"
):
    try:
        return await service.detail(identity, locale)
    except CandidateNotFound as error:
        raise HTTPException(404, str(error)) from error


@router.patch("/{identity}", response_model=CandidateDetail)
async def edit(identity: UUID, body: CandidateEdit, admin: RequiredAdmin, service: Service):
    try:
        return await service.edit(identity, admin.user_profile_id, body)
    except CandidateNotFound as error:
        raise HTTPException(404, str(error)) from error
    except CandidateConflict as error:
        raise HTTPException(409, str(error)) from error


@router.get("/{identity}/evidence", response_model=EvidencePage)
async def evidence(
    identity: UUID,
    _: RequiredAdmin,
    service: Service,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    locale: Literal["en-US", "zh-CN"] = "en-US",
    excluded: bool = False,
):
    try:
        return await service.evidence(identity, offset, limit, locale, excluded)
    except CandidateNotFound as error:
        raise HTTPException(404, str(error)) from error
