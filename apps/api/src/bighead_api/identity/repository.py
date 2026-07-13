import hashlib
import json
import secrets
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, cast
from uuid import UUID

import asyncpg  # type: ignore[import-untyped]
from asyncpg import Record
from fastapi import HTTPException

from bighead_api.identity.models import (
    InvitationCreatedResponse,
    MemberRole,
    Membership,
    MembershipPatchRequest,
    OnboardingSubmitRequest,
    OnboardingSubmitResponse,
    Organization,
    PreferencesPatchRequest,
    PreferencesResponse,
    Profile,
    Session,
)

ACTIVE_MEMBERSHIPS_QUERY = """select organization_id, user_id, role::text, status::text
  from public.organization_members
 where user_id = $1 and status = 'active'
 order by created_at"""
ACTIVE_OR_SUSPENDED_MEMBERSHIPS_QUERY = """
select organization_id, user_id, role::text, status::text
  from public.organization_members
 where user_id = $1 and status in ('active', 'suspended')
 order by created_at
"""
ACTIVE_ORGANIZATIONS_QUERY = """select o.id, o.name, o.slug, o.timezone, o.locale
  from public.organizations o
  join public.organization_members m on m.organization_id = o.id
 where m.user_id = $1 and m.status = 'active'
 order by o.name"""
ACTIVE_OR_SUSPENDED_ORGANIZATIONS_QUERY = """
select o.id, o.name, o.slug, o.timezone, o.locale
  from public.organizations o
  join public.organization_members m on m.organization_id = o.id
 where m.user_id = $1 and m.status in ('active', 'suspended')
 order by o.name
"""


class IdentityRepository(Protocol):
    async def memberships(
        self, user_id: UUID, include_suspended: bool = False
    ) -> list[Membership]: ...

    async def membership(self, user_id: UUID, organization_id: UUID) -> Membership | None: ...

    async def onboarding(
        self, user_id: UUID, payload: OnboardingSubmitRequest
    ) -> OnboardingSubmitResponse: ...

    async def organizations(
        self, user_id: UUID, include_suspended: bool = False
    ) -> list[Organization]: ...

    async def preferences(self, user_id: UUID) -> PreferencesResponse: ...

    async def patch_preferences(
        self, user_id: UUID, payload: PreferencesPatchRequest
    ) -> PreferencesResponse: ...

    async def create_invite(
        self, organization_id: UUID, invited_by: UUID, email: str, role: MemberRole, hours: int
    ) -> InvitationCreatedResponse: ...

    async def invite_email(self, token: str) -> str: ...

    async def accept_invite(
        self, token: str, user_id: UUID, email: str, full_name: str
    ) -> Membership: ...

    async def patch_membership(
        self, organization_id: UUID, actor_user_id: UUID, payload: MembershipPatchRequest
    ) -> Membership: ...

    async def organization_memberships(
        self, user_id: UUID, organization_id: UUID
    ) -> list[Membership]: ...

    async def organization_invites(
        self, user_id: UUID, organization_id: UUID
    ) -> list[dict[str, Any]]: ...


class Database:
    def __init__(self, dsn: str, service_dsn: str | None = None) -> None:
        self._dsn = dsn
        self._service_dsn = service_dsn or dsn
        self._pool: asyncpg.Pool[Record] | None = None
        self._service_pool: asyncpg.Pool[Record] | None = None

    async def pool(self) -> asyncpg.Pool[Record]:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=10)
        return self._pool

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
        if self._service_pool is not None:
            await self._service_pool.close()
            self._service_pool = None

    async def service_pool(self) -> asyncpg.Pool[Record]:
        if self._service_pool is None:
            self._service_pool = await asyncpg.create_pool(
                self._service_dsn, min_size=1, max_size=5
            )
        return self._service_pool

    @asynccontextmanager
    async def authenticated(
        self, user_id: UUID, organization_id: UUID | None = None
    ) -> AsyncIterator[asyncpg.Connection[Record]]:
        """Run one operation with the same role and claims used by the Data API."""
        pool = await self.pool()
        async with pool.acquire() as connection, connection.transaction():
            await connection.execute("set local role authenticated")
            await connection.execute(
                "select set_config('request.jwt.claim.sub', $1, true)", str(user_id)
            )
            await connection.execute(
                "select set_config('request.jwt.claim.organization_id', $1, true)",
                str(organization_id) if organization_id else "",
            )
            yield connection

    @asynccontextmanager
    async def privileged(self) -> AsyncIterator[asyncpg.Connection[Record]]:
        """Run a narrowly-scoped backend operation that cannot pass RLS bootstrap."""
        pool = await self.service_pool()
        async with pool.acquire() as connection, connection.transaction():
            yield connection


