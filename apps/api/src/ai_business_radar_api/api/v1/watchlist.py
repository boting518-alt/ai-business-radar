# ruff: noqa: B008

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ...infrastructure.auth import RequiredUser
from ...services.watchlist import (
    WatchlistMembershipResult,
    WatchlistOpportunityNotVisible,
    WatchlistResult,
    WatchlistService,
)

router = APIRouter(prefix="/watchlist", tags=["Watchlist"])


def get_watchlist_service(request: Request) -> WatchlistService:
    sessions = getattr(request.app.state, "database_session_factory", None)
    if sessions is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database is not configured")
    return WatchlistService(sessions)


@router.get("", response_model=WatchlistResult)
async def list_watchlist(
    user: RequiredUser,
    service: Annotated[WatchlistService, Depends(get_watchlist_service)],
) -> WatchlistResult:
    return await service.list_items(user.user_profile_id)


@router.post("/items/{opportunity_id}", response_model=WatchlistMembershipResult)
async def add_watchlist_item(
    opportunity_id: UUID,
    user: RequiredUser,
    service: Annotated[WatchlistService, Depends(get_watchlist_service)],
) -> WatchlistMembershipResult:
    try:
        return await service.add(user.user_profile_id, opportunity_id)
    except WatchlistOpportunityNotVisible as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Opportunity was not found") from error


@router.delete("/items/{opportunity_id}", response_model=WatchlistMembershipResult)
async def remove_watchlist_item(
    opportunity_id: UUID,
    user: RequiredUser,
    service: Annotated[WatchlistService, Depends(get_watchlist_service)],
) -> WatchlistMembershipResult:
    return await service.remove(user.user_profile_id, opportunity_id)
