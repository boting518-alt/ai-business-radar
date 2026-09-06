"""FastAPI authentication and role authorization dependencies."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ...dependencies import DatabaseSessionDependency
from ..database.repositories.profiles import UserProfileRepository
from .models import AuthenticatedIdentity, CurrentUser
from .supabase import AuthConfigurationError, InvalidAccessTokenError, SupabaseJWTVerifier

bearer = HTTPBearer(auto_error=False)


def get_token_verifier(request: Request) -> SupabaseJWTVerifier:
    settings = request.app.state.settings
    secret = settings.supabase_jwt_secret
    if secret is None and settings.supabase_jwks_url is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Authentication is not configured")
    try:
        return SupabaseJWTVerifier(
            secret.get_secret_value() if secret else None,
            jwks_url=settings.supabase_jwks_url,
            issuer=settings.supabase_jwt_issuer,
            audience=settings.supabase_jwt_audience,
        )
    except AuthConfigurationError as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error)) from error


def get_user_profile_repository(
    session: DatabaseSessionDependency,
) -> UserProfileRepository:
    return UserProfileRepository(session)


def get_authenticated_identity(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    request: Request,
) -> AuthenticatedIdentity:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Bearer authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    verifier = get_token_verifier(request)
    try:
        return verifier.verify(credentials.credentials)
    except InvalidAccessTokenError as error:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error


async def get_current_user(
    identity: Annotated[AuthenticatedIdentity, Depends(get_authenticated_identity)],
    profiles: Annotated[UserProfileRepository, Depends(get_user_profile_repository)],
) -> CurrentUser:
    profile = await profiles.get_by_auth_user_id(identity.auth_user_id)
    if profile is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Application profile is required")
    return CurrentUser(
        auth_user_id=identity.auth_user_id,
        user_profile_id=profile.id,
        role=profile.role,
        email=identity.email,
    )


CurrentUserDependency = Annotated[CurrentUser, Depends(get_current_user)]


def require_user(current_user: CurrentUserDependency) -> CurrentUser:
    return current_user


def require_admin(current_user: CurrentUserDependency) -> CurrentUser:
    if current_user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator role required")
    return current_user


RequiredUser = Annotated[CurrentUser, Depends(require_user)]
RequiredAdmin = Annotated[CurrentUser, Depends(require_admin)]
