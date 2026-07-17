import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class AnythingLlmClientError(Exception):
    """Exceção levantada para falhas na API do AnythingLLM."""

    pass


class AnythingLlmClient:
    def __init__(self, api_url: str, api_key: str, timeout_seconds: float = 60.0):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def upload_document(self, file_content: bytes, file_name: str) -> str:
        """Faz o upload de um documento para o AnythingLLM.

        Retorna a localização interna do documento.
        """
        url = f"{self.api_url}/api/v1/document/upload"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }
        files = {"file": (file_name, file_content)}

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                logger.info(
                    "Enviando documento para upload no AnythingLLM",
                    extra={"file_name": file_name},
                )
                response = await client.post(url, headers=headers, files=files)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            logger.error("Erro HTTP no upload do AnythingLLM", exc_info=True)
            raise AnythingLlmClientError(f"AnythingLLM upload failed: {exc}") from exc
        except Exception as exc:
            logger.error("Erro inesperado no upload do AnythingLLM", exc_info=True)
            raise AnythingLlmClientError(f"Unexpected upload error: {exc}") from exc

        success = data.get("success", False)
        documents = data.get("documents", [])
        if not success or not documents:
            raise AnythingLlmClientError("AnythingLLM upload returned unsuccessful status")

        location = documents[0].get("location")
        if not location:
            raise AnythingLlmClientError("Missing document location in AnythingLLM upload response")

        return str(location)

    async def update_embeddings(
        self, workspace_slug: str, adds: list[str], deletes: list[str] = None
    ) -> None:
        """Associa ou remove documentos no workspace do AnythingLLM e recalcula embeddings."""
        url = f"{self.api_url}/api/v1/workspace/{workspace_slug}/update-embeddings"
        payload = {"adds": adds, "deletes": deletes or []}

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                logger.info(
                    "Atualizando embeddings no workspace AnythingLLM",
                    extra={
                        "workspace": workspace_slug,
                        "adds": adds,
                        "deletes": payload["deletes"],
                    },
                )
                response = await client.post(url, headers=self._headers(), json=payload)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("Erro HTTP ao atualizar embeddings no AnythingLLM", exc_info=True)
            raise AnythingLlmClientError(f"AnythingLLM update-embeddings failed: {exc}") from exc
        except Exception as exc:
            logger.error(
                "Erro inesperado ao atualizar embeddings no AnythingLLM",
                exc_info=True,
            )
            raise AnythingLlmClientError(f"Unexpected update-embeddings error: {exc}") from exc

    async def query_workspace(self, workspace_slug: str, query: str) -> dict[str, Any]:
        """Consulta o workspace com RAG (modo query)."""
        url = f"{self.api_url}/api/v1/workspace/{workspace_slug}/chat"
        payload = {"message": query, "mode": "query"}

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                logger.info(
                    "Consultando workspace no AnythingLLM",
                    extra={"workspace": workspace_slug},
                )
                response = await client.post(url, headers=self._headers(), json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            logger.error("Erro HTTP ao consultar AnythingLLM", exc_info=True)
            raise AnythingLlmClientError(f"AnythingLLM query failed: {exc}") from exc
        except Exception as exc:
            logger.error("Erro inesperado ao consultar AnythingLLM", exc_info=True)
            raise AnythingLlmClientError(f"Unexpected query workspace error: {exc}") from exc

        return dict(data)
