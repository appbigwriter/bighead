from datetime import datetime
from typing import Any
from uuid import UUID

from bighead_api.governance.models import (
    ApprovalDecisionHistoryResponse,
    ApprovalDecisionResponse,
    ApprovalDetailResponse,
    ApprovalPolicyResponse,
    Page,
    PlaybookInstantiateResponse,
    SkillValidateResponse,
)
from bighead_api.governance.routes import repository, router
from bighead_api.identity.dependencies import TenantContext, tenant_context
from bighead_api.identity.models import AuthUser, MemberRole, Membership
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

USER_ID = UUID("10000000-0000-0000-0000-000000000001")
ORG_ID = UUID("20000000-0000-0000-0000-000000000001")
RESOURCE_ID = UUID("30000000-0000-0000-0000-000000000001")
RUN_ID = UUID("40000000-0000-0000-0000-000000000001")


class FakeRepository:
    def __init__(self) -> None:
        self.keys: set[str] = set()

    async def list_approvals(
        self,
        user_id: UUID,
        organization_id: UUID,
        queue: str,
        risk: str | None,
        due_before: datetime | None,
        limit: int,
    ) -> Page:
        assert queue in {"pending", "overdue", "decided", "all"}
        assert limit <= 100
        return Page(items=[{"id": RESOURCE_ID, "status": "pending"}], counters={"pending": 1})

    async def approval_detail(
        self, user_id: UUID, organization_id: UUID, approval_id: UUID
    ) -> ApprovalDetailResponse:
        return ApprovalDetailResponse(
            approval={"id": approval_id, "status": "pending", "round": 1},
            task={"id": RESOURCE_ID, "title": "Review campaign"},
            requester={"id": USER_ID},
            evidence=[{"type": "qa_evaluation", "evaluation": {"score": 98}}],
            impact={"taskStatus": "waiting_human", "activeRunCount": 1},
            available_actions=["approved", "changes_requested", "rejected"],
        )

    async def approval_decisions(
        self, user_id: UUID, organization_id: UUID, approval_id: UUID
    ) -> ApprovalDecisionHistoryResponse:
        return ApprovalDecisionHistoryResponse(
            items=[
                {
                    "id": RESOURCE_ID,
                    "decision": "approved",
                    "actor": {"type": "user", "id": USER_ID},
                    "decidedAt": "2026-07-13T12:00:00Z",
                }
            ]
        )

    async def decide(
        self, user_id: UUID, organization_id: UUID, approval_id: UUID, payload: Any
    ) -> ApprovalDecisionResponse:
        return ApprovalDecisionResponse(
            approval={"id": approval_id, "status": payload.decision},
            round_result=payload.decision,
            next_actions=["resume_task"],
        )

    async def scorecard(
        self, user_id: UUID, organization_id: UUID, approval_id: UUID
    ) -> dict[str, Any]:
        return {"scores": [{"score": 98}], "policyFindings": [], "trend": []}

    async def get_policy(self, user_id: UUID, organization_id: UUID) -> ApprovalPolicyResponse:
        return ApprovalPolicyResponse(policy={"version": 1}, simulation={}, coverage={})

    async def patch_policy(
        self, user_id: UUID, organization_id: UUID, payload: Any
    ) -> ApprovalPolicyResponse:
        return ApprovalPolicyResponse(
            policy={"version": payload.expected_version + 1}, simulation={}, coverage={}
        )

    async def portal_item(self, token: str) -> dict[str, Any]:
        return {
            "item": {"token": token},
            "allowedActions": ["approve"],
            "portalBranding": {},
            "state": "pending",
        }

    async def portal_decide(self, token: str, key: str, payload: Any) -> ApprovalDecisionResponse:
        return ApprovalDecisionResponse(
            approval={"token": token, "status": payload.decision},
            round_result=payload.decision,
            next_actions=["resume_task"],
        )

    async def list_agents(self, user_id: UUID, organization_id: UUID) -> Page:
        return Page(items=[{"id": RESOURCE_ID, "name": "Agent"}])

    async def create_agent(
        self, user_id: UUID, organization_id: UUID, payload: Any
    ) -> dict[str, Any]:
        return {
            "agent": {"id": RESOURCE_ID, "name": payload.name, "slug": payload.slug},
            "versions": [{"version": 1}],
            "confidence": 0,
        }

    async def agent_detail(
        self, user_id: UUID, organization_id: UUID, agent_id: UUID
    ) -> dict[str, Any]:
        return {"agent": {"id": agent_id}, "versions": [], "confidence": 0}

    async def patch_agent(
        self, user_id: UUID, organization_id: UUID, agent_id: UUID, payload: Any
    ) -> dict[str, Any]:
        return {
            "agent": {"id": agent_id},
            "versions": [{"version": payload.expected_version + 1}],
            "confidence": 0,
        }

    async def delete_agent(
        self, user_id: UUID, organization_id: UUID, agent_id: UUID, expected_version: int
    ) -> None:
        assert expected_version >= 1

    async def list_skills(self, user_id: UUID, organization_id: UUID) -> Page:
        return Page(items=[{"id": RESOURCE_ID, "name": "Skill"}])

    async def validate_skill(
        self, user_id: UUID, organization_id: UUID, skill_id: UUID, payload: Any
    ) -> SkillValidateResponse:
        return SkillValidateResponse(run_id=RUN_ID, status="accepted", findings=[], redactions=[])

    async def list_models(self, user_id: UUID, organization_id: UUID) -> dict[str, Any]:
        return {"providers": [], "models": [], "priceTables": []}

    async def list_prompts(self, user_id: UUID, organization_id: UUID) -> Page:
        return Page(items=[{"id": RESOURCE_ID, "version": 1}])

    async def list_workflows(self, user_id: UUID, organization_id: UUID) -> Page:
        return Page(items=[{"id": RESOURCE_ID, "name": "Workflow"}])

    async def validate_workflow(
        self, user_id: UUID, organization_id: UUID, workflow_id: UUID, payload: Any
    ) -> Any:
        from bighead_api.governance.service import validate_workflow

        return validate_workflow(payload)

    async def workflow_versions(
        self,
        user_id: UUID,
        organization_id: UUID,
        workflow_id: UUID,
        cursor: int | None,
        include_diff: bool,
    ) -> dict[str, Any]:
        return {"versions": [{"version": 1}], "diffs": [], "nextCursor": None}

    async def rollback_workflow(
        self, user_id: UUID, organization_id: UUID, workflow_id: UUID, payload: Any
    ) -> dict[str, Any]:
        return {
            "version": {"version": payload.expected_latest_version + 1},
            "rollbackTarget": payload.target_version,
            "activeRunsPreserved": True,
        }

    async def instantiate(
        self, user_id: UUID, organization_id: UUID, playbook_id: UUID, key: str, payload: Any
    ) -> PlaybookInstantiateResponse:
        replayed = key in self.keys
        self.keys.add(key)
        return PlaybookInstantiateResponse(
            task_id=RESOURCE_ID,
            workflow_instance_id=RUN_ID,
            summary={"status": "queued"},
            replayed=replayed,
        )


