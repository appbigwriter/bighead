import os
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import SecretStr

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("APP_URL", "http://localhost:3000")
os.environ.setdefault("API_URL", "http://localhost:8000")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")
os.environ.setdefault(
    "DIRECT_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres"
)
os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("SUPABASE_PUBLISHABLE_KEY", "test-publishable-key")
os.environ.setdefault("SUPABASE_SECRET_KEY", "test-secret-key")
os.environ.setdefault("STORAGE_BUCKET", "artifacts")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("QUEUE_NAME", "bighead:jobs")
os.environ.setdefault("JOB_LEASE_SECONDS", "300")
os.environ.setdefault("OTEL_SERVICE_NAME", "bighead-api-test")
os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
os.environ.setdefault("ENCRYPTION_KEY", "12345678901234567890123456789012")
os.environ.setdefault("WEBHOOK_SIGNING_SECRET", "test-webhook-secret")
os.environ.setdefault("PORTAL_TOKEN_PEPPER", "test-portal-pepper")

from bighead_api.identity.models import (  # noqa: E402
    AuthUser,
    InvitationCreatedResponse,
    MemberRole,
    Membership,
    OnboardingSubmitResponse,
    Organization,
    PreferencesResponse,
    Profile,
    Session,
)
from bighead_api.identity.repository import _preferences_response  # noqa: E402
from bighead_api.main import create_app  # noqa: E402

USER_ID = UUID("10000000-0000-0000-0000-000000000001")
ORG_ID = UUID("20000000-0000-0000-0000-000000000001")


class FakeSettings:
    app_env = "test"
    app_url = "http://localhost:3000"
    api_url = "http://localhost:8000"
    api_port = 8000
    cors_origins = ["http://localhost:3000"]
    log_level = "INFO"
    database_url = SecretStr("postgresql://unused")
    supabase_url = "http://localhost:54321"
    supabase_publishable_key = SecretStr("publishable")
    supabase_secret_key = SecretStr("secret")


class FakeAuth:
    def __init__(self) -> None:
        self.user = AuthUser(id=USER_ID, email="owner@example.com")
        self.recovery_emails: list[str] = []
        self.revocations: list[tuple[str, str]] = []
        self.password_updates: list[tuple[str, str]] = []

    async def verify(self, token: str) -> AuthUser:
        if token != "valid-token":
            raise HTTPException(status_code=401, detail="Invalid or expired session")
        return self.user

    async def login(self, email: str, password: str) -> tuple[AuthUser, Session]:
        if password != "correct-password":
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return self.user, Session(id="session-1", access_token="valid-token")

    async def send_magic_link(self, email: str) -> AuthUser:
        return AuthUser(id=None, email=email)

    async def request_recovery(self, email: str) -> None:
        self.recovery_emails.append(email)

    async def create_invited_user(self, email: str, password: str) -> AuthUser:
        return AuthUser(id=USER_ID, email=email)

    async def revoke(self, token: str, scope: str) -> None:
        self.revocations.append((token, scope))

    async def signup(self, email: str, password: str) -> tuple[AuthUser, Session | None]:
        return AuthUser(id=USER_ID, email=email), None

    async def exchange_code(self, code: str, verifier: str) -> tuple[AuthUser, Session]:
        return self.user, Session(id="callback-session", access_token="valid-token")

    async def update_password(self, token: str, new_password: str) -> None:
        self.password_updates.append((token, new_password))


