import secrets
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi.testclient import TestClient

from ai_business_radar_api.config import Settings
from ai_business_radar_api.infrastructure.auth.dependencies import get_user_profile_repository
from ai_business_radar_api.main import create_app


class ProfileRepositoryStub:
    def __init__(self, profile: SimpleNamespace | None) -> None:
        self.profile = profile
        self.requested_auth_user_id: UUID | None = None

    async def get_by_auth_user_id(self, auth_user_id: UUID) -> SimpleNamespace | None:
        self.requested_auth_user_id = auth_user_id
        return self.profile


@pytest.fixture
def auth_context() -> tuple[TestClient, str, UUID]:
    secret = secrets.token_urlsafe(48)
    auth_user_id = uuid4()
    app = create_app(
        Settings(
            _env_file=None,
            supabase_jwt_secret=secret,
            supabase_jwt_issuer="https://test.supabase.co/auth/v1",
            supabase_jwt_audience="authenticated",
        )
    )
    return TestClient(app), secret, auth_user_id


def make_token(secret: str, auth_user_id: UUID, **overrides: object) -> str:
    now = datetime.now(UTC)
    payload: dict[str, object] = {
        "sub": str(auth_user_id),
        "email": "analyst@example.test",
        "aud": "authenticated",
        "iss": "https://test.supabase.co/auth/v1",
        "iat": now,
        "exp": now + timedelta(minutes=5),
        "role": "admin",
    }
    payload.update(overrides)
    return jwt.encode(payload, secret, algorithm="HS256")


def test_missing_authorization_header_returns_401(
    auth_context: tuple[TestClient, str, UUID],
) -> None:
    client, _, _ = auth_context
    assert client.get("/api/v1/auth/me").status_code == 401


def test_missing_header_is_401_even_when_auth_is_not_configured() -> None:
    app = create_app(Settings(_env_file=None))
    with TestClient(app) as client:
        assert client.get("/api/v1/auth/me").status_code == 401


@pytest.mark.parametrize("token", ["not-a-jwt", "abc.def.ghi"])
def test_malformed_token_returns_401(
    auth_context: tuple[TestClient, str, UUID], token: str
) -> None:
    client, _, _ = auth_context
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_invalid_signature_returns_401_without_secret_leak(
    auth_context: tuple[TestClient, str, UUID],
) -> None:
    client, secret, auth_user_id = auth_context
    token = make_token(secrets.token_urlsafe(48), auth_user_id)
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert secret not in response.text
    assert token not in response.text


def test_expired_token_returns_401(auth_context: tuple[TestClient, str, UUID]) -> None:
    client, secret, auth_user_id = auth_context
    token = make_token(secret, auth_user_id, exp=datetime.now(UTC) - timedelta(seconds=1))
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code
        == 401
    )


def test_valid_token_without_profile_returns_403(
    auth_context: tuple[TestClient, str, UUID],
) -> None:
    client, secret, auth_user_id = auth_context
    client.app.dependency_overrides[get_user_profile_repository] = lambda: ProfileRepositoryStub(
        None
    )
    token = make_token(secret, auth_user_id)
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code
        == 403
    )


@pytest.mark.parametrize(("profile_role", "admin_status"), [("user", 403), ("admin", 200)])
def test_profile_role_controls_application_authorization(
    auth_context: tuple[TestClient, str, UUID], profile_role: str, admin_status: int
) -> None:
    client, secret, auth_user_id = auth_context
    profile_id = uuid4()
    repository = ProfileRepositoryStub(SimpleNamespace(id=profile_id, role=profile_role))
    client.app.dependency_overrides[get_user_profile_repository] = lambda: repository
    token = make_token(secret, auth_user_id, role="admin")
    headers = {"Authorization": f"Bearer {token}"}

    with client:
        me = client.get("/api/v1/auth/me", headers=headers)
        admin = client.get("/api/v1/admin/health", headers=headers)

    assert me.status_code == 200
    assert me.json() == {
        "auth_user_id": str(auth_user_id),
        "user_profile_id": str(profile_id),
        "role": profile_role,
        "email": "analyst@example.test",
    }
    assert repository.requested_auth_user_id == auth_user_id
    assert admin.status_code == admin_status
