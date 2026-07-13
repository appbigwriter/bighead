from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=lambda value: _camel(value), populate_by_name=True)


def _camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class MemberRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MANAGER = "manager"
    MEMBER = "member"
    REVIEWER = "reviewer"
    ANALYST = "analyst"


class LoginMethod(StrEnum):
    MAGIC_LINK = "magic_link"


class Membership(ApiModel):
    id: str
    organization_id: UUID
    user_id: UUID
    role: MemberRole
    status: str


class MembershipListResponse(ApiModel):
    members: list[Membership]
    invites: list[dict[str, Any]]
    guards: list[str] = Field(default_factory=lambda: ["last_owner"])


class AuthUser(ApiModel):
    id: UUID | None
    email: EmailStr
    session_id: UUID | None = None
    expires_at: datetime | None = None


class LoginRequest(ApiModel):
    email: EmailStr
    password_or_magic_link: str | None = None
    provider: str | None = None


class SignupRequest(ApiModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class AuthCallbackRequest(ApiModel):
    code: str = Field(min_length=8, max_length=2048)
    code_verifier: str = Field(min_length=43, max_length=128)


class RecoveryCompleteRequest(ApiModel):
    new_password: str = Field(min_length=8, max_length=128)


class Session(ApiModel):
    id: str
    access_token: str | None = None
    refresh_token: str | None = None
    expires_at: datetime | None = None


class AuthSessionResponse(ApiModel):
    session: Session | None
    user: AuthUser
    memberships: list[Membership]
    status: str = "authenticated"


class RecoveryRequest(ApiModel):
    email: EmailStr


class RecoveryRequestedResponse(ApiModel):
    status: str = "requested"
    expires_at: datetime | None = None


class ProfileInput(ApiModel):
    display_name: str = Field(min_length=1, max_length=120)
    locale: str = Field(default="pt-BR", min_length=2, max_length=16)
    timezone: str = Field(default="America/Sao_Paulo", min_length=1, max_length=64)


class OrganizationInput(ApiModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,62}$")
    timezone: str = Field(default="America/Sao_Paulo", min_length=1, max_length=64)
    locale: str = Field(default="pt-BR", min_length=2, max_length=16)


class OnboardingSubmitRequest(ApiModel):
    profile: ProfileInput
    organization: OrganizationInput
    goals: list[str] = Field(default_factory=list, max_length=20)
    approval_policy: dict[str, Any] = Field(default_factory=dict)


class OnboardingSubmitResponse(ApiModel):
    organization_id: UUID
    owner_membership_id: str
    next_route: str = "/operacao/home"


class Organization(ApiModel):
    id: UUID
    name: str
    slug: str
    timezone: str
    locale: str


class OrganizationListResponse(ApiModel):
    organizations: list[Organization]
    current_organization_id: UUID | None


class SwitchOrganizationResponse(ApiModel):
    organization_id: UUID
    role: MemberRole
    status: str = "active"


class PreferencesPatchRequest(ApiModel):
    theme: str | None = None
    locale: str | None = None
    timezone: str | None = None
    accessibility: dict[str, Any] | None = None
    expected_updated_at: datetime | None = None

    @field_validator("theme")
    @classmethod
    def valid_theme(cls, value: str | None) -> str | None:
        if value is not None and value not in {"light", "dark", "system"}:
            raise ValueError("theme must be light, dark, or system")
        return value


class Profile(ApiModel):
    id: UUID
    display_name: str
    avatar_path: str | None
    locale: str
    timezone: str
    updated_at: datetime


class PreferencesResponse(ApiModel):
    profile: Profile
    preferences: dict[str, Any]
    sessions: list[Session]


class InvitationAcceptRequest(ApiModel):
    full_name: str = Field(min_length=1, max_length=120)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    accept: bool


class InvitationAcceptResponse(ApiModel):
    membership: Membership
    next_route: str = "/operacao/home"


class InvitationCreateRequest(ApiModel):
    email: EmailStr
    role: MemberRole = MemberRole.MEMBER
    expires_in_hours: int = Field(default=72, ge=1, le=720)


class InvitationCreatedResponse(ApiModel):
    id: UUID
    email: EmailStr
    role: MemberRole
    expires_at: datetime
    token: str | None = None


class MembershipPatchRequest(ApiModel):
    user_id: UUID
    role: MemberRole | None = None
    status: str | None = None

    @field_validator("status")
    @classmethod
    def valid_status(cls, value: str | None) -> str | None:
        if value is not None and value not in {"active", "suspended", "removed"}:
            raise ValueError("invalid membership status")
        return value


class SessionRevokeRequest(ApiModel):
    scope: str = "local"

    @field_validator("scope")
    @classmethod
    def valid_scope(cls, value: str) -> str:
        if value not in {"local", "global"}:
            raise ValueError("scope must be local or global")
        return value
