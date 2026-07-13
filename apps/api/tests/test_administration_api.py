from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from bighead_api.administration.models import AuditPage, ExperimentPage
from bighead_api.administration.routes import repository, router
from bighead_api.administration.service import (
    _budget_report,
    _decode_cursor,
    _encode_cursor,
    _validate_period,
    _validate_timezone,
)
from bighead_api.identity.dependencies import TenantContext, tenant_context
from bighead_api.identity.models import AuthUser, MemberRole, Membership
from fastapi import FastAPI
from fastapi.testclient import TestClient

USER_ID = UUID("10000000-0000-0000-0000-000000000001")
ORG_ID = UUID("20000000-0000-0000-0000-000000000001")
OTHER_ORG_ID = UUID("20000000-0000-0000-0000-000000000002")
RESOURCE_ID = UUID("30000000-0000-0000-0000-000000000001")
NOW = datetime.now(UTC)


class FakeRepository:
    async def experiments(self, user_id: UUID, organization_id: UUID) -> ExperimentPage:
        return ExperimentPage(items=[{"id": RESOURCE_ID, "status": "draft"}], counters={"draft": 1})

    async def experiment(
        self, user_id: UUID, organization_id: UUID, experiment_id: UUID
    ) -> dict[str, Any]:
        return {
            "experiment": {"id": experiment_id, "status": "draft"},
            "variants": [],
            "immutableFields": [],
        }

    async def patch_experiment(
        self, user_id: UUID, organization_id: UUID, experiment_id: UUID, payload: Any
    ) -> dict[str, Any]:
        return {
            "experiment": {"id": experiment_id, "hypothesis": payload.hypothesis},
            "variants": [],
            "immutableFields": [],
        }

    async def analytics(
        self,
        user_id: UUID,
        organization_id: UUID,
        view: str,
        start: datetime,
        end: datetime,
        timezone: str | None,
        filters: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "view": view,
            "start": start,
            "end": end,
            "timezone": timezone,
            "filters": filters,
        }

    async def organization(self, user_id: UUID, organization_id: UUID) -> dict[str, Any]:
        return {"organization": {"id": organization_id}, "brandingPreview": {}, "validation": []}

    async def patch_organization(
        self, user_id: UUID, organization_id: UUID, payload: Any
    ) -> dict[str, Any]:
        return {
            "organization": {"id": organization_id, "timezone": payload.timezone},
            "brandingPreview": payload.branding or {},
            "validation": [],
        }

    async def integrations(
        self,
        user_id: UUID,
        organization_id: UUID,
        provider: str | None,
        status: str,
    ) -> dict[str, Any]:
        return {
            "integrations": [],
            "webhooks": [],
            "deliveryHealth": {"pending": 0},
            "filters": {"provider": provider, "status": status},
        }

    async def audit_events(
        self,
        user_id: UUID,
        organization_id: UUID,
        resource_type: str | None,
        actor_id: UUID | None,
        cursor: str | None,
        legal_hold: bool | None,
        limit: int,
    ) -> AuditPage:
        return AuditPage(
            events=[
                {
                    "action": "organization.updated",
                    "resource_type": resource_type,
                    "actor_id": actor_id,
                }
            ]
        )


def make_client(role: MemberRole = MemberRole.OWNER) -> TestClient:
    app = FastAPI()
    app.include_router(router)

    async def context() -> TenantContext:
        return TenantContext(
            user=AuthUser(id=USER_ID, email="owner@example.com"),
            token="token",
            membership=Membership(
                id="member", organization_id=ORG_ID, user_id=USER_ID, role=role, status="active"
            ),
        )

    app.dependency_overrides[tenant_context] = context
    app.dependency_overrides[repository] = FakeRepository
    return TestClient(app)


def test_t46_t47_experiment_list_detail_and_optimistic_patch_contract() -> None:
    client = make_client(role=MemberRole.ANALYST)
    assert client.get("/v1/experiments").json()["counters"] == {"draft": 1}
    assert client.get(f"/v1/experiments/{RESOURCE_ID}").status_code == 200
    response = client.patch(
        f"/v1/experiments/{RESOURCE_ID}",
        json={
            "hypothesis": "New hypothesis",
            "expectedUpdatedAt": NOW.isoformat(),
            "variants": [{"name": "A", "weight": 1}],
        },
    )
    assert response.status_code == 200
    assert response.json()["experiment"]["hypothesis"] == "New hypothesis"


