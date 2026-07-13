from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from bighead_api.artifacts.models import (
    ArtifactDownloadResponse,
    ArtifactStatusResponse,
    UploadConfirmRequest,
    UploadInitiateRequest,
    UploadInitiateResponse,
)
from bighead_api.artifacts.service import ArtifactService
from bighead_api.identity.dependencies import TenantContext, tenant_context

router = APIRouter(prefix="/v1/artifacts", tags=["artifacts"])


def artifact_service(request: Request) -> ArtifactService:
    return cast(ArtifactService, request.app.state.artifact_service)


@router.post("/uploads", response_model=UploadInitiateResponse, status_code=status.HTTP_201_CREATED)
async def initiate_upload(
    payload: UploadInitiateRequest,
    context: Annotated[TenantContext, Depends(tenant_context)],
    service: Annotated[ArtifactService, Depends(artifact_service)],
) -> UploadInitiateResponse:
    return await service.initiate(context.organization_id, _user_id(context), payload)


@router.post(
    "/{artifact_id}/confirm",
    response_model=ArtifactStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def confirm_upload(
    artifact_id: UUID,
    payload: UploadConfirmRequest,
    context: Annotated[TenantContext, Depends(tenant_context)],
    service: Annotated[ArtifactService, Depends(artifact_service)],
) -> ArtifactStatusResponse:
    return await service.confirm(context.organization_id, artifact_id, payload)


@router.get("/{artifact_id}/download", response_model=ArtifactDownloadResponse)
async def download_artifact(
    artifact_id: UUID,
    context: Annotated[TenantContext, Depends(tenant_context)],
    service: Annotated[ArtifactService, Depends(artifact_service)],
) -> ArtifactDownloadResponse:
    return await service.download(context.organization_id, artifact_id)


def _user_id(context: TenantContext) -> UUID:
    if context.user.id is None:
        raise HTTPException(status_code=401, detail="Authenticated user required")
    return context.user.id