@dataclass
class PostgresIdentityRepository:
    database: Database

    async def memberships(self, user_id: UUID, include_suspended: bool = False) -> list[Membership]:
        query = (
            ACTIVE_OR_SUSPENDED_MEMBERSHIPS_QUERY if include_suspended else ACTIVE_MEMBERSHIPS_QUERY
        )
        async with self.database.authenticated(user_id) as connection:
            rows = await connection.fetch(query, user_id)
        return [_membership(row) for row in rows]

    async def membership(self, user_id: UUID, organization_id: UUID) -> Membership | None:
        async with self.database.authenticated(user_id, organization_id) as connection:
            row = await connection.fetchrow(
                """select organization_id, user_id, role::text, status::text
                     from public.organization_members
                    where user_id = $1 and organization_id = $2""",
                user_id,
                organization_id,
            )
        return _membership(row) if row else None

    async def organization_memberships(
        self, user_id: UUID, organization_id: UUID
    ) -> list[Membership]:
        async with self.database.authenticated(user_id, organization_id) as connection:
            rows = await connection.fetch(
                """select organization_id, user_id, role::text, status::text
                     from public.organization_members
                    where organization_id = $1 order by created_at""",
                organization_id,
            )
        return [_membership(row) for row in rows]

    async def organization_invites(
        self, user_id: UUID, organization_id: UUID
    ) -> list[dict[str, Any]]:
        async with self.database.authenticated(user_id, organization_id) as connection:
            rows = await connection.fetch(
                """select id,email::text,role::text,expires_at,accepted_at,revoked_at,created_at
                     from public.organization_invites where organization_id=$1
                     order by created_at desc""",
                organization_id,
            )
        return [dict(row) for row in rows]

    async def onboarding(
        self, user_id: UUID, payload: OnboardingSubmitRequest
    ) -> OnboardingSubmitResponse:
        async with self.database.privileged() as connection:
            already_member = await connection.fetchval(
                "select exists(select 1 from public.organization_members where user_id = $1)",
                user_id,
            )
            if already_member:
                raise HTTPException(status_code=409, detail="Onboarding already completed")
            await connection.execute(
                """insert into public.profiles(id, display_name, locale, timezone)
                     values ($1, $2, $3, $4)
                     on conflict (id) do update set display_name = excluded.display_name,
                       locale = excluded.locale, timezone = excluded.timezone""",
                user_id,
                payload.profile.display_name,
                payload.profile.locale,
                payload.profile.timezone,
            )
            settings = {"goals": payload.goals, "approvalPolicy": payload.approval_policy}
            try:
                organization_id = await connection.fetchval(
                    """insert into public.organizations
                           (name, slug, timezone, locale, settings, created_by)
                         values ($1, $2, $3, $4, $5::jsonb, $6) returning id""",
                    payload.organization.name,
                    payload.organization.slug,
                    payload.organization.timezone,
                    payload.organization.locale,
                    json.dumps(settings),
                    user_id,
                )
            except asyncpg.UniqueViolationError as exc:
                raise HTTPException(
                    status_code=409, detail="Organization slug already exists"
                ) from exc
            await connection.execute(
                """insert into public.organization_members
                       (organization_id, user_id, role, status, joined_at)
                     values ($1, $2, 'owner', 'active', now())""",
                organization_id,
                user_id,
            )
        return OnboardingSubmitResponse(
            organization_id=organization_id,
            owner_membership_id=_membership_id(organization_id, user_id),
        )

    async def organizations(
        self, user_id: UUID, include_suspended: bool = False
    ) -> list[Organization]:
        query = (
            ACTIVE_OR_SUSPENDED_ORGANIZATIONS_QUERY
            if include_suspended
            else ACTIVE_ORGANIZATIONS_QUERY
        )
        async with self.database.authenticated(user_id) as connection:
            rows = await connection.fetch(query, user_id)
        return [Organization.model_validate(dict(row)) for row in rows]

    async def preferences(self, user_id: UUID) -> PreferencesResponse:
        async with self.database.authenticated(user_id) as connection:
            row = await connection.fetchrow(
                """select id, display_name, avatar_path, locale, timezone,
                          preferences, updated_at
                     from public.profiles where id = $1""",
                user_id,
            )
        if not row:
            raise HTTPException(status_code=404, detail="Profile not found")
        sessions = await self._sessions(user_id)
        return _preferences_response(row, sessions)

    async def patch_preferences(
        self, user_id: UUID, payload: PreferencesPatchRequest
    ) -> PreferencesResponse:
        async with self.database.authenticated(user_id) as connection:
            current = await connection.fetchrow(
                """select id, display_name, avatar_path, locale, timezone, preferences, updated_at
                     from public.profiles where id = $1 for update""",
                user_id,
            )
            if not current:
                raise HTTPException(status_code=404, detail="Profile not found")
            if payload.expected_updated_at and current["updated_at"] != payload.expected_updated_at:
                raise HTTPException(
                    status_code=409, detail="Preferences changed in another session"
                )
            preferences = dict(current["preferences"])
            if payload.theme is not None:
                preferences["theme"] = payload.theme
            if payload.accessibility is not None:
                preferences["accessibility"] = payload.accessibility
            row = await connection.fetchrow(
                """update public.profiles
                      set locale = coalesce($2, locale), timezone = coalesce($3, timezone),
                          preferences = $4::jsonb
                    where id = $1
                returning id, display_name, avatar_path, locale, timezone,
                          preferences, updated_at""",
                user_id,
                payload.locale,
                payload.timezone,
                json.dumps(preferences),
            )
        return _preferences_response(cast(Record, row), await self._sessions(user_id))

    async def _sessions(self, user_id: UUID) -> list[Session]:
        async with self.database.privileged() as connection:
            rows = await connection.fetch(
                """select id, created_at, not_after from auth.sessions
                    where user_id = $1 order by created_at desc""",
                user_id,
            )
        return [Session(id=str(row["id"]), expires_at=row["not_after"]) for row in rows]

    async def create_invite(
        self, organization_id: UUID, invited_by: UUID, email: str, role: MemberRole, hours: int
    ) -> InvitationCreatedResponse:
        normalized_email = email.strip().lower()
        generated_token = secrets.token_urlsafe(32)
        token: str | None = generated_token
        token_hash = _token_hash(generated_token)
        expires_at = datetime.now(UTC) + timedelta(hours=hours)
        try:
            async with self.database.privileged() as connection:
                row = await connection.fetchrow(
                    """insert into public.organization_invites
                       (organization_id, email, role, token_hash, invited_by, expires_at)
                     select $1, $2, $3, $4, $5, $6
                      where exists (
                        select 1 from public.organization_members
                         where organization_id = $1 and user_id = $5
                           and status = 'active' and role in ('owner', 'admin')
                      )
                  returning id, email::text, role::text, expires_at""",
                    organization_id,
                    normalized_email,
                    role.value,
                    token_hash,
                    invited_by,
                    expires_at,
                )
        except asyncpg.UniqueViolationError:
            async with self.database.privileged() as connection:
                row = await connection.fetchrow(
                    """select i.id, i.email::text, i.role::text, i.expires_at
                         from public.organization_invites i
                        where i.organization_id = $1 and i.email = $2
                          and i.accepted_at is null and i.revoked_at is null
                          and exists (
                            select 1 from public.organization_members m
                             where m.organization_id = i.organization_id and m.user_id = $3
                               and m.status = 'active' and m.role in ('owner', 'admin')
                          )""",
                    organization_id,
                    normalized_email,
                    invited_by,
                )
            token = None
        if not row:
            raise HTTPException(status_code=409, detail="Invite conflict")
        return InvitationCreatedResponse(
            id=row["id"],
            email=row["email"],
            role=row["role"],
            expires_at=row["expires_at"],
            token=token,
        )

    async def invite_email(self, token: str) -> str:
        async with self.database.privileged() as connection:
            row = await connection.fetchrow(
                """select email::text, expires_at, accepted_at, revoked_at
                     from public.organization_invites where token_hash = $1""",
                _token_hash(token),
            )
        _validate_invite(row)
        return cast(str, row["email"])

    async def accept_invite(
        self, token: str, user_id: UUID, email: str, full_name: str
    ) -> Membership:
        async with self.database.privileged() as connection:
            row = await connection.fetchrow(
                """select id, organization_id, email::text, role::text, expires_at,
                          accepted_at, revoked_at
                     from public.organization_invites where token_hash = $1 for update""",
                _token_hash(token),
            )
            _validate_invite(row)
            if cast(str, row["email"]).casefold() != email.casefold():
                raise HTTPException(status_code=409, detail="Invite email does not match session")
            await connection.execute(
                """insert into public.profiles(id, display_name)
                     values ($1, $2) on conflict (id) do update
                       set display_name = excluded.display_name""",
                user_id,
                full_name,
            )
            await connection.execute(
                """insert into public.organization_members
                       (organization_id, user_id, role, status, joined_at)
                     values ($1, $2, $3, 'active', now())
                     on conflict (organization_id, user_id) do update
                       set role = excluded.role, status = 'active',
                           joined_at = coalesce(organization_members.joined_at, now())""",
                row["organization_id"],
                user_id,
                row["role"],
            )
            await connection.execute(
                "update public.organization_invites set accepted_at = now() where id = $1",
                row["id"],
            )
        return Membership(
            id=_membership_id(row["organization_id"], user_id),
            organization_id=row["organization_id"],
            user_id=user_id,
            role=row["role"],
            status="active",
        )

    async def patch_membership(
        self, organization_id: UUID, actor_user_id: UUID, payload: MembershipPatchRequest
    ) -> Membership:
        try:
            async with self.database.privileged() as connection:
                row = await connection.fetchrow(
                    """update public.organization_members
                      set role = coalesce($3, role), status = coalesce($4, status)
                    where organization_id = $1 and user_id = $2
                      and exists (
                        select 1 from public.organization_members actor
                         where actor.organization_id = $1 and actor.user_id = $5
                           and actor.status = 'active' and actor.role in ('owner', 'admin')
                      )
                returning organization_id, user_id, role::text, status::text""",
                    organization_id,
                    payload.user_id,
                    payload.role.value if payload.role else None,
                    payload.status,
                    actor_user_id,
                )
                if row:
                    changes = json.dumps({"role": row["role"], "status": row["status"]})
                    await connection.execute(
                        """insert into public.event_outbox(
                               organization_id,event_type,aggregate_type,aggregate_id,payload)
                           values($1,'memberships.updated','membership',$2,$3::jsonb)""",
                        organization_id,
                        payload.user_id,
                        changes,
                    )
                    await connection.execute(
                        """insert into public.audit_log(
                               organization_id,actor_user_id,actor_type,action,resource_type,
                               resource_id,risk_level,changes_redacted)
                           values($1,$2,'user','membership.updated','membership',$3,'high',$4::jsonb)""",
                        organization_id,
                        actor_user_id,
                        str(payload.user_id),
                        changes,
                    )
        except asyncpg.CheckViolationError as exc:
            raise HTTPException(status_code=409, detail="The last owner cannot be changed") from exc
        if not row:
            raise HTTPException(status_code=404, detail="Membership not found")
        return _membership(row)


