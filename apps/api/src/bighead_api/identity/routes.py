from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from bighead_api.identity.auth import AuthProvider, optional_bearer_token
from bighead_api.identity.dependencies import (
    TenantContext,
    UserSession,
    auth_provider,
    current_session,
    identity_repository,
    require_roles,
    tenant_context,
)
from bighead_api.identity.models import (
    AuthCallbackRequest,
    AuthSessionResponse,
    InvitationAcceptRequest,
    InvitationAcceptResponse,
    InvitationCreatedResponse,
    InvitationCreateRequest,
    LoginMethod,
    LoginRequest,
    MemberRole,
    Membership,
    MembershipListResponse,
    MembershipPatchRequest,
    OnboardingSubmitRequest,
    OnboardingSubmitResponse,
    OrganizationListResponse,
    PreferencesPatchRequest,
    PreferencesResponse,
    RecoveryCompleteRequest,
    RecoveryRequest,
    RecoveryRequestedResponse,
    SessionRevokeRequest,
    SignupRequest,
    SwitchOrganizationResponse,
)
from bighead_api.identity.repository import IdentityRepository

router = APIRouter(prefix="/v1")


@router.post("/auth/signup", response_model=AuthSessionResponse, tags=["access"])
async def signup(
    payload: SignupRequest,
    provider: Annotated[AuthProvider, Depends(auth_provider)],
) -> AuthSessionResponse:
    user, session = await provider.signup(str(payload.email), payload.password)
    return AuthSessionResponse(
        session=session,
        user=user,
        memberships=[],
        status="authenticated" if session else "confirmation_required",
    )


@router.post("/auth/callback", response_model=AuthSessionResponse, tags=["access"])
async def auth_callback(
    payload: AuthCallbackRequest,
    provider: Annotated[AuthProvider, Depends(auth_provider)],
    repository: Annotated[IdentityRepository, Depends(identity_repository)],
) -> AuthSessionResponse:
    user, session = await provider.exchange_code(payload.code, payload.code_verifier)
    memberships = await repository.memberships(user.id) if user.id else []
    return AuthSessionResponse(session=session, user=user, memberships=memberships)


@router.post("/auth/login", response_model=AuthSessionResponse, tags=["access"])
async def login(
    payload: LoginRequest,
    provider: Annotated[AuthProvider, Depends(auth_provider)],
    repository: Annotated[IdentityRepository, Depends(identity_repository)],
) -> AuthSessionResponse:
    if payload.provider:
        raise HTTPException(status_code=422, detail="Provider login must use the PKCE callback")
    if (
        not payload.password_or_magic_link
        or payload.password_or_magic_link == LoginMethod.MAGIC_LINK
    ):
        user = await provider.send_magic_link(str(payload.email))
        return AuthSessionResponse(
            session=None, user=user, memberships=[], status="magic_link_sent"
        )
    user, session = await provider.login(str(payload.email), payload.password_or_magic_link)
    memberships = await repository.memberships(user.id) if user.id else []
    return AuthSessionResponse(session=session, user=user, memberships=memberships)


@router.post(
    "/auth/recovery",
    response_model=RecoveryRequestedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["access"],
)
async def recovery(
    payload: RecoveryRequest,
    provider: Annotated[AuthProvider, Depends(auth_provider)],
) -> RecoveryRequestedResponse:
    await provider.request_recovery(str(payload.email))
    # Deliberately identical whether the account exists.
    return RecoveryRequestedResponse(expires_at=datetime.now(UTC) + timedelta(hours=1))


@router.post("/auth/recovery/complete", status_code=204, tags=["access"])
async def complete_recovery(
    payload: RecoveryCompleteRequest,
    session: Annotated[UserSession, Depends(current_session)],
    provider: Annotated[AuthProvider, Depends(auth_provider)],
) -> Response:
    await provider.update_password(session.token, payload.new_password)
    return Response(status_code=204)


@router.get("/me", response_model=AuthSessionResponse, tags=["access"])
async def me(
    session: Annotated[UserSession, Depends(current_session)],
    repository: Annotated[IdentityRepository, Depends(identity_repository)],
) -> AuthSessionResponse:
    if session.user.id is None:
        raise HTTPException(status_code=401, detail="Authenticated user required")
    memberships = await repository.memberships(session.user.id, include_suspended=True)
    return AuthSessionResponse(session=None, user=session.user, memberships=memberships)


@router.post(
    "/onboarding",
    response_model=OnboardingSubmitResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["access"],
)
async def onboarding(
    payload: OnboardingSubmitRequest,
    session: Annotated[UserSession, Depends(current_session)],
    repository: Annotated[IdentityRepository, Depends(identity_repository)],
) -> OnboardingSubmitResponse:
    if session.user.id is None:
        raise HTTPException(status_code=401, detail="Authenticated user required")
    return await repository.onboarding(session.user.id, payload)


