from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
    status,
)

from bighead_api.commercial.models import (
    CampaignListResponse,
    ContentAssetCreateRequest,
    ContentAssetResponse,
    CrmAccountMergeRequest,
    CrmAccountMergeResponse,
    CrmImportRequest,
    CrmImportResponse,
    CrmImportResumeRequest,
    KnowledgeDocumentResponse,
    KnowledgeUploadRequest,
    KnowledgeUploadResponse,
    LeadDetailResponse,
    LeadFollowUpRequest,
    LeadFollowUpResponse,
    LeadListResponse,
    MemoryItemResponse,
    OpportunityStageRequest,
    OpportunityStageResponse,
    PipelineBoardResponse,
    PublicationRetryRequest,
    PublicationRetryResponse,
    SemanticSearchRequest,
    SemanticSearchResponse,
)
from bighead_api.commercial.service import CommercialRepository
from bighead_api.identity.dependencies import TenantContext, tenant_context

router = APIRouter(prefix="/v1")


def repository(request: Request) -> CommercialRepository:
    return cast(CommercialRepository, request.app.state.commercial_repository)


@router.get(
    "/knowledge/documents",
    tags=["knowledge"],
    response_model=KnowledgeDocumentResponse,
    operation_id="t35Get",
    summary="T35 - /v1/knowledge/documents",
    response_description="T35 successful response",
)
async def documents(
    context: Annotated[TenantContext, Depends(tenant_context)],
    repo: Annotated[CommercialRepository, Depends(repository)],
    document_status: Annotated[str | None, Query(alias="status")] = None,
    classification: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, Any]:
    return await repo.documents(
        _user(context), context.organization_id, document_status, classification, limit
    )


@router.post(
    "/knowledge/documents",
    tags=["knowledge"],
    response_model=KnowledgeUploadResponse,
    operation_id="t36Post",
    summary="T36 - /v1/knowledge/documents",
    response_description="T36 successful response",
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_document(
    payload: KnowledgeUploadRequest,
    context: Annotated[TenantContext, Depends(tenant_context)],
    repo: Annotated[CommercialRepository, Depends(repository)],
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=1, max_length=200, pattern=r".*\S.*")
    ],
) -> dict[str, Any]:
    return await repo.upload_document(
        _user(context), context.organization_id, payload, idempotency_key
    )


@router.get(
    "/memory/items",
    tags=["memory"],
    response_model=MemoryItemResponse,
    operation_id="t37Get",
    summary="T37 - /v1/memory/items",
    response_description="T37 successful response",
)
async def memory_items(
    context: Annotated[TenantContext, Depends(tenant_context)],
    repo: Annotated[CommercialRepository, Depends(repository)],
    kind: str | None = None,
    item_status: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, Any]:
    return await repo.memory_items(
        _user(context), context.organization_id, kind, item_status, limit
    )


@router.post(
    "/search/semantic",
    tags=["search"],
    response_model=SemanticSearchResponse,
    operation_id="t38Post",
    summary="T38 - /v1/search/semantic",
    response_description="T38 successful response",
)
async def semantic_search(
    payload: SemanticSearchRequest,
    response: Response,
    context: Annotated[TenantContext, Depends(tenant_context)],
    repo: Annotated[CommercialRepository, Depends(repository)],
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    return await repo.semantic_search(
        _user(context), context.organization_id, context.membership.role, payload
    )


@router.post(
    "/crm/imports",
    tags=["crm"],
    response_model=CrmImportResponse,
    operation_id="t39Post",
    summary="T39 - /v1/crm/imports",
    response_description="T39 successful response",
    status_code=status.HTTP_202_ACCEPTED,
)
async def crm_import(
    payload: CrmImportRequest,
    context: Annotated[TenantContext, Depends(tenant_context)],
    repo: Annotated[CommercialRepository, Depends(repository)],
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=1, max_length=200, pattern=r".*\S.*")
    ],
) -> dict[str, Any]:
    return await repo.crm_import(
        _user(context),
        context.organization_id,
        context.membership.role,
        payload,
        idempotency_key,
    )


@router.post(
    "/crm/imports/{importId}/resume",
    tags=["crm"],
    response_model=CrmImportResponse,
    operation_id="t39ResumePost",
    summary="T39 - resume failed CRM import rows",
)
async def resume_crm_import(
    import_id: Annotated[UUID, Path(alias="importId")],
    payload: CrmImportResumeRequest,
    context: Annotated[TenantContext, Depends(tenant_context)],
    repo: Annotated[CommercialRepository, Depends(repository)],
) -> dict[str, Any]:
    return await repo.resume_crm_import(
        _user(context), context.organization_id, context.membership.role, import_id, payload
    )


@router.post(
    "/crm/accounts/{accountId}/merge",
    tags=["crm"],
    response_model=CrmAccountMergeResponse,
    operation_id="t39AccountMergePost",
    summary="T39 - merge duplicate CRM account",
)
async def merge_crm_account(
    account_id: Annotated[UUID, Path(alias="accountId")],
    payload: CrmAccountMergeRequest,
    context: Annotated[TenantContext, Depends(tenant_context)],
    repo: Annotated[CommercialRepository, Depends(repository)],
) -> dict[str, Any]:
    return await repo.merge_crm_accounts(
        _user(context),
        context.organization_id,
        context.membership.role,
        account_id,
        payload.target_account_id,
        payload.reason,
    )


