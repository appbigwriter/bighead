from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from bighead_api.commercial.models import (
    ContentAssetCreateRequest,
    CrmImportRequest,
    KnowledgeUploadRequest,
    OpportunityStageRequest,
    PublicationRetryRequest,
    SemanticSearchRequest,
)
from bighead_api.commercial.routes import repository, router
from bighead_api.identity.dependencies import TenantContext, tenant_context
from bighead_api.identity.models import AuthUser, MemberRole, Membership
from fastapi import FastAPI
from fastapi.testclient import TestClient

USER_ID = UUID("10000000-0000-0000-0000-000000000001")
ORG_ID = UUID("20000000-0000-0000-0000-000000000001")
RESOURCE_ID = UUID("30000000-0000-0000-0000-000000000001")
NOW = datetime.now(UTC).isoformat()


class FakeRepository:
    def __init__(self) -> None:
        self.keys: set[str] = set()
        self.calls: list[str] = []

    async def documents(
        self,
        user_id: UUID,
        organization_id: UUID,
        status: str | None,
        classification: str | None,
        limit: int,
    ) -> dict[str, Any]:
        return {
            "documents": [
                {
                    "id": str(RESOURCE_ID),
                    "title": "Policy",
                    "sourceType": "upload",
                    "sourceUri": "artifact.pdf",
                    "classification": "medium",
                    "status": status or "approved",
                    "metadata": {},
                    "createdAt": NOW,
                }
            ],
            "counters": {"total": 1},
            "nextCursor": None,
        }

    async def upload_document(
        self,
        user_id: UUID,
        organization_id: UUID,
        payload: KnowledgeUploadRequest,
        idempotency_key: str,
    ) -> dict[str, Any]:
        replayed = bool(idempotency_key and idempotency_key in self.keys)
        if idempotency_key:
            self.keys.add(idempotency_key)
        return {
            "documentId": str(RESOURCE_ID),
            "jobId": str(RESOURCE_ID),
            "chunkPlan": {"status": "queued"},
            "replayed": replayed,
        }

    async def memory_items(
        self, user_id: UUID, organization_id: UUID, kind: str | None, status: str | None, limit: int
    ) -> dict[str, Any]:
        return {
            "items": [
                {
                    "id": str(RESOURCE_ID),
                    "kind": kind or "fact",
                    "content": "Renew annually",
                    "source": {"documentId": str(RESOURCE_ID)},
                    "confidence": 90,
                    "status": status or "approved",
                    "createdAt": NOW,
                }
            ],
            "sources": [{"documentId": str(RESOURCE_ID)}],
            "nextCursor": None,
        }

    async def semantic_search(
        self,
        user_id: UUID,
        organization_id: UUID,
        role: MemberRole,
        payload: SemanticSearchRequest,
    ) -> dict[str, Any]:
        return {
            "results": [{"score": 0.9, "source": {"documentId": str(RESOURCE_ID)}}],
            "retrievalTrace": [],
            "blockedReasons": [],
        }

    async def crm_import(
        self,
        user_id: UUID,
        organization_id: UUID,
        role: MemberRole,
        payload: CrmImportRequest,
        idempotency_key: str,
    ) -> dict[str, Any]:
        self.calls.append(role.value)
        return {
            "importId": str(RESOURCE_ID),
            "dedupePreview": [{"action": "create"}],
            "validationSummary": {"total": 1, "accepted": 1, "rejected": 0},
            "rowReports": [{"row": 0, "action": "create"}],
            "status": "completed",
        }

    async def resume_crm_import(
        self,
        user_id: UUID,
        organization_id: UUID,
        role: MemberRole,
        import_id: UUID,
        payload: Any,
    ) -> dict[str, Any]:
        self.calls.append("resume")
        return {
            "importId": str(import_id),
            "dedupePreview": [{"action": "create"}],
            "rowReports": [{"row": 1, "action": "create"}],
            "validationSummary": {"total": 2, "accepted": 2, "rejected": 0},
            "status": "completed",
        }

    async def merge_crm_accounts(
        self,
        user_id: UUID,
        organization_id: UUID,
        role: MemberRole,
        source_id: UUID,
        target_id: UUID,
        reason: str,
    ) -> dict[str, Any]:
        self.calls.append(reason)
        return {
            "sourceId": source_id,
            "targetId": target_id,
            "references": {"contacts": 1, "leads": 1, "opportunities": 1},
        }

    async def leads(
        self,
        user_id: UUID,
        organization_id: UUID,
        status: str | None,
        owner_id: UUID | None,
        limit: int,
    ) -> dict[str, Any]:
        return {
            "items": [
                {
                    "id": str(RESOURCE_ID),
                    "status": status or "qualified",
                    "ownerUserId": str(USER_ID),
                    "source": "import",
                    "icpScore": 80,
                    "scoreFactors": {},
                    "scoreAlgorithmVersion": "icp-v2.1",
                    "createdAt": NOW,
                }
            ],
            "counters": {"total": 1},
            "nextCursor": None,
        }

    async def lead(self, user_id: UUID, organization_id: UUID, lead_id: UUID) -> dict[str, Any]:
        return {
            "lead": {
                "id": str(lead_id),
                "status": "qualified",
                "ownerUserId": str(USER_ID),
                "source": "import",
                "icpScore": 80,
                "scoreFactors": {},
                "scoreAlgorithmVersion": "icp-v2.1",
                "createdAt": NOW,
            },
            "timeline": [],
            "signals": [],
            "suggestions": [],
        }

    async def opportunity_stage(
        self,
        user_id: UUID,
        organization_id: UUID,
        role: MemberRole,
        opportunity_id: UUID,
        payload: OpportunityStageRequest,
    ) -> dict[str, Any]:
        self.calls.append(role.value)
        return {
            "opportunity": {
                "id": str(opportunity_id),
                "name": "Atlas renewal",
                "stage": payload.target_stage,
                "currency": "BRL",
            },
            "boardSummary": {"movedTo": payload.target_stage},
            "auditEntry": {"actorUserId": str(user_id)},
        }

    async def pipeline(self, user_id: UUID, organization_id: UUID) -> dict[str, Any]:
        return {
            "stages": [
                {
                    "id": "proposal",
                    "label": "Proposta",
                    "opportunities": [
                        {
                            "id": str(RESOURCE_ID),
                            "leadId": str(RESOURCE_ID),
                            "name": "Atlas renewal",
                            "stage": "proposal",
                            "amount": 1000,
                            "currency": "BRL",
                            "updatedAt": NOW,
                        }
                    ],
                    "count": 1,
                    "amount": 1000,
                }
            ],
            "totals": {"opportunities": 1, "amount": 1000},
        }

    async def create_lead_follow_up(
        self,
        user_id: UUID,
        organization_id: UUID,
        lead_id: UUID,
        payload: Any,
        idempotency_key: str,
    ) -> dict[str, Any]:
        replayed = idempotency_key in self.keys
        self.keys.add(idempotency_key)
        return {
            "lead": {
                "id": str(lead_id),
                "status": "qualified",
                "ownerUserId": str(user_id),
                "source": "import",
                "icpScore": 80,
                "scoreFactors": {},
                "scoreAlgorithmVersion": "icp-v2.1",
                "nextAction": payload.action,
                "nextActionAt": payload.due_at,
                "createdAt": NOW,
            },
            "timelineItem": {
                "type": "follow_up",
                "action": payload.action,
                "dueAt": payload.due_at,
                "actorUserId": str(user_id),
                "createdAt": NOW,
            },
            "replayed": replayed,
        }

    async def campaigns(
        self,
        user_id: UUID,
        organization_id: UUID,
        status: str | None,
        channel: str | None,
        limit: int,
    ) -> dict[str, Any]:
        return {
            "campaigns": [
                {
                    "id": str(RESOURCE_ID),
                    "name": "Launch",
                    "status": status or "active",
                    "createdAt": NOW,
                }
            ],
            "counters": {"total": 1},
            "nextCursor": None,
        }

    async def content_assets(
        self, user_id: UUID, organization_id: UUID, limit: int
    ) -> dict[str, Any]:
        return {
            "assets": [
                {
                    "id": str(RESOURCE_ID),
                    "title": "Launch",
                    "contentType": "multichannel",
                    "status": "draft",
                    "body": {},
                    "createdAt": NOW,
                    "updatedAt": NOW,
                }
            ],
            "approvals": [],
            "versionHistory": [],
        }

    async def create_content_asset(
        self,
        user_id: UUID,
        organization_id: UUID,
        payload: ContentAssetCreateRequest,
        idempotency_key: str,
    ) -> dict[str, Any]:
        replayed = bool(idempotency_key and idempotency_key in self.keys)
        if idempotency_key:
            self.keys.add(idempotency_key)
        return {
            "asset": {
                "id": str(RESOURCE_ID),
                "title": payload.title or payload.brief,
                "contentType": "multichannel",
                "status": "draft",
                "body": {"versions": [{"version": 1}]},
                "channel": payload.channels[0],
                "createdAt": NOW,
                "updatedAt": NOW,
            },
            "approvals": [],
            "versionHistory": [{"version": 1}],
            "replayed": replayed,
        }

    async def retry_publication(
        self,
        user_id: UUID,
        organization_id: UUID,
        asset_id: UUID,
        payload: PublicationRetryRequest,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return {
            "publication": {"id": str(asset_id), "status": "scheduled", "channel": payload.channel},
            "providerAttempt": {"status": "queued"},
            "preservedPayload": {"body": "original"},
        }


def make_client(
    role: MemberRole = MemberRole.MANAGER, repo: FakeRepository | None = None
) -> TestClient:
    selected = repo or FakeRepository()
    app = FastAPI()
    app.include_router(router)

    async def context() -> TenantContext:
        return TenantContext(
            user=AuthUser(id=USER_ID, email="manager@example.com"),
            token="token",
            membership=Membership(
                id="membership", organization_id=ORG_ID, user_id=USER_ID, role=role, status="active"
            ),
        )

    app.dependency_overrides[tenant_context] = context
    app.dependency_overrides[repository] = lambda: selected
    return TestClient(app)


def test_t35_t38_knowledge_memory_and_search_contracts() -> None:
    client = make_client()
    assert (
        client.get("/v1/knowledge/documents?status=approved").json()["documents"][0]["status"]
        == "approved"
    )
    upload = client.post(
        "/v1/knowledge/documents",
        headers={"Idempotency-Key": "knowledge-1"},
        json={"fileRef": str(RESOURCE_ID), "classification": "high", "visibility": "tenant"},
    )
    assert upload.status_code == 202 and upload.json()["chunkPlan"]["status"] == "queued"
    assert client.get("/v1/memory/items?type=fact&status=approved").json()["sources"]
    search = client.post(
        "/v1/search/semantic",
        json={"query": "renewal policy", "topK": 5, "filters": {"embedding": [0] * 1536}},
    )
    assert search.status_code == 200 and search.headers["cache-control"] == "no-store"
    assert search.json()["results"][0]["source"]


def test_t39_import_forwards_role_and_dedupe_preview() -> None:
    repo = FakeRepository()
    response = make_client(MemberRole.ANALYST, repo).post(
        "/v1/crm/imports",
        headers={"Idempotency-Key": "import-1"},
        json={
            "source": "csv",
            "rows": [{"accountName": "Atlas", "consentStatus": "granted"}],
            "consentBasis": "legitimate_interest",
        },
    )
    assert response.status_code == 202
    assert response.json()["dedupePreview"][0]["action"] == "create"
    assert repo.calls == ["analyst"]


def test_t39_failed_rows_resume_and_account_merge_contracts() -> None:
    repo = FakeRepository()
    client = make_client(MemberRole.MANAGER, repo)
    resumed = client.post(
        f"/v1/crm/imports/{RESOURCE_ID}/resume",
        json={
            "rows": [
                {"rowNumber": 1, "payload": {"accountName": "Atlas", "consentStatus": "granted"}}
            ]
        },
    )
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "completed"
    merged = client.post(
        f"/v1/crm/accounts/{RESOURCE_ID}/merge",
        json={"targetAccountId": str(ORG_ID), "reason": "same legal entity"},
    )
    assert merged.status_code == 200
    assert merged.json()["references"]["leads"] == 1
    assert repo.calls == ["resume", "same legal entity"]


def test_t40_t42_leads_detail_and_pipeline_contracts() -> None:
    client = make_client()
    assert client.get("/v1/crm/leads?stage=qualified").json()["items"][0]["status"] == "qualified"
    assert client.get(f"/v1/crm/leads/{RESOURCE_ID}").json()["lead"]["id"] == str(RESOURCE_ID)
    moved = client.post(
        f"/v1/crm/opportunities/{RESOURCE_ID}/stage",
        json={
            "targetStage": "proposal",
            "requiredFields": {"amount": 1000},
            "forecast": {"probability": 60},
        },
    )
    assert moved.status_code == 200 and moved.json()["auditEntry"]


def test_t42_required_fields_are_defined_by_the_server() -> None:
    request = OpportunityStageRequest(
        targetStage="won",
        amount="1000.50",
        probability="100",
        requiredFields={"amount": "untrusted compatibility field"},
    )
    assert str(request.amount) == "1000.50"
    assert str(request.probability) == "100"


def test_pipeline_board_and_idempotent_follow_up_contracts() -> None:
    repo = FakeRepository()
    client = make_client(repo=repo)
    board = client.get("/v1/crm/pipeline")
    assert board.status_code == 200
    assert board.json()["stages"][0]["opportunities"][0]["id"] == str(RESOURCE_ID)
    payload = {"action": "Ligar para o decisor", "dueAt": NOW, "notes": "Confirmar prazo"}
    created = client.post(
        f"/v1/crm/leads/{RESOURCE_ID}/follow-ups",
        headers={"Idempotency-Key": "follow-up-1"},
        json=payload,
    )
    replayed = client.post(
        f"/v1/crm/leads/{RESOURCE_ID}/follow-ups",
        headers={"Idempotency-Key": "follow-up-1"},
        json=payload,
    )
    assert created.status_code == 201
    assert created.json()["timelineItem"]["type"] == "follow_up"
    assert replayed.json()["replayed"] is True


def test_follow_up_requires_idempotency_key() -> None:
    response = make_client().post(
        f"/v1/crm/leads/{RESOURCE_ID}/follow-ups",
        json={"action": "Ligar", "dueAt": NOW},
    )
    assert response.status_code == 422


def test_t43_t45_campaign_asset_and_publication_contracts() -> None:
    repo = FakeRepository()
    client = make_client(repo=repo)
    assert client.get("/v1/content/campaigns?status=active").json()["campaigns"]
    assert client.get("/v1/content/assets").json()["assets"]
    created = client.post(
        "/v1/content/assets",
        headers={"Idempotency-Key": "asset-1"},
        json={"brief": "Launch", "channels": ["linkedin"], "variants": [{"name": "A"}]},
    )
    replayed = client.post(
        "/v1/content/assets",
        headers={"Idempotency-Key": "asset-1"},
        json={"brief": "Launch", "channels": ["linkedin"], "variants": [{"name": "A"}]},
    )
    assert created.status_code == 201 and replayed.json()["replayed"] is True
    retried = client.post(
        f"/v1/content/publications/{RESOURCE_ID}/retry",
        headers={"Idempotency-Key": "retry-1"},
        json={"channel": "linkedin", "reason": "provider recovered"},
    )
    assert retried.status_code == 200 and retried.json()["preservedPayload"] == {"body": "original"}


def test_invalid_idempotency_key_is_rejected_before_repository() -> None:
    response = make_client().post(
        "/v1/content/assets",
        headers={"Idempotency-Key": " "},
        json={"brief": "Launch", "channels": ["email"]},
    )
    assert response.status_code == 422


def test_async_commands_require_idempotency_key() -> None:
    client = make_client()
    assert (
        client.post(
            "/v1/knowledge/documents",
            json={"fileRef": str(RESOURCE_ID), "classification": "medium", "visibility": "tenant"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/v1/crm/imports",
            json={"source": "csv", "rows": [{"accountName": "Atlas"}], "consentBasis": "contract"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/v1/content/assets", json={"brief": "Launch", "channels": ["email"]}
        ).status_code
        == 422
    )


def test_t36_rejects_invalid_classification() -> None:
    response = make_client().post(
        "/v1/knowledge/documents",
        json={"fileRef": str(RESOURCE_ID), "classification": "secret", "visibility": "tenant"},
    )
    assert response.status_code == 422
