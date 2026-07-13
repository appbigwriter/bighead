from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from bighead_api.administration.models import AuditPage, ExperimentPage
from bighead_api.administration.routes import repository, router
from bighead_api.administration.service import _validate_period
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
        self, user_id: UUID, organization_id: UUID, view: str, start: datetime, end: datetime
    ) -> dict[str, Any]:
        return {"view": view, "start": start, "end": end}

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

    async def integrations(self, user_id: UUID, organization_id: UUID) -> dict[str, Any]:
        return {"integrations": [], "webhooks": [], "deliveryHealth": {"pending": 0}}

    async def audit_events(
        self, user_id: UUID, organization_id: UUID, resource_type: str | None, actor_id: UUID | None
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
    assert client.get("/v1/integrations").json()["deliveryHealth"] == {"pending": 0}
    audit = client.get("/v1/audit/events?resourceType=organization")
    assert audit.status_code == 200 and audit.json()["events"][0]["resource_type"] == "organization"


def test_period_and_domain_validation_reject_invalid_inputs() -> None:
    import pytest
    from bighead_api.administration.models import OrganizationPatchRequest
    from fastapi import HTTPException
    from pydantic import ValidationError

    with pytest.raises(HTTPException):
        _validate_period(NOW, NOW)
    with pytest.raises(ValidationError):
        OrganizationPatchRequest(domains=["https://not-a-domain/path"], expectedUpdatedAt=NOW)
