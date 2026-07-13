from dataclasses import dataclass
from typing import Annotated, cast
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request

from bighead_api.identity.auth import AuthProvider, bearer_token
from bighead_api.identity.models import AuthUser, MemberRole, Membership
from bighead_api.identity.repository import IdentityRepository


@dataclass(frozen=True)
class UserSession:
    user: AuthUser
    token: str


@dataclass(frozen=True)
class TenantContext:
    user: AuthUser
    membership: Membership
    token: str

    @property
    def organization_id(self) -> UUID:
        return self.membership.organization_id


def auth_provider(request: Request) -> AuthProvider:
    return cast(AuthProvider, request.app.state.auth_provider)


def identity_repository(request: Request) -> IdentityRepository:
    return cast(IdentityRepository, request.app.state.identity_repository)


async def current_session(
    request: Request,
    provider: Annotated[AuthProvider, Depends(auth_provider)],
) -> UserSession:
    token = bearer_token(request)
    return UserSession(user=await provider.verify(token), token=token)


async def tenant_context(
    session: Annotated[UserSession, Depends(current_session)],
    repository: Annotated[IdentityRepository, Depends(identity_repository)],
    organization_id: Annotated[UUID | None, Header(alias="x-organization-id")] = None,
) -> TenantContext:
    if organization_id is None:
        raise HTTPException(status_code=400, detail="x-organization-id header required")
    if session.user.id is None:
        raise HTTPException(status_code=401, detail="Authenticated user required")
    membership = await repository.membership(session.user.id, organization_id)
    if membership is None or membership.status != "active":
        raise HTTPException(status_code=403, detail="Active tenant membership required")
    return TenantContext(user=session.user, membership=membership, token=session.token)


def require_roles(*roles: MemberRole) -> object:
    async def dependency(
        context: Annotated[TenantContext, Depends(tenant_context)],
    ) -> TenantContext:
        if context.membership.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient organization role")
        return context

    return Depends(dependency)
