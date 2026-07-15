from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, Request

from bighead_api.administration.models import (
    AnalyticsSummaryRecordPage,
    AnalyticsSummaryResponse,
    AttributionModel,
    AuditPage,
    CostGroup,
    ExperimentPage,
    ExperimentPatchRequest,
    ExperimentStartRequest,
    IntegrationStatus,
    LegalHoldCreateRequest,
    OrganizationPatchRequest,
    PrivacyRequestCreateRequest,
    RetentionPolicyRequest,
)
from bighead_api.administration.service import AdministrationRepository
from bighead_api.identity.dependencies import TenantContext, require_roles
from bighead_api.identity.models import MemberRole

router = APIRouter(prefix="/v1")
AdminContext = Annotated[TenantContext, require_roles(MemberRole.OWNER, MemberRole.ADMIN)]
AnalystContext = Annotated[
    TenantContext, require_roles(MemberRole.OWNER, MemberRole.ADMIN, MemberRole.ANALYST)
]
ExecutiveContext = Annotated[TenantContext, require_roles(MemberRole.OWNER, MemberRole.ANALYST)]
ManagerContext = Annotated[
    TenantContext, require_roles(MemberRole.OWNER, MemberRole.ADMIN, MemberRole.MANAGER)
]


def repository(request: Request) -> AdministrationRepository:
    return cast(AdministrationRepository, request.app.state.administration_repository)


@router.get("/experiments", response_model=ExperimentPage, tags=["experiments"])
async def experiments(
    context: AnalystContext,
    repo: Annotated[AdministrationRepository, Depends(repository)],
) -> ExperimentPage:
    return await repo.experiments(_user(context), context.organization_id)


@router.get("/experiments/{experimentId}", tags=["experiments"])
async def experiment(
    experiment_id: Annotated[UUID, Path(alias="experimentId")],
    context: AnalystContext,
    repo: Annotated[AdministrationRepository, Depends(repository)],
) -> dict[str, Any]:
    return await repo.experiment(_user(context), context.organization_id, experiment_id)


@router.patch("/experiments/{experimentId}", tags=["experiments"])
async def patch_experiment(
    experiment_id: Annotated[UUID, Path(alias="experimentId")],
    payload: ExperimentPatchRequest,
    context: AnalystContext,
    repo: Annotated[AdministrationRepository, Depends(repository)],
) -> dict[str, Any]:
    return await repo.patch_experiment(
        _user(context), context.organization_id, experiment_id, payload
    )


