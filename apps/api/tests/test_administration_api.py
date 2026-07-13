from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from bighead_api.administration.models import AuditPage, ExperimentPage
from bighead_api.administration.routes import repository, router
from bighead_api.administration.service import (
    AnalyticsView,
    _analytics_metadata,
    _budget_report,
    _comparison_period,
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


def test_every_analytics_view_declares_metadata_and_attribution_semantics() -> None:
    views: tuple[AnalyticsView, ...] = ("summary", "operations", "agents", "costs", "funnel")
    for view in views:
        metadata = _analytics_metadata(
            view,
            NOW,
            NOW,
            "America/Sao_Paulo",
            {"attribution_model": "linear"} if view == "funnel" else {},
            NOW,
        )
        assert set(metadata) >= {
            "source",
            "period",
            "timezone",
            "freshness",
            "attributionModel",
            "attributionMethod",
        }
        assert metadata["attributionModel"] == ("linear" if view == "funnel" else "not_applicable")
    agents_source = _analytics_metadata("agents", NOW, NOW, "UTC", {}, NOW)["source"]
    costs_source = _analytics_metadata("costs", NOW, NOW, "UTC", {}, NOW)["source"]
    assert set(agents_source) >= {
        "cost_events.model_id",
        "models",
        "model_providers",
        "skills",
        "tool_calls",
    }
    assert set(costs_source) >= {
        "cost_events.model_id",
        "models",
        "model_providers",
        "tasks",
        "agents",
    }


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

    async def start_experiment(
        self,
        user_id: UUID,
        organization_id: UUID,
        experiment_id: UUID,
        expected_updated_at: datetime,
    ) -> dict[str, Any]:
        return {
            "experiment": {"id": experiment_id, "status": "running"},
            "variants": [],
            "immutableFields": ["hypothesis", "variants"],
            "replayed": False,
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
        if view == "summary":
            resolved_timezone = timezone or "UTC"
            period = {"from": start, "to": end, "boundary": "[from,to)"}
            return {
                "cards": [
                    {
                        "key": "total",
                        "value": 2,
                        "source": "tasks.created_at",
                        "period": period,
                        "timezone": resolved_timezone,
                        "freshness": NOW,
                    }
                ],
                "drilldowns": [
                    {
                        "card": "total",
                        "dimension": "done",
                        "value": 2,
                        "recordIds": [RESOURCE_ID],
                        "recordCount": 1,
                        "recordsTruncated": False,
                        "recordsEndpoint": "/v1/analytics/summary/records",
                    }
                ],
                "alerts": [],
                "source": ["tasks"],
                "period": period,
                "timezone": resolved_timezone,
                "freshness": NOW,
                "calculatedAt": NOW,
                "filters": filters,
                "reconciliation": {
                    "card": "total",
                    "cardValue": 2,
                    "drilldownValue": 2,
                    "reconciled": True,
                },
            }
        return {
            "view": view,
            "start": start,
            "end": end,
            "timezone": timezone,
            "filters": filters,
        }

    async def analytics_summary_records(
        self,
        user_id: UUID,
        organization_id: UUID,
        dimension: str,
        start: datetime,
        end: datetime,
        cursor: str | None,
        limit: int,
    ) -> dict[str, Any]:
        return {
            "items": [{"id": RESOURCE_ID, "status": dimension, "createdAt": NOW}],
            "total": 1,
            "nextCursor": None,
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

    async def create_privacy_request(
        self, user_id: UUID, organization_id: UUID, key: str, payload: Any
    ) -> dict[str, Any]:
        return {
            "request": {
                "id": RESOURCE_ID,
                "subjectUserId": payload.subject_user_id,
                "requestType": payload.request_type,
                "status": "requested",
            },
            "replayed": False,
        }

    async def privacy_requests(self, user_id: UUID, organization_id: UUID) -> dict[str, Any]:
        return {"items": [{"id": RESOURCE_ID, "status": "completed"}]}

    async def privacy_export(
        self, user_id: UUID, organization_id: UUID, request_id: UUID
    ) -> dict[str, Any]:
        return {
            "requestId": request_id,
            "downloadUrl": "https://storage.example.test/signed",
            "expiresAt": NOW,
        }

    async def create_legal_hold(
        self, user_id: UUID, organization_id: UUID, payload: Any
    ) -> dict[str, Any]:
        return {"id": RESOURCE_ID, "active": True, "reason": payload.reason}

    async def release_legal_hold(
        self, user_id: UUID, organization_id: UUID, hold_id: UUID
    ) -> dict[str, Any]:
        return {"id": hold_id, "active": False}

    async def update_retention(
        self, user_id: UUID, organization_id: UUID, payload: Any
    ) -> dict[str, Any]:
        return {"auditDays": payload.audit_days, "analyticsDays": payload.analytics_days}


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
    started = client.post(
        f"/v1/experiments/{RESOURCE_ID}/start",
        json={"expectedUpdatedAt": NOW.isoformat()},
    )
    assert started.status_code == 200
    assert started.json()["experiment"]["status"] == "running"


def test_t48_t52_analytics_views_enforce_roles() -> None:
    summary = make_client(role=MemberRole.ANALYST).get("/v1/analytics/summary").json()
    assert summary["source"] == ["tasks"]
    assert summary["reconciliation"]["reconciled"] is True
    assert summary["drilldowns"][0]["recordIds"] == [str(RESOURCE_ID)]
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
    assert make_client(role=MemberRole.ADMIN).get("/v1/analytics/summary").status_code == 403


def test_t48_t52_analytics_filters_are_typed_and_forwarded() -> None:
    analyst = make_client(role=MemberRole.ANALYST)
    summary = analyst.get(
        "/v1/analytics/summary?timezone=America%2FSao_Paulo&cards=done&cards=failed"
    ).json()
    assert summary["timezone"] == "America/Sao_Paulo"
    assert summary["filters"] == {"cards": ["done", "failed"]}
    records = analyst.get("/v1/analytics/summary/records?dimension=done&limit=1").json()
    assert records == {
        "items": [
            {
                "id": str(RESOURCE_ID),
                "status": "done",
                "createdAt": NOW.isoformat().replace("+00:00", "Z"),
            }
        ],
        "total": 1,
        "nextCursor": None,
    }

    operations = (
        make_client(role=MemberRole.MANAGER)
        .get(f"/v1/analytics/operations?teamIds={USER_ID}&compareTo=previous_period")
        .json()
    )
    assert operations["filters"] == {
        "team_ids": [str(USER_ID)],
        "compare_to": "previous_period",
    }

    admin = make_client(role=MemberRole.ADMIN)
    agents = admin.get(f"/v1/analytics/agents?provider=openai&modelId={RESOURCE_ID}").json()
    assert agents["filters"] == {"provider": "openai", "model_id": str(RESOURCE_ID)}
    assert admin.get("/v1/analytics/costs?groupBy=invalid").status_code == 422
    assert admin.get(f"/v1/analytics/costs?organizationId={OTHER_ORG_ID}").status_code == 403
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
        _validate_timezone("not a timezone!")
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

    usage, alerts = _budget_report(
        {"quotas": {"tokens": 1000, "exceededAction": "block"}},
        Decimal("0"),
        tokens=1001,
    )
    assert usage == []
    assert alerts[0]["code"] == "token_quota_exceeded"
    assert alerts[0]["blocking"] is True


def test_t49_comparison_windows_are_contiguous_and_calendar_aligned() -> None:
    start = datetime(2024, 2, 29, tzinfo=UTC)
    end = datetime(2024, 3, 31, tzinfo=UTC)
    previous_start, previous_end = _comparison_period(start, end, "previous_period")
    assert previous_end == start
    assert previous_end - previous_start == end - start
    year_start, year_end = _comparison_period(start, end, "previous_year")
    assert year_start == datetime(2023, 2, 28, tzinfo=UTC)
    assert year_end == datetime(2023, 3, 31, tzinfo=UTC)


def test_t56_audit_cursor_round_trip_and_tampering_rejection() -> None:
    import pytest
    from fastapi import HTTPException

    cursor = _encode_cursor(NOW, 42)
    created_at, event_id = _decode_cursor(cursor)
    assert created_at == NOW
    assert event_id == 42
    with pytest.raises(HTTPException):
        _decode_cursor("not-a-cursor")


def test_t56_privacy_commands_and_authorized_export_contract() -> None:
    client = make_client()
    created = client.post(
        "/v1/privacy/requests",
        headers={"Idempotency-Key": "privacy-contract-1"},
        json={"subjectUserId": str(USER_ID), "requestType": "export"},
    )
    assert created.status_code == 202 and created.json()["replayed"] is False
    assert client.get("/v1/privacy/requests").status_code == 200
    export = client.get(f"/v1/privacy/requests/{RESOURCE_ID}/export")
    assert export.status_code == 200
    assert export.json()["downloadUrl"].startswith("https://")
    hold = client.post(
        "/v1/privacy/legal-holds",
        json={"subjectUserId": str(USER_ID), "reason": "active litigation"},
    )
    assert hold.status_code == 201 and hold.json()["active"] is True
    assert client.delete(f"/v1/privacy/legal-holds/{RESOURCE_ID}").status_code == 200
    retention = client.put(
        "/v1/privacy/retention-policy",
        json={"auditDays": 2555, "analyticsDays": 730},
    )
    assert retention.status_code == 200
    assert make_client(MemberRole.MEMBER).get("/v1/privacy/requests").status_code == 403
