from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, field_validator

from bighead_api.identity.models import ApiModel


class ExperimentPatchRequest(ApiModel):
    hypothesis: str | None = Field(default=None, min_length=1, max_length=10_000)
    variants: list[ExperimentVariantInput] | None = None
    stop_rule: dict[str, Any] | None = None
    window: dict[str, datetime | None] | None = None
    expected_updated_at: datetime


class ExperimentStartRequest(ApiModel):
    expected_updated_at: datetime


class ExperimentVariantInput(ApiModel):
    name: str = Field(min_length=1, max_length=160)
    content_asset_id: UUID | None = None
    weight: float = Field(gt=0, le=1)
    configuration: dict[str, Any] = Field(default_factory=dict)


class OrganizationPatchRequest(ApiModel):
    branding: dict[str, Any] | None = None
    domains: list[str] | None = Field(default=None, max_length=50)
    defaults: dict[str, Any] | None = None
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    expected_updated_at: datetime

    @field_validator("domains")
    @classmethod
    def valid_domains(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and any(
            not domain or len(domain) > 253 or "." not in domain or "/" in domain
            for domain in value
        ):
            raise ValueError("domains must be DNS names")
        return value


class ExperimentPage(ApiModel):
    items: list[dict[str, Any]]
    counters: dict[str, int]
    next_cursor: str | None = None


class AuditPage(ApiModel):
    events: list[dict[str, Any]]
    privacy_jobs: list[dict[str, Any]] = Field(default_factory=list)
    next_cursor: str | None = None


class PrivacyRequestCreateRequest(ApiModel):
    subject_user_id: UUID
    request_type: Literal["export", "anonymize", "delete"]


class LegalHoldCreateRequest(ApiModel):
    subject_user_id: UUID
    reason: str = Field(min_length=3, max_length=2_000)


class RetentionPolicyRequest(ApiModel):
    audit_days: int = Field(ge=365, le=36500)
    analytics_days: int = Field(ge=30, le=36500)


AnalyticsView = Literal["summary", "operations", "agents", "costs", "funnel"]
AttributionModel = Literal["first_touch", "last_touch", "linear"]
CostGroup = Literal["currency", "provider", "model", "agent", "day"]
IntegrationStatus = Literal["all", "enabled", "disabled", "degraded"]


class PeriodQuery(ApiModel):
    start: datetime
    end: datetime

    @field_validator("end")
    @classmethod
    def sensible_end(cls, value: datetime) -> datetime:
        return value