@router.get(
    "/analytics/summary/records",
    response_model=AnalyticsSummaryRecordPage,
    tags=["analytics"],
)
async def summary_records(
    context: ExecutiveContext,
    repo: Annotated[AdministrationRepository, Depends(repository)],
    dimension: Annotated[
        str,
        Query(
            pattern="^(new|triaged|in_progress|waiting_tool|waiting_human|ready_for_review|approved|failed|done|canceled)$"
        ),
    ],
    start: Annotated[datetime | None, Query(alias="from")] = None,
    end: Annotated[datetime | None, Query(alias="to")] = None,
    cursor: Annotated[str | None, Query(min_length=1, max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AnalyticsSummaryRecordPage:
    start, end = _period(start, end)
    return AnalyticsSummaryRecordPage.model_validate(
        await repo.analytics_summary_records(
            _user(context),
            context.organization_id,
            dimension,
            start,
            end,
            cursor,
            limit,
        )
    )


@router.post("/experiments/{experimentId}/start", tags=["experiments"])
async def start_experiment(
    experiment_id: Annotated[UUID, Path(alias="experimentId")],
    payload: ExperimentStartRequest,
    context: AnalystContext,
    repo: Annotated[AdministrationRepository, Depends(repository)],
) -> dict[str, Any]:
    return await repo.start_experiment(
        _user(context),
        context.organization_id,
        experiment_id,
        payload.expected_updated_at,
    )


@router.get(
    "/analytics/summary",
    response_model=AnalyticsSummaryResponse,
    tags=["analytics"],
)
async def summary(
    context: ExecutiveContext,
    repo: Annotated[AdministrationRepository, Depends(repository)],
    start: Annotated[datetime | None, Query(alias="from")] = None,
    end: Annotated[datetime | None, Query(alias="to")] = None,
    timezone: Annotated[str | None, Query(min_length=1, max_length=64)] = None,
    cards: Annotated[list[str] | None, Query()] = None,
) -> AnalyticsSummaryResponse:
    start, end = _period(start, end)
    return AnalyticsSummaryResponse.model_validate(
        await repo.analytics(
            _user(context),
            context.organization_id,
            "summary",
            start,
            end,
            timezone,
            {"cards": cards or []},
        )
    )


@router.get("/analytics/operations", tags=["analytics"])
async def operations(
    context: ManagerContext,
    repo: Annotated[AdministrationRepository, Depends(repository)],
    start: Annotated[datetime | None, Query(alias="from")] = None,
    end: Annotated[datetime | None, Query(alias="to")] = None,
    timezone: Annotated[str | None, Query(min_length=1, max_length=64)] = None,
    team_ids: Annotated[list[UUID] | None, Query(alias="teamIds")] = None,
    compare_to: Annotated[
        str | None,
        Query(alias="compareTo", pattern="^(previous_period|previous_year)$"),
    ] = None,
) -> dict[str, Any]:
    start, end = _period(start, end)
    return await repo.analytics(
        _user(context),
        context.organization_id,
        "operations",
        start,
        end,
        timezone,
        {"team_ids": team_ids or [], "compare_to": compare_to},
    )


@router.get("/analytics/agents", tags=["analytics"])
async def agents(
    context: AdminContext,
    repo: Annotated[AdministrationRepository, Depends(repository)],
    start: Annotated[datetime | None, Query(alias="from")] = None,
    end: Annotated[datetime | None, Query(alias="to")] = None,
    timezone: Annotated[str | None, Query(min_length=1, max_length=64)] = None,
    provider: Annotated[str | None, Query(min_length=1, max_length=120)] = None,
    model_id: Annotated[UUID | None, Query(alias="modelId")] = None,
) -> dict[str, Any]:
    start, end = _period(start, end)
    return await repo.analytics(
        _user(context),
        context.organization_id,
        "agents",
        start,
        end,
        timezone,
        {"provider": provider, "model_id": model_id},
    )


@router.get("/analytics/costs", tags=["analytics"])
async def costs(
    context: AdminContext,
    repo: Annotated[AdministrationRepository, Depends(repository)],
    start: Annotated[datetime | None, Query(alias="from")] = None,
    end: Annotated[datetime | None, Query(alias="to")] = None,
    timezone: Annotated[str | None, Query(min_length=1, max_length=64)] = None,
    group_by: Annotated[CostGroup, Query(alias="groupBy")] = "currency",
    organization_id: Annotated[UUID | None, Query(alias="organizationId")] = None,
) -> dict[str, Any]:
    if organization_id is not None and organization_id != context.organization_id:
        raise HTTPException(status_code=403, detail="Query tenant does not match request tenant")
    start, end = _period(start, end)
    return await repo.analytics(
        _user(context),
        context.organization_id,
        "costs",
        start,
        end,
        timezone,
        {"group_by": group_by},
    )


@router.get("/analytics/funnel", tags=["analytics"])
async def funnel(
    context: AnalystContext,
    repo: Annotated[AdministrationRepository, Depends(repository)],
    start: Annotated[datetime | None, Query(alias="from")] = None,
    end: Annotated[datetime | None, Query(alias="to")] = None,
    timezone: Annotated[str | None, Query(min_length=1, max_length=64)] = None,
    attribution_model: Annotated[AttributionModel, Query(alias="attributionModel")] = "last_touch",
    campaign_ids: Annotated[list[UUID] | None, Query(alias="campaignIds")] = None,
) -> dict[str, Any]:
    start, end = _period(start, end)
    return await repo.analytics(
        _user(context),
        context.organization_id,
        "funnel",
        start,
        end,
        timezone,
        {"attribution_model": attribution_model, "campaign_ids": campaign_ids or []},
    )


@router.get("/organizations/{organizationId}", tags=["administration"])
async def organization(
    organization_id: Annotated[UUID, Path(alias="organizationId")],
    context: AdminContext,
    repo: Annotated[AdministrationRepository, Depends(repository)],
) -> dict[str, Any]:
    if organization_id != context.organization_id:
        raise HTTPException(status_code=403, detail="Path tenant does not match request tenant")
    return await repo.organization(_user(context), context.organization_id)


@router.patch("/organizations/{organizationId}", tags=["administration"])
async def patch_organization(
    organization_id: Annotated[UUID, Path(alias="organizationId")],
    payload: OrganizationPatchRequest,
    context: AdminContext,
    repo: Annotated[AdministrationRepository, Depends(repository)],
) -> dict[str, Any]:
    if organization_id != context.organization_id:
        # Do not let a valid membership header authorize a different path tenant.
        raise HTTPException(status_code=403, detail="Path tenant does not match request tenant")
    return await repo.patch_organization(_user(context), organization_id, payload)


@router.get("/integrations", tags=["administration"])
async def integrations(
    context: AdminContext,
    repo: Annotated[AdministrationRepository, Depends(repository)],
    provider: Annotated[str | None, Query(min_length=1, max_length=120)] = None,
    status: Annotated[IntegrationStatus, Query()] = "all",
) -> dict[str, Any]:
    return await repo.integrations(_user(context), context.organization_id, provider, status)


@router.get("/audit/events", response_model=AuditPage, tags=["administration"])
async def audit_events(
    context: AdminContext,
    repo: Annotated[AdministrationRepository, Depends(repository)],
    resource_type: Annotated[str | None, Query(alias="resourceType")] = None,
    actor_id: Annotated[UUID | None, Query(alias="actorId")] = None,
    cursor: Annotated[str | None, Query(min_length=1, max_length=512)] = None,
    legal_hold: Annotated[bool | None, Query(alias="legalHold")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AuditPage:
    return await repo.audit_events(
        _user(context),
        context.organization_id,
        resource_type,
        actor_id,
        cursor,
        legal_hold,
        limit,
    )


@router.post("/privacy/requests", status_code=202, tags=["administration"])
async def create_privacy_request(
    payload: PrivacyRequestCreateRequest,
    context: AdminContext,
    repo: Annotated[AdministrationRepository, Depends(repository)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)],
) -> dict[str, Any]:
    return await repo.create_privacy_request(
        _user(context), context.organization_id, idempotency_key, payload
    )


@router.get("/privacy/requests", tags=["administration"])
async def privacy_requests(
    context: AdminContext,
    repo: Annotated[AdministrationRepository, Depends(repository)],
) -> dict[str, Any]:
    return await repo.privacy_requests(_user(context), context.organization_id)


@router.get("/privacy/requests/{requestId}/export", tags=["administration"])
async def privacy_export(
    request_id: Annotated[UUID, Path(alias="requestId")],
    context: AdminContext,
    repo: Annotated[AdministrationRepository, Depends(repository)],
) -> dict[str, Any]:
    return await repo.privacy_export(_user(context), context.organization_id, request_id)


@router.post("/privacy/legal-holds", status_code=201, tags=["administration"])
async def create_legal_hold(
    payload: LegalHoldCreateRequest,
    context: AdminContext,
    repo: Annotated[AdministrationRepository, Depends(repository)],
) -> dict[str, Any]:
    return await repo.create_legal_hold(_user(context), context.organization_id, payload)


@router.delete("/privacy/legal-holds/{holdId}", tags=["administration"])
async def release_legal_hold(
    hold_id: Annotated[UUID, Path(alias="holdId")],
    context: AdminContext,
    repo: Annotated[AdministrationRepository, Depends(repository)],
) -> dict[str, Any]:
    return await repo.release_legal_hold(_user(context), context.organization_id, hold_id)


@router.put("/privacy/retention-policy", tags=["administration"])
async def update_retention(
    payload: RetentionPolicyRequest,
    context: AdminContext,
    repo: Annotated[AdministrationRepository, Depends(repository)],
) -> dict[str, Any]:
    return await repo.update_retention(_user(context), context.organization_id, payload)


def _period(start: datetime | None, end: datetime | None) -> tuple[datetime, datetime]:
    resolved_end = end or datetime.now(UTC)
    resolved_start = start or resolved_end - timedelta(days=30)
    if resolved_start.tzinfo is None or resolved_end.tzinfo is None:
        raise HTTPException(
            status_code=422, detail="Analytics period must include timezone offsets"
        )
    return resolved_start, resolved_end


def _user(context: TenantContext) -> UUID:
    if context.user.id is None:
        raise HTTPException(status_code=401, detail="Authenticated user required")
    return context.user.id