def _membership(row: Mapping[str, Any]) -> Membership:
    return Membership(
        id=_membership_id(row["organization_id"], row["user_id"]),
        organization_id=row["organization_id"],
        user_id=row["user_id"],
        role=row["role"],
        status=row["status"],
    )


def _membership_id(organization_id: UUID, user_id: UUID) -> str:
    return f"{organization_id}:{user_id}"


def _preferences_response(row: Mapping[str, Any], sessions: list[Session]) -> PreferencesResponse:
    return PreferencesResponse(
        profile=Profile.model_validate(
            {
                key: row[key]
                for key in ("id", "display_name", "avatar_path", "locale", "timezone", "updated_at")
            }
        ),
        preferences=_json_object(row["preferences"]),
        sessions=sessions,
    )


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return {}
    return dict(value) if isinstance(value, Mapping) else {}


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _validate_invite(row: Mapping[str, Any] | None) -> None:
    if not row:
        raise HTTPException(status_code=404, detail="Invitation not found")
    if row["revoked_at"] is not None:
        raise HTTPException(status_code=410, detail="Invitation revoked")
    if row["accepted_at"] is not None:
        raise HTTPException(status_code=409, detail="Invitation already used")
    if row["expires_at"] <= datetime.now(UTC):
        raise HTTPException(status_code=410, detail="Invitation expired")
