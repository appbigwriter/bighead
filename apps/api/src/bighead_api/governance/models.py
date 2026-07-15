import re
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, field_validator

from bighead_api.identity.models import ApiModel


class Page(ApiModel):
    items: list[dict[str, Any]]
    counters: dict[str, int] = Field(default_factory=dict)
    next_cursor: str | None = None


class ApprovalDecisionRequest(ApiModel):
    decision: Literal["approved", "changes_requested", "rejected"]
    comment: str | None = Field(default=None, max_length=10_000)
    expected_round: int = Field(ge=1)


class ApprovalDecisionResponse(ApiModel):
    approval: dict[str, Any]
    round_result: str
    next_actions: list[str]


class ApprovalDetailResponse(ApiModel):
    approval: dict[str, Any]
    task: dict[str, Any]
    requester: dict[str, Any]
    assignee: dict[str, Any] | None = None
    artifact: dict[str, Any] | None = None
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    impact: dict[str, Any]
    available_actions: list[str] = Field(default_factory=list)
    decision_blocked_reason: str | None = None


class ApprovalDecisionHistoryResponse(ApiModel):
    items: list[dict[str, Any]]
    next_cursor: str | None = None


class PortalDecisionRequest(ApiModel):
    decision: Literal["approved", "changes_requested", "rejected"]
    comment: str | None = Field(default=None, max_length=10_000)
    expected_round: int = Field(ge=1)


class ApprovalPolicyPatchRequest(ApiModel):
    rules: list[dict[str, Any]]
    segregation: bool = True
    thresholds: dict[str, Any] = Field(default_factory=dict)
    expected_version: int = Field(ge=0)


class ApprovalPolicyResponse(ApiModel):
    policy: dict[str, Any]
    simulation: dict[str, Any]
    coverage: dict[str, Any]


class AgentPatchRequest(ApiModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=2_000)
    risk_level: Literal["low", "medium", "high", "critical"] | None = None
    is_enabled: bool | None = None
    prompt: str | None = Field(default=None, min_length=1, max_length=100_000)
    model_id: UUID | None = None
    limits: dict[str, Any] = Field(default_factory=dict)
    skill_ids: list[UUID] | None = None
    expected_version: int = Field(ge=0)


class AgentCreateRequest(ApiModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=2_000)
    risk_level: Literal["low", "medium", "high", "critical"] = "medium"
    prompt: str = Field(min_length=1, max_length=100_000)
    model_id: UUID | None = None
    limits: dict[str, Any] = Field(default_factory=dict)
    skill_ids: list[UUID] = Field(default_factory=list)

    @field_validator("slug")
    @classmethod
    def normalize_slug(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", normalized):
            raise ValueError("Slug must use lowercase letters, numbers, and hyphens")
        return normalized


class AgentDetailResponse(ApiModel):
    agent: dict[str, Any]
    versions: list[dict[str, Any]] = Field(default_factory=list)
    consumers: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=100)


class SkillValidateRequest(ApiModel):
    payload: dict[str, Any]
    timeout_ms: int = Field(default=30_000, ge=1, le=3_600_000)
    retries: int = Field(default=0, ge=0, le=10)


class SkillValidateResponse(ApiModel):
    run_id: UUID
    status: Literal["accepted", "rejected"]
    findings: list[str]
    redactions: list[str]


class WorkflowValidateRequest(ApiModel):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    version: int = Field(ge=1)


class WorkflowValidateResponse(ApiModel):
    valid: bool
    warnings: list[str]
    cycles: list[str]
    schema_errors: list[str]


class PlaybookInstantiateRequest(ApiModel):
    context: dict[str, Any]
    owner_id: UUID | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)

    @field_validator("context", "parameters")
    @classmethod
    def limit_payload(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(str(value)) > 100_000:
            raise ValueError("Payload is too large")
        return value


class WorkflowRollbackRequest(ApiModel):
    target_version: int = Field(ge=1)
    expected_latest_version: int = Field(ge=1)


class PlaybookInstantiateResponse(ApiModel):
    task_id: UUID
    workflow_instance_id: UUID
    summary: dict[str, Any]
    replayed: bool = False