class SelfApprovalRepository(FakeRepository):
    async def decide(
        self, user_id: UUID, organization_id: UUID, approval_id: UUID, payload: Any
    ) -> ApprovalDecisionResponse:
        raise HTTPException(status_code=403, detail="Self-approval is prohibited")


def make_client(
    role: MemberRole = MemberRole.ADMIN, repo: FakeRepository | None = None
) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    selected = repo or FakeRepository()

    async def context() -> TenantContext:
        return TenantContext(
            user=AuthUser(id=USER_ID, email="admin@example.com"),
            token="token",
            membership=Membership(
                id="member", organization_id=ORG_ID, user_id=USER_ID, role=role, status="active"
            ),
        )

    app.dependency_overrides[tenant_context] = context
    app.dependency_overrides[repository] = lambda: selected
    return TestClient(app)


def test_t20_t24_approval_policy_scorecard_and_public_portal() -> None:
    client = make_client()
    assert client.get("/v1/approvals").json()["counters"] == {"pending": 1}
    detail = client.get(f"/v1/approvals/{RESOURCE_ID}")
    assert detail.status_code == 200
    assert detail.json()["requester"]["id"] == str(USER_ID)
    assert detail.json()["evidence"][0]["type"] == "qa_evaluation"
    assert detail.json()["impact"]["activeRunCount"] == 1
    history = client.get(f"/v1/approvals/{RESOURCE_ID}/decisions")
    assert history.status_code == 200
    assert history.json()["items"][0]["actor"]["id"] == str(USER_ID)
    assert history.json()["items"][0]["decidedAt"] == "2026-07-13T12:00:00Z"
    decision = client.post(
        f"/v1/approvals/{RESOURCE_ID}/decision", json={"decision": "approved", "expectedRound": 1}
    )
    assert decision.json()["roundResult"] == "approved"
    assert client.get(f"/v1/approvals/{RESOURCE_ID}/scorecard").json()["scores"][0]["score"] == 98
    assert (
        client.patch("/v1/policies/approvals", json={"rules": [], "expectedVersion": 1}).json()[
            "policy"
        ]["version"]
        == 2
    )
    assert client.get("/v1/portal/items/opaque-token").json()["state"] == "pending"
    external = client.post(
        "/v1/portal/items/opaque-token/decision",
        headers={"Idempotency-Key": "portal-decision-1"},
        json={"decision": "approved", "expectedRound": 1},
    )
    assert external.status_code == 200 and external.json()["roundResult"] == "approved"


