# ruff: noqa: ASYNC230, ASYNC240
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from bighead_api.artifacts.service import StorageGateway
from bighead_api.governance.ingestion import KnowledgeIngestionService
from bighead_api.governance.routes import router
from bighead_api.identity.dependencies import TenantContext, tenant_context
from bighead_api.identity.models import AuthUser, MemberRole, Membership
from bighead_api.identity.repository import Database
from bighead_pycore.integrations.anythingllm import AnythingLlmClient
from fastapi import FastAPI
from fastapi.testclient import TestClient

USER_ID = UUID("10000000-0000-0000-0000-000000000001")
ORG_ID = UUID("20000000-0000-0000-0000-000000000001")
ARTIFACT_ID = UUID("90000000-0000-0000-0000-000000000001")


class AsyncContextManagerMock:
    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


def make_rag_smoke_client(db_mock, storage_mock, anything_mock) -> TestClient:
    app = FastAPI()
    app.include_router(router)

    # Injeta a rota de teste de fumaça para ingestão de RAG
    @app.post("/v1/test/ingest-document/{artifactId}", tags=["test"])
    async def test_ingest_document(
        artifactId: UUID,
        workspace: str,
    ):
        service = KnowledgeIngestionService(anything_mock, db_mock, storage_mock)
        return await service.ingest_document(ORG_ID, artifactId, workspace)

    async def context() -> TenantContext:
        return TenantContext(
            user=AuthUser(id=USER_ID, email="admin@example.com"),
            token="token",
            membership=Membership(
                id="member",
                organization_id=ORG_ID,
                user_id=USER_ID,
                role=MemberRole.ADMIN,
                status="active",
            ),
        )

    app.dependency_overrides[tenant_context] = context
    return TestClient(app)


@pytest.mark.asyncio
async def test_rag_smoke_ingestion_lifecycle() -> None:
    # 1. Configurar Mocks
    conn = AsyncMock()
    conn.transaction = MagicMock(return_value=AsyncContextManagerMock(None))

    db_mock = MagicMock(spec=Database)
    db_mock.privileged.side_effect = lambda: AsyncContextManagerMock(conn)

    storage_mock = AsyncMock(spec=StorageGateway)
    storage_mock.signed_download.return_value = ("http://signed-url.com/doc.pdf", None)

    anything_mock = AsyncMock(spec=AnythingLlmClient)
    anything_mock.upload_document.return_value = "custom-documents/test.pdf"

    # Mock do download de arquivo HTTP
    class FakeResponse:
        def __init__(self, content):
            self.content = content
        def raise_for_status(self):
            pass

    mock_http_response = FakeResponse(b"pdf content bytes")
    mock_get = AsyncMock(return_value=mock_http_response)

    # 2. Configurar mock de queries SQL para caso Feliz
    async def mock_fetchrow(query, *args):
        query_lower = query.lower()
        if "from public.artifacts" in query_lower:
            return {
                "id": ARTIFACT_ID,
                "name": "manual.pdf",
                "storage_path": "org/manual.pdf",
                "checksum_sha256": "sha256hash",
                "mime_type": "application/pdf",
                "size_bytes": 1024,
                "quarantine_status": "clean",
            }
        elif "from public.anything_llm_ingestions" in query_lower:
            return None  # Não indexado ainda (caso feliz)
        return None

    conn.fetchrow.side_effect = mock_fetchrow

    client = make_rag_smoke_client(db_mock, storage_mock, anything_mock)

    # Executar a chamada via POST com mock de requisição HTTP (para o download do PDF)
    with patch("httpx.AsyncClient.get", mock_get):
        response = client.post(f"/v1/test/ingest-document/{ARTIFACT_ID}?workspace=bighead-docs")

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["externalDocumentId"] == "custom-documents/test.pdf"

    # Verifica se os mocks foram chamados
    storage_mock.signed_download.assert_called_once_with("org/manual.pdf")
    anything_mock.upload_document.assert_called_once()
    anything_mock.update_embeddings.assert_called_once_with(
        workspace_slug="bighead-docs", adds=["custom-documents/test.pdf"], deletes=[]
    )

    # Verifica se os status foram gravados
    assert conn.execute.called
