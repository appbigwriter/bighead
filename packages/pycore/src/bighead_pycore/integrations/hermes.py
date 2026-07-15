import logging
from typing import Any

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class HermesContractError(Exception):
    """Exceção levantada quando o Hermes retorna uma resposta fora do contrato esperado."""

    pass


class HermesResponse(BaseModel):
    provider_event_id: str
    model: str
    input_tokens: int
    output_tokens: int
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None


class HermesClient:
    def __init__(self, api_url: str, api_key: str, timeout_seconds: float = 60.0):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    async def chat_completion(
        self,
        messages: list[dict[str, Any]],
        idempotency_key: str,
        profile: str | None = None,
        organization_id: str | None = None,
        run_id: str | None = None,
        model: str | None = None,
        temperature: float = 0.0,
        response_format: dict[str, Any] | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> HermesResponse:
        url = f"{self.api_url}/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "Idempotency-Key": idempotency_key,
        }
        if profile:
            headers["X-Hermes-Profile"] = profile
        if organization_id:
            headers["X-BigHead-Organization-Id"] = organization_id
        if run_id:
            headers["X-BigHead-Run-Id"] = run_id

        payload: dict[str, Any] = {
            "model": model or "hermes",
            "messages": messages,
            "temperature": temperature,
        }
        if response_format:
            payload["response_format"] = response_format
        if tools:
            payload["tools"] = tools

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                logger.info(
                    "Chamando chat completion do Hermes",
                    extra={
                        "url": url,
                        "profile": profile,
                        "model": payload["model"],
                        "idempotency_key": idempotency_key,
                    },
                )
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            logger.error("Erro HTTP ao chamar Hermes", exc_info=True)
            raise RuntimeError(f"Hermes HTTP call failed: {exc}") from exc
        except Exception as exc:
            logger.error("Erro inesperado ao chamar Hermes", exc_info=True)
            raise RuntimeError(f"Unexpected error in Hermes client: {exc}") from exc

        # Validação do contrato
        provider_event_id = data.get("id")
        resp_model = data.get("model")
        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens")
        output_tokens = usage.get("completion_tokens")

        if (
            not provider_event_id
            or not isinstance(provider_event_id, str)
            or not provider_event_id.strip()
        ):
            raise HermesContractError("Missing or invalid providerEventId (id) in Hermes response")
        if not resp_model or not isinstance(resp_model, str) or not resp_model.strip():
            raise HermesContractError("Missing or invalid model in Hermes response")
        if input_tokens is None or not isinstance(input_tokens, int) or input_tokens < 0:
            raise HermesContractError(
                "Missing or invalid prompt_tokens (input_tokens) in Hermes response"
            )
        if output_tokens is None or not isinstance(output_tokens, int) or output_tokens < 0:
            raise HermesContractError(
                "Missing or invalid completion_tokens (output_tokens) in Hermes response"
            )

        choices = data.get("choices", [])
        if not choices or not isinstance(choices, list):
            raise HermesContractError("Missing or invalid choices in Hermes response")

        message_data = choices[0].get("message", {})
        content = message_data.get("content")
        tool_calls = message_data.get("tool_calls")

        return HermesResponse(
            provider_event_id=provider_event_id,
            model=resp_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            content=content,
            tool_calls=tool_calls,
        )
