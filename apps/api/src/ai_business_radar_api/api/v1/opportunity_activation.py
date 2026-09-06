from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ...infrastructure.auth import RequiredAdmin
from ...services.opportunity_activation import (
    ActivationReviewResult,
    OpportunityActivationNotEligible,
    OpportunityActivationNotFound,
    OpportunityActivationReadiness,
    OpportunityActivationReadinessService,
)

router = APIRouter(prefix="/admin/opportunities", tags=["admin", "opportunity activation"])


def get_activation_service(request: Request) -> OpportunityActivationReadinessService:
    sessions = getattr(request.app.state, "database_session_factory", None)
    if sessions is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database is not configured")
    return OpportunityActivationReadinessService(sessions)


def _raise_error(error: Exception) -> None:
    if isinstance(error, OpportunityActivationNotFound):
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
    if isinstance(error, OpportunityActivationNotEligible):
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    raise error


@router.get("/{opportunity_id}/activation-readiness", response_model=OpportunityActivationReadiness)
async def activation_readiness(
    opportunity_id: UUID,
    _: RequiredAdmin,
    service: Annotated[OpportunityActivationReadinessService, Depends(get_activation_service)],
) -> OpportunityActivationReadiness:
    try:
        return await service.assess(opportunity_id)
    except Exception as error:
        _raise_error(error)
        raise


@router.post("/{opportunity_id}/activation-review", response_model=ActivationReviewResult)
async def create_activation_review(
    opportunity_id: UUID,
    _: RequiredAdmin,
    service: Annotated[OpportunityActivationReadinessService, Depends(get_activation_service)],
) -> ActivationReviewResult:
    try:
        return await service.create_review(opportunity_id)
    except Exception as error:
        _raise_error(error)
        raise
