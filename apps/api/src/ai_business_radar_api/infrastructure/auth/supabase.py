"""Local verification of Supabase-compatible HS256 access tokens."""

from typing import Any
from uuid import UUID

import jwt
from pydantic import ValidationError

from .models import AuthenticatedIdentity


class InvalidAccessTokenError(ValueError):
    pass


class AuthConfigurationError(RuntimeError):
    pass


class SupabaseJWTVerifier:
    def __init__(self, secret: str, *, issuer: str | None, audience: str | None) -> None:
        if not secret:
            raise AuthConfigurationError("Supabase JWT verification is not configured")
        self._secret = secret
        self._issuer = issuer
        self._audience = audience

    def verify(self, token: str) -> AuthenticatedIdentity:
        options = {"require": ["sub", "exp"], "verify_aud": self._audience is not None}
        try:
            payload: dict[str, Any] = jwt.decode(
                token,
                self._secret,
                algorithms=["HS256"],
                audience=self._audience,
                issuer=self._issuer,
                options=options,
            )
            return AuthenticatedIdentity(
                auth_user_id=UUID(str(payload["sub"])),
                email=payload.get("email"),
            )
        except (jwt.PyJWTError, KeyError, ValueError, ValidationError) as error:
            raise InvalidAccessTokenError("Invalid or expired access token") from error
