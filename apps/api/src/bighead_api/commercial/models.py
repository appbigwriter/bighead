from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import Field, field_validator

from bighead_api.identity.models import ApiModel


class KnowledgeUploadRequest(ApiModel):
    file_ref: str = Field(min_length=1, max_length=2000)
    classification: str = "medium"
    visibility: str = "tenant"
    title: str | None = Field(default=None, max_length=500)

    @field_validator("classification")
    @classmethod
    def classification_is_valid(cls, value: str) -> str:
        if value not in {"low", "medium", "high", "critical"}:
            raise ValueError("invalid classification")
        return value

    @field_validator("file_ref")
    @classmethod
    def artifact_reference_is_uuid(cls, value: str) -> str:
        try:
            return str(UUID(value))
        except ValueError as exc:
            raise ValueError("fileRef must be an artifact UUID") from exc


class SemanticSearchRequest(ApiModel):
    query: str = Field(min_length=2, max_length=2000)
    filters: dict[str, Any] = Field(default_factory=dict)
    top_k: int = Field(default=10, ge=1, le=50)
    debug: bool = False

    @field_validator("filters")
    @classmethod
    def semantic_filters_are_valid(cls, value: dict[str, Any]) -> dict[str, Any]:
        classification = value.get("classification", "medium")
        if classification not in {"low", "medium", "high", "critical"}:
            raise ValueError("invalid classification filter")
        embedding = value.get("embedding")
        if not isinstance(embedding, list) or not 1 <= len(embedding) <= 2000:
            raise ValueError("filters.embedding must contain 1 to 2000 numbers")
        if any(not isinstance(item, int | float) or isinstance(item, bool) for item in embedding):
            raise ValueError("filters.embedding must contain only numbers")
        value["classification"] = classification
        return value


class CrmImportRequest(ApiModel):
    source: str = Field(min_length=1, max_length=120)
    rows: list[dict[str, Any]] = Field(min_length=1, max_length=1000)
    consent_basis: str = Field(min_length=1, max_length=240)


class CrmImportResumeRow(ApiModel):
    row_number: int = Field(ge=0)
    payload: dict[str, Any]


class CrmImportResumeRequest(ApiModel):
    rows: list[CrmImportResumeRow] = Field(min_length=1, max_length=1000)


class CrmAccountMergeRequest(ApiModel):
    target_account_id: UUID
    reason: str = Field(min_length=1, max_length=2000)


class OpportunityStageRequest(ApiModel):
    target_stage: str = Field(min_length=1, max_length=80)
    amount: Decimal | None = Field(default=None, gt=0)
    probability: Decimal | None = Field(default=None, ge=0, le=100)
    expected_close_date: date | None = None
    loss_reason: str | None = Field(default=None, min_length=1, max_length=2000)
    required_fields: dict[str, Any] = Field(default_factory=dict)
    forecast: dict[str, Any] = Field(default_factory=dict)


class ContentAssetCreateRequest(ApiModel):
    brief: str = Field(min_length=1, max_length=20_000)
    channels: list[str] = Field(min_length=1, max_length=20)
    variants: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    campaign_id: UUID | None = None
    task_id: UUID | None = None
    title: str | None = Field(default=None, max_length=500)
    approval_request_id: UUID | None = None


class PublicationRetryRequest(ApiModel):
    channel: str = Field(min_length=1, max_length=120)
    reason: str = Field(min_length=1, max_length=2000)


class KnowledgeDocument(ApiModel):
    id: UUID
    title: str
    source_type: str
    source_uri: str | None = None
    classification: str
    status: str
    metadata: dict[str, Any]
    created_at: datetime


class MemoryItem(ApiModel):
    id: UUID
    kind: str
    content: str
    source: dict[str, Any]
    confidence: float | None = None
    status: str
    valid_until: datetime | None = None
    created_at: datetime


class Lead(ApiModel):
    id: UUID
    account_id: UUID | None = None
    contact_id: UUID | None = None
    owner_user_id: UUID | None = None
    status: str
    source: str | None = None
    icp_score: float | None = None
    score_factors: dict[str, Any]
    score_algorithm_version: str | None = None
    next_action: str | None = None
    next_action_at: datetime | None = None
    created_at: datetime


class Opportunity(ApiModel):
    id: UUID
    name: str
    stage: str
    amount: float | None = None
    currency: str
    probability: float | None = None
    expected_close_date: date | None = None


class Campaign(ApiModel):
    id: UUID
    name: str
    objective: str | None = None
    status: str
    budget: float | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    created_at: datetime


class ContentAsset(ApiModel):
    id: UUID
    campaign_id: UUID | None = None
    title: str
    content_type: str
    status: str
    body: dict[str, Any]
    channel: str | None = None
    scheduled_at: datetime | None = None
    published_at: datetime | None = None
    external_id: str | None = None
    created_at: datetime
    updated_at: datetime


class KnowledgeDocumentResponse(ApiModel):
    documents: list[KnowledgeDocument]
    counters: dict[str, int]
    next_cursor: str | None = None


class KnowledgeUploadResponse(ApiModel):
    document_id: UUID
    job_id: UUID
    chunk_plan: dict[str, Any]
    replayed: bool = False


class MemoryItemResponse(ApiModel):
    items: list[MemoryItem]
    sources: list[dict[str, Any]]
    next_cursor: str | None = None


class SemanticSearchResponse(ApiModel):
    results: list[dict[str, Any]]
    retrieval_trace: list[dict[str, Any]]
    blocked_reasons: list[str]
    instruction_boundary: str | None = None


class CrmImportResponse(ApiModel):
    import_id: UUID
    dedupe_preview: list[dict[str, Any]]
    validation_summary: dict[str, int]
    row_reports: list[dict[str, Any]] = Field(default_factory=list)
    status: str = "processing"
    replayed: bool = False


class CrmAccountMergeResponse(ApiModel):
    source_id: UUID
    target_id: UUID
    references: dict[str, int]


class LeadListResponse(ApiModel):
    items: list[Lead]
    counters: dict[str, int]
    next_cursor: str | None = None


class LeadDetailResponse(ApiModel):
    lead: Lead
    timeline: list[dict[str, Any]]
    signals: list[dict[str, Any]]
    suggestions: list[dict[str, Any]]


class OpportunityStageResponse(ApiModel):
    opportunity: Opportunity
    board_summary: dict[str, Any]
    audit_entry: dict[str, Any]


class CampaignListResponse(ApiModel):
    campaigns: list[Campaign]
    counters: dict[str, int]
    next_cursor: str | None = None


class ContentAssetResponse(ApiModel):
    asset: ContentAsset | None = None
    assets: list[ContentAsset] = Field(default_factory=list)
    approvals: list[dict[str, Any]]
    version_history: list[dict[str, Any]]
    replayed: bool = False


class PublicationRetryResponse(ApiModel):
    publication: dict[str, Any]
    provider_attempt: dict[str, Any]
    preserved_payload: dict[str, Any]
    replayed: bool = False
