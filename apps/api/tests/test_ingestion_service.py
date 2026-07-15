from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from bighead_api.artifacts.service import StorageGateway
from bighead_api.governance.ingestion import (
    KnowledgeIngestionService,
    KnowledgeIngestionServiceError,
)
from bighead_pycore.integrations.anythingllm import AnythingLlmClient, AnythingLlmClientError


class AsyncContextManagerMock:
    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.fixture
def mock_db_and_conn():
    conn = AsyncMock()
    from unittest.mock import MagicMock

    db = MagicMock()
    db.privileged.side_effect = lambda: AsyncContextManagerMock(conn)
    return db, conn


@pytest.fixture
def mock_storage():
    storage = AsyncMock(spec=StorageGateway)
    storage.signed_download.return_value = ("http://signed-url.com/doc.pdf", None)
    return storage


@pytest.fixture
def mock_anything_llm():
    client = AsyncMock(spec=AnythingLlmClient)
    client.upload_document.return_value = "custom-documents/test.pdf"
    return client


@pytest.mark.asyncio
async def test_ingest_document_success(mock_db_and_conn, mock_storage, mock_anything_llm):
    db, conn = mock_db_and_conn
    artifact_id = uuid4()
    org_id = uuid4()

    # 1. Mock do artefato existente e limpo no banco
    conn.fetchrow.side_effect = [
        # Retorno de public.artifacts
        {
            "id": artifact_id,
            "name": "test.pdf",
            "storage_path": "org/user/test.pdf",
            "checksum_sha256": "sha256hash",
            "mime_type": "application/pdf",
            "size_bytes": 1024,
            "quarantine_status": "clean",
        },
        # Retorno de public.anything_llm_ingestions (nenhuma ingestão anterior com sucesso)
        None,
    ]

    service = KnowledgeIngestionService(mock_anything_llm, db, mock_storage)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        from unittest.mock import MagicMock

        mock_res = MagicMock(content=b"pdf-data", status_code=200)
        mock_res.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_res
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        res = await service.ingest_document(org_id, artifact_id, "test-workspace")

    assert res["status"] == "success"
    assert res["externalDocumentId"] == "custom-documents/test.pdf"

    # Verifica chamadas ao AnythingLLM
    mock_anything_llm.upload_document.assert_called_once_with(b"pdf-data", "test.pdf")
    mock_anything_llm.update_embeddings.assert_called_once_with(
        workspace_slug="test-workspace", adds=["custom-documents/test.pdf"], deletes=[]
    )

    # Verifica se os updates de status foram feitos no banco
    assert conn.execute.called


@pytest.mark.asyncio
async def test_ingest_document_not_clean_raises_error(
    mock_db_and_conn, mock_storage, mock_anything_llm
):
    db, conn = mock_db_and_conn
    artifact_id = uuid4()
    org_id = uuid4()

    # Mock do artefato com status 'pending' (quarentena não limpa)
    conn.fetchrow.return_value = {
        "id": artifact_id,
        "name": "test.pdf",
        "storage_path": "org/user/test.pdf",
        "checksum_sha256": "sha256hash",
        "mime_type": "application/pdf",
        "size_bytes": 1024,
        "quarantine_status": "pending",
    }

    service = KnowledgeIngestionService(mock_anything_llm, db, mock_storage)

    with pytest.raises(KnowledgeIngestionServiceError) as exc_info:
        await service.ingest_document(org_id, artifact_id, "test-workspace")
    assert "Only clean artifacts can be ingested" in str(exc_info.value)


@pytest.mark.asyncio
async def test_ingest_document_idempotency(mock_db_and_conn, mock_storage, mock_anything_llm):
    db, conn = mock_db_and_conn
    artifact_id = uuid4()
    org_id = uuid4()

    conn.fetchrow.side_effect = [
        # Retorno de public.artifacts
        {
            "id": artifact_id,
            "name": "test.pdf",
            "storage_path": "org/user/test.pdf",
            "checksum_sha256": "sha256hash",
            "mime_type": "application/pdf",
            "size_bytes": 1024,
            "quarantine_status": "clean",
        },
        # Retorno de public.anything_llm_ingestions (documento já indexado com sucesso)
        {"status": "success", "external_document_id": "custom-documents/already-indexed.pdf"},
    ]

    service = KnowledgeIngestionService(mock_anything_llm, db, mock_storage)
    res = await service.ingest_document(org_id, artifact_id, "test-workspace")

    assert res["status"] == "success"
    assert res["externalDocumentId"] == "custom-documents/already-indexed.pdf"

    # Nenhuma chamada de upload ou embedding deve ter sido executada
    mock_anything_llm.upload_document.assert_not_called()
    mock_anything_llm.update_embeddings.assert_not_called()


@pytest.mark.asyncio
async def test_ingest_document_failure_updates_status(
    mock_db_and_conn, mock_storage, mock_anything_llm
):
    db, conn = mock_db_and_conn
    artifact_id = uuid4()
    org_id = uuid4()

    conn.fetchrow.side_effect = [
        {
            "id": artifact_id,
            "name": "test.pdf",
            "storage_path": "org/user/test.pdf",
            "checksum_sha256": "sha256hash",
            "mime_type": "application/pdf",
            "size_bytes": 1024,
            "quarantine_status": "clean",
        },
        None,
    ]

    # Simula erro na chamada do AnythingLLM
    mock_anything_llm.upload_document.side_effect = AnythingLlmClientError("API error")

    service = KnowledgeIngestionService(mock_anything_llm, db, mock_storage)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        from unittest.mock import MagicMock

        mock_res = MagicMock(content=b"pdf-data", status_code=200)
        mock_res.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_res
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        with pytest.raises(KnowledgeIngestionServiceError) as exc_info:
            await service.ingest_document(org_id, artifact_id, "test-workspace")
        assert "AnythingLLM integration failed" in str(exc_info.value)

    # Verifica se registrou falha no banco de dados
    calls = conn.execute.call_args_list
    assert any("failed" in str(call) for call in calls)
