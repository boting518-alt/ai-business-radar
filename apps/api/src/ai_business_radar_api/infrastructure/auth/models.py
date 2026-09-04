"""Authenticated identity and application-user contracts."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel

ApplicationRole = Literal["user", "admin"]


class AuthenticatedIdentity(BaseModel):
    auth_user_id: UUID
    email: str | None = None


class CurrentUser(BaseModel):
    auth_user_id: UUID
    user_profile_id: UUID
    role: ApplicationRole
    email: str | None = None
