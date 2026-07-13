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
    description: str | None = Field(default=None, max_length=2_000)
    is_enabled: bool | None = None
    prompt: str | None = Field(default=None, min_length=1, max_length=100_000)
    model_id: UUID | None = None
    limits: dict[str, Any] = Field(default_factory=dict)
    skill_ids: list[UUID] | None = None
    expected_version: int = Field(ge=0)


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