@router.get("/organizations", response_model=OrganizationListResponse, tags=["access"])
async def organizations(
    session: Annotated[UserSession, Depends(current_session)],
    repository: Annotated[IdentityRepository, Depends(identity_repository)],
    include_suspended: Annotated[bool, Query(alias="includeSuspended")] = False,
    current_organization_id: Annotated[UUID | None, Query(alias="currentOrganizationId")] = None,
) -> OrganizationListResponse:
    if session.user.id is None:
        raise HTTPException(status_code=401, detail="Authenticated user required")
    items = await repository.organizations(session.user.id, include_suspended)
    allowed_ids = {item.id for item in items}
    current = current_organization_id if current_organization_id in allowed_ids else None
    return OrganizationListResponse(organizations=items, current_organization_id=current)


@router.post(
    "/organizations/{organization_id}/switch",
    response_model=SwitchOrganizationResponse,
    tags=["access"],
    responses={403: {"description": "Active tenant membership required"}},
)
async def switch_organization(
    organization_id: UUID,
    session: Annotated[UserSession, Depends(current_session)],
    repository: Annotated[IdentityRepository, Depends(identity_repository)],
) -> SwitchOrganizationResponse:
    if session.user.id is None:
        raise HTTPException(status_code=401, detail="Authenticated user required")
    membership = await repository.membership(session.user.id, organization_id)
    if not membership or membership.status != "active":
        raise HTTPException(status_code=403, detail="Active tenant membership required")
    return SwitchOrganizationResponse(organization_id=organization_id, role=membership.role)


@router.get("/preferences", response_model=PreferencesResponse, tags=["access"])
async def get_preferences(
    context: Annotated[TenantContext, Depends(tenant_context)],
    repository: Annotated[IdentityRepository, Depends(identity_repository)],
) -> PreferencesResponse:
    return await repository.preferences(_required_user_id(context))


@router.patch("/preferences", response_model=PreferencesResponse, tags=["access"])
async def patch_preferences(
    payload: PreferencesPatchRequest,
    context: Annotated[TenantContext, Depends(tenant_context)],
    repository: Annotated[IdentityRepository, Depends(identity_repository)],
) -> PreferencesResponse:
    return await repository.patch_preferences(_required_user_id(context), payload)


@router.post(
    "/invitations/{token}/accept",
    response_model=InvitationAcceptResponse,
    tags=["access"],
)
async def accept_invitation(
    token: str,
    payload: InvitationAcceptRequest,
    request: Request,
    provider: Annotated[AuthProvider, Depends(auth_provider)],
    repository: Annotated[IdentityRepository, Depends(identity_repository)],
) -> InvitationAcceptResponse:
    if not payload.accept:
        raise HTTPException(status_code=409, detail="Invitation was not accepted")
    expected_email = await repository.invite_email(token)
    bearer = optional_bearer_token(request)
    if bearer:
        user = await provider.verify(bearer)
    elif payload.password:
        user = await provider.create_invited_user(expected_email, payload.password)
    else:
        raise HTTPException(status_code=401, detail="Session or password required")
    if user.id is None:
        raise HTTPException(status_code=401, detail="Authenticated user required")
    membership = await repository.accept_invite(token, user.id, str(user.email), payload.full_name)
    return InvitationAcceptResponse(membership=membership)


@router.post(
    "/invitations",
    response_model=InvitationCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["administration"],
)
async def create_invitation(
    payload: InvitationCreateRequest,
    context: Annotated[TenantContext, require_roles(MemberRole.OWNER, MemberRole.ADMIN)],
    repository: Annotated[IdentityRepository, Depends(identity_repository)],
) -> InvitationCreatedResponse:
    return await repository.create_invite(
        context.organization_id,
        _required_user_id(context),
        str(payload.email),
        payload.role,
        payload.expires_in_hours,
    )


@router.get("/memberships", response_model=MembershipListResponse, tags=["administration"])
async def list_memberships(
    context: Annotated[TenantContext, Depends(tenant_context)],
    repository: Annotated[IdentityRepository, Depends(identity_repository)],
) -> MembershipListResponse:
    if context.membership.role not in {MemberRole.OWNER, MemberRole.ADMIN}:
        raise HTTPException(status_code=403, detail="Insufficient organization role")
    user_id = _required_user_id(context)
    return MembershipListResponse(
        members=await repository.organization_memberships(user_id, context.organization_id),
        invites=await repository.organization_invites(user_id, context.organization_id),
    )


@router.patch("/memberships", response_model=Membership, tags=["administration"])
async def patch_membership(
    payload: MembershipPatchRequest,
    context: Annotated[TenantContext, require_roles(MemberRole.OWNER, MemberRole.ADMIN)],
    repository: Annotated[IdentityRepository, Depends(identity_repository)],
) -> Membership:
    return await repository.patch_membership(
        context.organization_id, _required_user_id(context), payload
    )


@router.post("/sessions/revoke", status_code=204, tags=["access"])
async def revoke_session(
    payload: SessionRevokeRequest,
    session: Annotated[UserSession, Depends(current_session)],
    provider: Annotated[AuthProvider, Depends(auth_provider)],
) -> Response:
    await provider.revoke(session.token, payload.scope)
    return Response(status_code=204)


def _required_user_id(context: TenantContext) -> UUID:
    if context.user.id is None:
        raise HTTPException(status_code=401, detail="Authenticated user required")
    return context.user.id