def test_approval_detail_and_history_require_reviewer_role() -> None:
    client = make_client(role=MemberRole.MEMBER)

    assert client.get(f"/v1/approvals/{RESOURCE_ID}").status_code == 403
    assert client.get(f"/v1/approvals/{RESOURCE_ID}/decisions").status_code == 403


def test_self_approval_is_exposed_as_forbidden_not_conflict() -> None:
    response = make_client(repo=SelfApprovalRepository()).post(
        f"/v1/approvals/{RESOURCE_ID}/decision",
        json={"decision": "approved", "expectedRound": 1},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Self-approval is prohibited"


def test_t25_t31_catalog_endpoints_and_rbac() -> None:
    client = make_client()
    assert client.get("/v1/agents").status_code == 200
    created = client.post(
        "/v1/agents",
        json={"name": "SDR virtual", "slug": "sdr-virtual", "prompt": "Qualifique leads."},
    )
    assert created.status_code == 201 and created.json()["versions"][0]["version"] == 1
    assert (
        client.post(
            "/v1/agents", json={"name": "Bad", "slug": "invalid slug", "prompt": "x"}
        ).status_code
        == 422
    )
    assert client.get(f"/v1/agents/{RESOURCE_ID}").status_code == 200
    assert client.patch(f"/v1/agents/{RESOURCE_ID}", json={"expectedVersion": 1}).status_code == 200
    assert client.delete(f"/v1/agents/{RESOURCE_ID}?expectedVersion=1").status_code == 204
    assert client.get("/v1/skills").status_code == 200
    assert (
        client.post(f"/v1/skills/{RESOURCE_ID}/validate", json={"payload": {}}).status_code == 200
    )
    assert client.get("/v1/models").status_code == 200
    assert client.get("/v1/prompts").status_code == 200
    assert client.get("/v1/workflows").status_code == 200
    assert make_client(role=MemberRole.MEMBER).get("/v1/agents").status_code == 403


def test_t32_cycle_validation_t33_versions_and_t34_idempotency() -> None:
    client = make_client()
    cyclic = client.post(
        f"/v1/workflows/{RESOURCE_ID}/validate",
        json={
            "version": 1,
            "nodes": [{"id": "a"}, {"id": "b"}],
            "edges": [{"source": "a", "target": "b"}, {"source": "b", "target": "a"}],
        },
    )
    assert cyclic.status_code == 200 and cyclic.json()["valid"] is False
    assert client.get(f"/v1/workflows/{RESOURCE_ID}/versions").status_code == 200
    rollback = client.post(
        f"/v1/workflows/{RESOURCE_ID}/rollback",
        json={"targetVersion": 1, "expectedLatestVersion": 2},
    )
    assert rollback.status_code == 201 and rollback.json()["activeRunsPreserved"] is True
    assert (
        client.post(f"/v1/playbooks/{RESOURCE_ID}/instantiate", json={"context": {}}).status_code
        == 422
    )
    repo = FakeRepository()
    replay_client = make_client(repo=repo)
    first = replay_client.post(
        f"/v1/playbooks/{RESOURCE_ID}/instantiate",
        headers={"Idempotency-Key": "playbook-1"},
        json={"context": {}},
    )
    replay = replay_client.post(
        f"/v1/playbooks/{RESOURCE_ID}/instantiate",
        headers={"Idempotency-Key": "playbook-1"},
        json={"context": {}},
    )
    assert first.status_code == 201 and first.json()["replayed"] is False
    assert replay.status_code == 201 and replay.json()["replayed"] is True
    manager = make_client(role=MemberRole.MANAGER)
    assert (
        manager.post(
            f"/v1/workflows/{RESOURCE_ID}/validate",
            json={"version": 1, "nodes": [], "edges": []},
        ).status_code
        == 403
    )
    assert manager.get(f"/v1/workflows/{RESOURCE_ID}/versions").status_code == 403
    assert manager.get("/v1/policies/approvals").status_code == 403