class FakeRepository:
    def __init__(self, *, status: str = "active", role: MemberRole = MemberRole.OWNER) -> None:
        self.member = Membership(
            id=f"{ORG_ID}:{USER_ID}",
            organization_id=ORG_ID,
            user_id=USER_ID,
            role=role,
            status=status,
        )
        self.onboarding_user: UUID | None = None
        self.accepted: tuple[str, UUID, str, str] | None = None

    async def memberships(self, user_id: UUID, include_suspended: bool = False) -> list[Membership]:
        return [self.member] if self.member.status == "active" or include_suspended else []

    async def membership(self, user_id: UUID, organization_id: UUID) -> Membership | None:
        return self.member if user_id == USER_ID and organization_id == ORG_ID else None

    async def onboarding(self, user_id: UUID, payload: Any) -> OnboardingSubmitResponse:
        self.onboarding_user = user_id
        return OnboardingSubmitResponse(
            organization_id=ORG_ID, owner_membership_id=f"{ORG_ID}:{USER_ID}"
        )

    async def organizations(
        self, user_id: UUID, include_suspended: bool = False
    ) -> list[Organization]:
        return [
            Organization(id=ORG_ID, name="BigHead", slug="bighead", timezone="UTC", locale="pt-BR")
        ]

    async def preferences(self, user_id: UUID) -> PreferencesResponse:
        return _preferences()

    async def patch_preferences(self, user_id: UUID, payload: Any) -> PreferencesResponse:
        response = _preferences()
        if payload.theme:
            response.preferences["theme"] = payload.theme
        return response

    async def create_invite(
        self, organization_id: UUID, invited_by: UUID, email: str, role: MemberRole, hours: int
    ) -> InvitationCreatedResponse:
        return InvitationCreatedResponse(
            id=uuid4(), email=email, role=role, expires_at=datetime.now(UTC), token="one-time-token"
        )

    async def invite_email(self, token: str) -> str:
        return "invitee@example.com"

    async def accept_invite(
        self, token: str, user_id: UUID, email: str, full_name: str
    ) -> Membership:
        if email != "invitee@example.com":
            raise HTTPException(status_code=409, detail="Invite email does not match session")
        self.accepted = (token, user_id, email, full_name)
        return self.member.model_copy(update={"role": MemberRole.MEMBER})

    async def patch_membership(
        self, organization_id: UUID, actor_user_id: UUID, payload: Any
    ) -> Membership:
        return self.member.model_copy(update={"role": payload.role or self.member.role})

    async def organization_memberships(
        self, user_id: UUID, organization_id: UUID
    ) -> list[Membership]:
        return [self.member]

    async def organization_invites(
        self, user_id: UUID, organization_id: UUID
    ) -> list[dict[str, object]]:
        return []


def _preferences() -> PreferencesResponse:
    return PreferencesResponse(
        profile=Profile(
            id=USER_ID,
            display_name="Owner",
            avatar_path=None,
            locale="pt-BR",
            timezone="UTC",
            updated_at=datetime.now(UTC),
        ),
        preferences={"theme": "system"},
        sessions=[Session(id="session-1")],
    )


def test_preferences_response_decodes_asyncpg_json_string() -> None:
    now = datetime.now(UTC)
    response = _preferences_response(
        {
            "id": USER_ID,
            "display_name": "Owner",
            "avatar_path": None,
            "locale": "pt-BR",
            "timezone": "America/Sao_Paulo",
            "updated_at": now,
            "preferences": '{"theme":"radar-dark","density":"compact"}',
        },
        [Session(id="session-1")],
    )

    assert response.preferences == {"theme": "radar-dark", "density": "compact"}


def client(repository: FakeRepository | None = None, auth: FakeAuth | None = None) -> TestClient:
    return TestClient(
        create_app(
            settings=FakeSettings(),  # type: ignore[arg-type]
            auth_provider=auth or FakeAuth(),
            identity_repository=repository or FakeRepository(),
        )
    )


def test_login_returns_server_memberships_and_never_accepts_role_claims() -> None:
    response = client().post(
        "/v1/auth/login",
        json={
            "email": "owner@example.com",
            "passwordOrMagicLink": "correct-password",
            "role": "owner",
        },
    )
    assert response.status_code == 200
    assert response.json()["memberships"][0]["organizationId"] == str(ORG_ID)
    assert response.json()["session"]["accessToken"] == "valid-token"