@router.get(
    "/crm/leads",
    tags=["crm"],
    response_model=LeadListResponse,
    operation_id="t40Get",
    summary="T40 - /v1/crm/leads",
    response_description="T40 successful response",
)
async def leads(
    context: Annotated[TenantContext, Depends(tenant_context)],
    repo: Annotated[CommercialRepository, Depends(repository)],
    lead_status: Annotated[str | None, Query(alias="stage")] = None,
    owner_id: Annotated[UUID | None, Query(alias="ownerId")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, Any]:
    return await repo.leads(_user(context), context.organization_id, lead_status, owner_id, limit)


@router.get(
    "/crm/leads/{leadId}",
    tags=["crm"],
    response_model=LeadDetailResponse,
    operation_id="t41Get",
    summary="T41 - /v1/crm/leads/{leadId}",
    response_description="T41 successful response",
)
async def lead(
    lead_id: Annotated[UUID, Path(alias="leadId")],
    context: Annotated[TenantContext, Depends(tenant_context)],
    repo: Annotated[CommercialRepository, Depends(repository)],
) -> dict[str, Any]:
    return await repo.lead(_user(context), context.organization_id, lead_id)


@router.post(
    "/crm/opportunities/{id}/stage",
    tags=["crm"],
    response_model=OpportunityStageResponse,
    operation_id="t42Post",
    summary="T42 - /v1/crm/opportunities/{id}/stage",
    response_description="T42 successful response",
)
async def opportunity_stage(
    opportunity_id: Annotated[UUID, Path(alias="id")],
    payload: OpportunityStageRequest,
    context: Annotated[TenantContext, Depends(tenant_context)],
    repo: Annotated[CommercialRepository, Depends(repository)],
) -> dict[str, Any]:
    return await repo.opportunity_stage(
        _user(context), context.organization_id, context.membership.role, opportunity_id, payload
    )


@router.get(
    "/crm/pipeline",
    tags=["crm"],
    response_model=PipelineBoardResponse,
    operation_id="crmPipelineGet",
    summary="CRM opportunity pipeline board",
)
async def pipeline(
    context: Annotated[TenantContext, Depends(tenant_context)],
    repo: Annotated[CommercialRepository, Depends(repository)],
) -> dict[str, Any]:
    return await repo.pipeline(_user(context), context.organization_id)


@router.post(
    "/crm/leads/{leadId}/follow-ups",
    tags=["crm"],
    response_model=LeadFollowUpResponse,
    operation_id="crmLeadFollowUpPost",
    summary="Create an idempotent lead follow-up",
    status_code=status.HTTP_201_CREATED,
)
async def create_lead_follow_up(
    lead_id: Annotated[UUID, Path(alias="leadId")],
    payload: LeadFollowUpRequest,
    context: Annotated[TenantContext, Depends(tenant_context)],
    repo: Annotated[CommercialRepository, Depends(repository)],
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=1, max_length=200, pattern=r".*\S.*")
    ],
) -> dict[str, Any]:
    return await repo.create_lead_follow_up(
        _user(context), context.organization_id, lead_id, payload, idempotency_key
    )


@router.get(
    "/content/campaigns",
    tags=["content"],
    response_model=CampaignListResponse,
    operation_id="t43Get",
    summary="T43 - /v1/content/campaigns",
    response_description="T43 successful response",
)
async def campaigns(
    context: Annotated[TenantContext, Depends(tenant_context)],
    repo: Annotated[CommercialRepository, Depends(repository)],
    campaign_status: Annotated[str | None, Query(alias="status")] = None,
    channel: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, Any]:
    return await repo.campaigns(
        _user(context), context.organization_id, campaign_status, channel, limit
    )


@router.get(
    "/content/assets",
    tags=["content"],
    response_model=ContentAssetResponse,
    operation_id="t44Get",
    summary="T44 - /v1/content/assets",
    response_description="T44 successful response",
)
async def content_assets(
    context: Annotated[TenantContext, Depends(tenant_context)],
    repo: Annotated[CommercialRepository, Depends(repository)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, Any]:
    return await repo.content_assets(_user(context), context.organization_id, limit)


@router.post(
    "/content/assets",
    tags=["content"],
    response_model=ContentAssetResponse,
    operation_id="t44Post",
    summary="T44 - /v1/content/assets",
    response_description="T44 successful response",
    status_code=status.HTTP_201_CREATED,
)
async def create_content_asset(
    payload: ContentAssetCreateRequest,
    context: Annotated[TenantContext, Depends(tenant_context)],
    repo: Annotated[CommercialRepository, Depends(repository)],
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=1, max_length=200, pattern=r".*\S.*")
    ],
) -> dict[str, Any]:
    return await repo.create_content_asset(
        _user(context), context.organization_id, payload, idempotency_key
    )


@router.post(
    "/content/publications/{id}/retry",
    tags=["content"],
    response_model=PublicationRetryResponse,
    operation_id="t45Post",
    summary="T45 - /v1/content/publications/{id}/retry",
    response_description="T45 successful response",
)
async def retry_publication(
    asset_id: Annotated[UUID, Path(alias="id")],
    payload: PublicationRetryRequest,
    context: Annotated[TenantContext, Depends(tenant_context)],
    repo: Annotated[CommercialRepository, Depends(repository)],
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=1, max_length=200, pattern=r".*\S.*")
    ],
) -> dict[str, Any]:
    return await repo.retry_publication(
        _user(context), context.organization_id, asset_id, payload, idempotency_key
    )


def _user(context: TenantContext) -> UUID:
    if context.user.id is None:
        raise HTTPException(status_code=401, detail="Authenticated user required")
    return context.user.id
