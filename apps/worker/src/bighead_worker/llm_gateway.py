from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

import httpx
from jsonschema import Draft202012Validator

ProviderName = Literal["openai", "anthropic", "google"]
_SECRET_FIELDS = (
    "api_key",
    "apikey",
    "authorization",
    "token",
    "secret",
    "password",
    "access_token",
    "client_secret",
)


def redact(value: Any) -> Any:
    """Return an observability-safe copy; provider credentials never enter payloads/logs."""
    if isinstance(value, Mapping):
        return {
            str(key): "[REDACTED]"
            if any(marker in str(key).lower() for marker in _SECRET_FIELDS)
            else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


@dataclass(frozen=True)
class LlmCapability:
    structured_output: bool = True
    tools: bool = False
    vision: bool = False


@dataclass(frozen=True)
class LlmRequest:
    prompt: str
    system: str | None
    schema: dict[str, Any]
    idempotency_key: str
    required: LlmCapability = LlmCapability()
    temperature: float = 0.0

    def __post_init__(self) -> None:
        if not self.prompt.strip() or not self.idempotency_key.strip():
            raise ValueError("prompt and idempotency_key are required")
        Draft202012Validator.check_schema(self.schema)


@dataclass(frozen=True)
class LlmResult:
    provider: ProviderName
    model: str
    provider_event_id: str
    output: dict[str, Any]
    input_tokens: int = 0
    output_tokens: int = 0


class LlmAdapter(Protocol):
    name: ProviderName
    model: str
    capability: LlmCapability

    async def generate(self, request: LlmRequest) -> LlmResult: ...


@dataclass
class CircuitBreaker:
    failure_threshold: int = 3
    recovery_seconds: float = 30.0
    failures: int = 0
    opened_at: float | None = None

    def allow(self) -> bool:
        if self.opened_at is None:
            return True
        if time.monotonic() - self.opened_at >= self.recovery_seconds:
            self.failures = 0
            self.opened_at = None
            return True
        return False

    def success(self) -> None:
        self.failures = 0
        self.opened_at = None

    def failure(self) -> None:
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.opened_at = time.monotonic()


@dataclass
class MultiProviderRouter:
    primary: LlmAdapter
    fallbacks: tuple[LlmAdapter, ...] = ()
    timeout_seconds: float = 60.0
    breakers: dict[ProviderName, CircuitBreaker] = field(default_factory=dict)

    async def generate(self, request: LlmRequest) -> LlmResult:
        errors: list[str] = []
        for adapter in (self.primary, *self.fallbacks):
            if not _compatible(request.required, adapter.capability):
                errors.append(f"{adapter.name}: incompatible capabilities")
                continue
            breaker = self.breakers.setdefault(adapter.name, CircuitBreaker())
            if not breaker.allow():
                errors.append(f"{adapter.name}: circuit open")
                continue
            try:
                async with asyncio.timeout(self.timeout_seconds):
                    result = await adapter.generate(request)
                Draft202012Validator(request.schema).validate(result.output)
                breaker.success()
                return result
            except Exception as exc:
                breaker.failure()
                errors.append(f"{adapter.name}: {type(exc).__name__}")
        raise RuntimeError("all compatible LLM providers failed: " + ", ".join(errors))


def _compatible(required: LlmCapability, actual: LlmCapability) -> bool:
    return all(
        not needed or supported
        for needed, supported in (
            (required.structured_output, actual.structured_output),
            (required.tools, actual.tools),
            (required.vision, actual.vision),
        )
    )


@dataclass
class HttpLlmAdapter:
    name: ProviderName
    model: str
    api_key: str = field(repr=False)
    base_url: str = ""
    capability: LlmCapability = LlmCapability()
    transport: httpx.AsyncBaseTransport | None = field(default=None, repr=False)

    async def generate(self, request: LlmRequest) -> LlmResult:
        url, headers, body = self._wire_request(request)
        async with httpx.AsyncClient(transport=self.transport, timeout=60) as client:
            response = await client.post(url, headers=headers, json=body)
        response.raise_for_status()
        return self._wire_response(response)

    def _wire_request(self, request: LlmRequest) -> tuple[str, dict[str, str], dict[str, Any]]:
        common = {"Content-Type": "application/json", "Idempotency-Key": request.idempotency_key}
        if self.name == "openai":
            return (
                (self.base_url or "https://api.openai.com") + "/v1/responses",
                {**common, "Authorization": f"Bearer {self.api_key}"},
                {
                    "model": self.model,
                    "instructions": request.system,
                    "input": request.prompt,
                    "temperature": request.temperature,
                    "text": {
                        "format": {
                            "type": "json_schema",
                            "name": "bighead_output",
                            "strict": True,
                            "schema": request.schema,
                        }
                    },
                },
            )
        if self.name == "anthropic":
            return (
                (self.base_url or "https://api.anthropic.com") + "/v1/messages",
                {**common, "x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
                {
                    "model": self.model,
                    "max_tokens": 4096,
                    "system": request.system
                    or "Return only valid JSON matching the supplied schema.",
                    "messages": [{"role": "user", "content": request.prompt}],
                    "output_config": {"format": {"type": "json_schema", "schema": request.schema}},
                },
            )
        return (
            (self.base_url or "https://generativelanguage.googleapis.com")
            + f"/v1beta/models/{self.model}:generateContent",
            {**common, "x-goog-api-key": self.api_key},
            {
                "systemInstruction": {"parts": [{"text": request.system}]}
                if request.system
                else None,
                "contents": [{"role": "user", "parts": [{"text": request.prompt}]}],
                "generationConfig": {
                    "temperature": request.temperature,
                    "responseMimeType": "application/json",
                    "responseJsonSchema": request.schema,
                },
            },
        )

    def _wire_response(self, response: httpx.Response) -> LlmResult:
        payload = response.json()
        if self.name == "openai":
            text = payload.get("output_text")
            if text is None:
                text = payload["output"][0]["content"][0]["text"]
            usage = payload.get("usage", {})
            event_id = str(payload["id"])
            input_tokens, output_tokens = (
                usage.get("input_tokens", 0),
                usage.get("output_tokens", 0),
            )
        elif self.name == "anthropic":
            text = payload["content"][0]["text"]
            usage = payload.get("usage", {})
            event_id = str(payload["id"])
            input_tokens, output_tokens = (
                usage.get("input_tokens", 0),
                usage.get("output_tokens", 0),
            )
        else:
            text = payload["candidates"][0]["content"]["parts"][0]["text"]
            usage = payload.get("usageMetadata", {})
            event_id = response.headers.get("x-request-id") or str(
                payload.get("responseId", "google-response")
            )
            input_tokens, output_tokens = (
                usage.get("promptTokenCount", 0),
                usage.get("candidatesTokenCount", 0),
            )
        output = json.loads(text)
        if not isinstance(output, dict):
            raise ValueError("structured LLM response must be an object")
        return LlmResult(
            self.name, self.model, event_id, output, int(input_tokens), int(output_tokens)
        )


def build_router(
    *,
    default_provider: ProviderName,
    fallback_provider: ProviderName,
    default_model: str,
    fallback_model: str,
    api_keys: Mapping[str, str],
    timeout_seconds: float,
) -> MultiProviderRouter:
    def adapter(provider: ProviderName, model: str) -> HttpLlmAdapter:
        key = api_keys.get(provider, "").strip()
        if not key:
            raise ValueError(f"missing API key for LLM provider {provider}")
        return HttpLlmAdapter(provider, model, key)

    return MultiProviderRouter(
        adapter(default_provider, default_model),
        (adapter(fallback_provider, fallback_model),),
        timeout_seconds,
    )
