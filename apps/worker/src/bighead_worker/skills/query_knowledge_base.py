import logging
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
    try:
        logger.info(
            "Executando skill query_knowledge_base",
            extra={"workspace": workspace_slug, "query": query},
        )
        res = await client.query_workspace(workspace_slug, query)
        return {
            "text": res.get("text", "Nenhuma informação encontrada."),
            "sources": [src.get("title") for src in res.get("sources", []) if src.get("title")],
        }
    except Exception as exc:
        logger.error("Erro ao executar skill query_knowledge_base", exc_info=True)
        return {"error": str(exc)}