def test_t48_t52_analytics_views_enforce_roles() -> None:
    assert (
        make_client(role=MemberRole.ANALYST).get("/v1/analytics/summary").json()["view"]
        == "summary"
    )
    assert (
        make_client(role=MemberRole.MANAGER).get("/v1/analytics/operations").json()["view"]
        == "operations"
    )
    admin = make_client(role=MemberRole.ADMIN)
    assert admin.get("/v1/analytics/agents").json()["view"] == "agents"
    assert admin.get("/v1/analytics/costs").json()["view"] == "costs"
    assert (
        make_client(role=MemberRole.ANALYST).get("/v1/analytics/funnel").json()["view"] == "funnel"
    )
    assert make_client(role=MemberRole.MEMBER).get("/v1/analytics/costs").status_code == 403
    assert make_client(role=MemberRole.MEMBER).get("/v1/analytics/summary").status_code == 403


def test_t48_t52_analytics_filters_are_typed_and_forwarded() -> None:
    analyst = make_client(role=MemberRole.ANALYST)
    summary = analyst.get(
        "/v1/analytics/summary?timezone=America%2FSao_Paulo&cards=done&cards=failed"
    ).json()
    assert summary["timezone"] == "America/Sao_Paulo"
    assert summary["filters"] == {"cards": ["done", "failed"]}

    operations = make_client(role=MemberRole.MANAGER).get(
        f"/v1/analytics/operations?teamIds={USER_ID}&compareTo=previous_period"
    ).json()
    assert operations["filters"] == {
        "team_ids": [str(USER_ID)],
        "compare_to": "previous_period",
    }

    admin = make_client(role=MemberRole.ADMIN)
    agents = admin.get(
        f"/v1/analytics/agents?provider=openai&modelId={RESOURCE_ID}"
    ).json()
    assert agents["filters"] == {"provider": "openai", "model_id": str(RESOURCE_ID)}
    assert admin.get("/v1/analytics/costs?groupBy=invalid").status_code == 422
    assert (
        admin.get(f"/v1/analytics/costs?organizationId={OTHER_ORG_ID}").status_code
        == 403
    )
    funnel = analyst.get(
        f"/v1/analytics/funnel?attributionModel=linear&campaignIds={RESOURCE_ID}"
    ).json()
    assert funnel["filters"] == {
        "attribution_model": "linear",
        "campaign_ids": [str(RESOURCE_ID)],
    }


def test_t53_t56_administration_tenant_boundary_integrations_and_audit() -> None:
    client = make_client()
    assert client.get(f"/v1/organizations/{ORG_ID}").status_code == 200
    assert client.get(f"/v1/organizations/{OTHER_ORG_ID}").status_code == 403
    patched = client.patch(
        f"/v1/organizations/{ORG_ID}",
        json={
            "timezone": "UTC",
            "domains": ["example.com"],
            "expectedUpdatedAt": NOW.isoformat(),
        },
    )
    assert patched.status_code == 200 and patched.json()["organization"]["timezone"] == "UTC"
    integrations = client.get("/v1/integrations?provider=webhook&status=degraded").json()
    assert integrations["deliveryHealth"] == {"pending": 0}
    assert integrations["filters"] == {"provider": "webhook", "status": "degraded"}
    audit = client.get("/v1/audit/events?resourceType=organization")
    assert audit.status_code == 200 and audit.json()["events"][0]["resource_type"] == "organization"


def test_period_and_domain_validation_reject_invalid_inputs() -> None:
    import pytest
    from bighead_api.administration.models import OrganizationPatchRequest
    from fastapi import HTTPException
    from pydantic import ValidationError

    with pytest.raises(HTTPException):
        _validate_period(NOW, NOW)
    with pytest.raises(HTTPException):
        _validate_period(NOW.replace(tzinfo=None), NOW)
    with pytest.raises(HTTPException):
        _validate_timezone("Mars/Olympus_Mons")
    with pytest.raises(ValidationError):
        OrganizationPatchRequest(domains=["https://not-a-domain/path"], expectedUpdatedAt=NOW)


def test_t51_budget_threshold_and_blocking_policy_are_computed_from_tenant_settings() -> None:
    from decimal import Decimal

    usage, alerts = _budget_report(
        {"budgets": {"limit": "100", "currency": "USD", "exceededAction": "block"}},
        Decimal("125.50"),
    )
    assert usage[0]["usageRatio"] == Decimal("1.255")
    assert usage[0]["remaining"] == 0
    assert alerts[0]["blocking"] is True
    assert alerts[0]["code"] == "budget_exceeded"


def test_t56_audit_cursor_round_trip_and_tampering_rejection() -> None:
    import pytest
    from fastapi import HTTPException

    cursor = _encode_cursor(NOW, 42)
    created_at, event_id = _decode_cursor(cursor)
    assert created_at == NOW
    assert event_id == 42
    with pytest.raises(HTTPException):
        _decode_cursor("not-a-cursor")