def test_recovery_response_is_non_enumerating() -> None:
    auth = FakeAuth()
    response = client(auth=auth).post("/v1/auth/recovery", json={"email": "unknown@example.com"})
    assert response.status_code == 202
    assert response.json()["status"] == "requested"
    assert auth.recovery_emails == ["unknown@example.com"]


def test_pkce_callback_exchanges_code_and_resolves_server_memberships() -> None:
    response = client().post(
        "/v1/auth/callback",
        json={"code": "authorization-code", "codeVerifier": "v" * 43},
    )
    assert response.status_code == 200
    assert response.json()["session"]["id"] == "callback-session"
    assert response.json()["memberships"][0]["role"] == "owner"


def test_recovery_completion_requires_verified_session() -> None:
    auth = FakeAuth()
    response = client(auth=auth).post(
        "/v1/auth/recovery/complete",
        headers={"Authorization": "Bearer valid-token"},
        json={"newPassword": "new-strong-password"},
    )
    assert response.status_code == 204
    assert auth.password_updates == [("valid-token", "new-strong-password")]


def test_onboarding_uses_verified_subject_not_payload_identity() -> None:
    repository = FakeRepository()
    response = client(repository).post(
        "/v1/onboarding",
        headers={"Authorization": "Bearer valid-token"},
        json={
            "profile": {"displayName": "Owner"},
            "organization": {"name": "BigHead", "slug": "bighead"},
            "goals": ["quality"],
            "approvalPolicy": {"highRisk": "manual"},
            "userId": str(uuid4()),
        },
    )
    assert response.status_code == 201
    assert repository.onboarding_user == USER_ID


def test_suspended_membership_is_rejected_even_with_valid_token() -> None:
    response = client(FakeRepository(status="suspended")).get(
        "/v1/preferences",
        headers={"Authorization": "Bearer valid-token", "x-organization-id": str(ORG_ID)},
    )
    assert response.status_code == 403


def test_tenant_header_cannot_select_an_unrelated_organization() -> None:
    response = client().get(
        "/v1/preferences",
        headers={"Authorization": "Bearer valid-token", "x-organization-id": str(uuid4())},
    )
    assert response.status_code == 403


def test_preferences_patch_requires_active_tenant_context() -> None:
    response = client().patch(
        "/v1/preferences",
        headers={"Authorization": "Bearer valid-token", "x-organization-id": str(ORG_ID)},
        json={"theme": "dark"},
    )
    assert response.status_code == 200
    assert response.json()["preferences"]["theme"] == "dark"


def test_only_owner_or_admin_can_create_invitation() -> None:
    headers = {"Authorization": "Bearer valid-token", "x-organization-id": str(ORG_ID)}
    denied = client(FakeRepository(role=MemberRole.MEMBER)).post(
        "/v1/invitations", headers=headers, json={"email": "invitee@example.com"}
    )
    allowed = client().post(
        "/v1/invitations", headers=headers, json={"email": "invitee@example.com"}
    )
    assert denied.status_code == 403
    assert allowed.status_code == 201
    assert allowed.json()["token"] == "one-time-token"


def test_admin_membership_list_returns_the_tenant_roster() -> None:
    response = client().get(
        "/v1/memberships",
        headers={"Authorization": "Bearer valid-token", "x-organization-id": str(ORG_ID)},
    )
    assert response.status_code == 200
    assert response.json()["members"][0]["organizationId"] == str(ORG_ID)


def test_invitation_rejects_authenticated_email_mismatch() -> None:
    response = client().post(
        "/v1/invitations/token/accept",
        headers={"Authorization": "Bearer valid-token"},
        json={"fullName": "Invitee", "accept": True},
    )
    assert response.status_code == 409


def test_session_revocation_is_scoped_to_verified_bearer() -> None:
    auth = FakeAuth()
    response = client(auth=auth).post(
        "/v1/sessions/revoke",
        headers={"Authorization": "Bearer valid-token"},
        json={"scope": "global"},
    )
    assert response.status_code == 204
    assert auth.revocations == [("valid-token", "global")]
