from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from bighead_api.discovery.models import (
    GlobalSearchRequest,
    GlobalSearchResponse,
    NotificationListResponse,
)
from bighead_api.discovery.service import DiscoveryRepository
from bighead_api.identity.dependencies import TenantContext, tenant_context

router = APIRouter(prefix="/v1")


def repository(request: Request) -> DiscoveryRepository:
    return cast(DiscoveryRepository, request.app.state.discovery_repository)


@router.post("/search/global", response_model=GlobalSearchResponse, tags=["search"])
async def global_search(
    payload: GlobalSearchRequest,
    response: Response,
    context: Annotated[TenantContext, Depends(tenant_context)],
    repo: Annotated[DiscoveryRepository, Depends(repository)],
) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    return await repo.search(_user(context), context.organization_id, payload)


@router.get("/notifications", response_model=NotificationListResponse, tags=["notifications"])
async def notifications(
    context: Annotated[TenantContext, Depends(tenant_context)],
    repo: Annotated[DiscoveryRepository, Depends(repository)],
    notification_filter: Annotated[Literal["all", "unread"], Query(alias="filter")] = "all",
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, object]:
    return await repo.notifications(
        _user(context),
        context.organization_id,
        unread_only=notification_filter == "unread",
        limit=limit,
    )


def _user(context: TenantContext) -> UUID:
    if context.user.id is None:
        raise HTTPException(status_code=401, detail="Authenticated user required")
    return context.user.id
