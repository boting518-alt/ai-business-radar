"""Local verification of Supabase access tokens using JWKS or legacy HS256."""

from typing import Any
from uuid import UUID

import jwt
from jwt import PyJWKClient
from pydantic import ValidationError

from .models import AuthenticatedIdentity


class InvalidAccessTokenError(ValueError):
    pass


class AuthConfigurationError(RuntimeError):
    pass


class SupabaseJWTVerifier:
    def __init__(
        self,
        secret: str | None,
        *,
        jwks_url: str | None = None,
        issuer: str | None,
        audience: str | None,
    ) -> None:
        if not secret and not jwks_url:
            raise AuthConfigurationError("Supabase JWT verification is not configured")
        self._secret = secret
        self._jwks_client = PyJWKClient(jwks_url) if jwks_url else None
        self._issuer = issuer
        self._audience = audience

    def verify(self, token: str) -> AuthenticatedIdentity:
        options = {"require": ["sub", "exp"], "verify_aud": self._audience is not None}
        try:
            algorithm = str(jwt.get_unverified_header(token).get("alg", ""))
            if algorithm == "HS256" and self._secret:
                key: Any = self._secret
            elif algorithm in {"RS256", "ES256"} and self._jwks_client:
                key = self._jwks_client.get_signing_key_from_jwt(token).key
            else:
                raise InvalidAccessTokenError("Unsupported access token signing algorithm")
            payload: dict[str, Any] = jwt.decode(
                token,
                key,
                algorithms=[algorithm],
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
