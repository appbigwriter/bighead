import hashlib
import logging
import re
from typing import Any

from bighead_pycore.integrations.anythingllm import AnythingLlmClient

logger = logging.getLogger(__name__)

# Definição do schema OpenAI Tool da Skill para o Hermes
QUERY_KNOWLEDGE_BASE_TOOL = {
    "type": "function",
    "function": {
        "name": "query_knowledge_base",
        "description": (
            "Consulta a base de conhecimento corporativa (RAG) do tenant/organização "
            "para obter respostas contextuais baseadas em documentos privados."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "A pergunta ou termo de busca a ser pesquisado "
                        "na base de conhecimento."
                    ),
                }
            },
            "required": ["query"],
        },
    },
}


async def execute_query_knowledge_base(
    client: AnythingLlmClient, workspace_slug: str, query: str
) -> dict[str, Any]:
    """Executa a busca na base de conhecimento (RAG) e retorna a resposta textual com fontes."""
    normalized_query = re.sub(r"[\x00-\x1f\x7f]", " ", query).strip()[:2000]
    if not normalized_query:
        return {"error": "invalid_query"}
    try:
        logger.info(
            "Executando skill query_knowledge_base",
            extra={
                "workspace": workspace_slug,
                "query_sha256": hashlib.sha256(normalized_query.encode()).hexdigest(),
            },
        )
        res = await client.query_workspace(workspace_slug, normalized_query)
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", str(res.get("text", "")))
        sources = [
            re.sub(r"[\x00-\x1f\x7f]", " ", str(src.get("title", ""))).strip()[:300]
            for src in res.get("sources", [])[:20]
            if isinstance(src, dict) and src.get("title")
        ]
        return {
            "text": text[:12000] or "Nenhuma informação encontrada.",
            "sources": sources,
        }
    except Exception:
        logger.error("Erro ao executar skill query_knowledge_base", exc_info=True)
        return {"error": "knowledge_base_unavailable"}
