import logging
from typing import Any
from uuid import UUID

import httpx
from bighead_pycore.integrations.anythingllm import AnythingLlmClient, AnythingLlmClientError

from bighead_api.artifacts.service import StorageGateway
from bighead_api.identity.repository import Database

logger = logging.getLogger(__name__)


class KnowledgeIngestionServiceError(Exception):
    """Exceção levantada para erros no serviço de ingestão de conhecimento."""

    pass


class KnowledgeIngestionService:
    def __init__(
        self,
        anything_llm_client: AnythingLlmClient,
        database: Database,
        storage_gateway: StorageGateway,
    ):
        self.anything_llm_client = anything_llm_client
        self.database = database
        self.storage = storage_gateway

    async def ingest_document(
        self, organization_id: UUID, artifact_id: UUID, workspace_slug: str
    ) -> dict[str, Any]:
        """Orquestra a ingestão de um documento corporativo aprovado no AnythingLLM.

        Garante idempotência, persistência de status e isolamento de tenant.
        """
        async with self.database.privileged() as conn:
            # 1. Recupera metadados do artefato
            artifact = await conn.fetchrow(
                """select id, name, storage_path, checksum_sha256, mime_type,
                          size_bytes, quarantine_status::text
                     from public.artifacts
                    where id=$1 and organization_id=$2""",
                artifact_id,
                organization_id,
            )
            if not artifact:
                raise KnowledgeIngestionServiceError("Artifact not found")

            # Ingestão somente de documento aprovado / clean
            if artifact["quarantine_status"] != "clean":
                raise KnowledgeIngestionServiceError(
                    f"Artifact quarantine status is '{artifact['quarantine_status']}'. "
                    "Only clean artifacts can be ingested."
                )

            # 2. Verifica idempotência
            existing = await conn.fetchrow(
                """select status, external_document_id
                     from public.anything_llm_ingestions
                    where artifact_id=$1 and organization_id=$2""",
                artifact_id,
                organization_id,
            )
            if existing and existing["status"] == "success":
                logger.info(
                    "Documento já indexado com sucesso no AnythingLLM. "
                    "Reutilizando indexação (Idempotência).",
                    extra={"artifact_id": str(artifact_id)},
                )
                return {
                    "artifactId": artifact_id,
                    "status": "success",
                    "externalDocumentId": existing["external_document_id"],
                }

            # Registra/Atualiza o status como 'processing'
            await conn.execute(
                """insert into public.anything_llm_ingestions
                      (artifact_id, organization_id, workspace, status,
                       checksum_sha256, mime_type, size_bytes)
                   values ($1, $2, $3, 'processing', $4, $5, $6)
                   on conflict (artifact_id) do update
                      set status = 'processing', updated_at = now()""",
                artifact_id,
                organization_id,
                workspace_slug,
                artifact["checksum_sha256"],
                artifact["mime_type"],
                artifact["size_bytes"],
            )

        # 3. Download do conteúdo do storage do Supabase
        try:
            download_url, _ = await self.storage.signed_download(artifact["storage_path"])
            async with httpx.AsyncClient(timeout=60) as client:
                download_res = await client.get(download_url)
                download_res.raise_for_status()
                content = download_res.content
        except Exception as exc:
            await self._mark_failure(
                organization_id,
                artifact_id,
                "DOWNLOAD_FAILED",
                f"Failed to download file content from storage: {exc}",
            )
            raise KnowledgeIngestionServiceError(f"Storage download failed: {exc}") from exc

        # 4. Upload e indexação no AnythingLLM
        try:
            # Upload do arquivo
            doc_location = await self.anything_llm_client.upload_document(content, artifact["name"])
            # Ingestão de embeddings no workspace específico do tenant
            await self.anything_llm_client.update_embeddings(
                workspace_slug=workspace_slug, adds=[doc_location], deletes=[]
            )
        except AnythingLlmClientError as exc:
            await self._mark_failure(
                organization_id,
                artifact_id,
                "ANYTHING_LLM_ERROR",
                str(exc),
            )
            raise KnowledgeIngestionServiceError(f"AnythingLLM integration failed: {exc}") from exc
        except Exception as exc:
            await self._mark_failure(
                organization_id,
                artifact_id,
                "INGESTION_FAILED",
                f"Unexpected ingestion error: {exc}",
            )
            raise KnowledgeIngestionServiceError(f"Ingestion failed unexpectedly: {exc}") from exc

        # 5. Sucesso: Grava e atualiza o status de sucesso com o id do documento externo
        async with self.database.privileged() as conn:
            await conn.execute(
                """update public.anything_llm_ingestions
                      set status = 'success',
                          external_document_id = $3,
                          embeddings_updated_at = now(),
                          error_code = null,
                          error_message = null,
                          updated_at = now()
                    where artifact_id = $1 and organization_id = $2""",
                artifact_id,
                organization_id,
                doc_location,
            )

        return {
            "artifactId": artifact_id,
            "status": "success",
            "externalDocumentId": doc_location,
        }

    async def _mark_failure(
        self, organization_id: UUID, artifact_id: UUID, code: str, message: str
    ) -> None:
        """Grava com segurança as falhas na tabela anything_llm_ingestions para auditoria."""
        async with self.database.privileged() as conn:
            await conn.execute(
                """update public.anything_llm_ingestions
                      set status = 'failed',
                          error_code = $3,
                          error_message = $4,
                          updated_at = now()
                    where artifact_id = $1 and organization_id = $2""",
                artifact_id,
                organization_id,
                code,
                message[:1000],
            )
