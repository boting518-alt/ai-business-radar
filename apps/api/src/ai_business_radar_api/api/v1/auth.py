"""Authenticated session introspection endpoint."""

from fastapi import APIRouter

from ...infrastructure.auth import CurrentUser, RequiredUser

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=CurrentUser)
async def get_me(current_user: RequiredUser) -> CurrentUser:
    return current_user
