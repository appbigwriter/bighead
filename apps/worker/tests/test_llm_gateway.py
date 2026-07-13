import httpx
import pytest
from bighead_worker.llm_gateway import (
    HttpLlmAdapter,
    LlmCapability,
    LlmRequest,
    LlmResult,
    MultiProviderRouter,
    redact,
)

SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "string"}},
    "required": ["answer"],
    "additionalProperties": False,
}


@pytest.mark.asyncio
async def test_openai_adapter_forwards_idempotency_and_schema() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Idempotency-Key"] == "run:1"
        assert b'"json_schema"' in request.content
        return httpx.Response(
            200,
            json={
                "id": "resp-1",
                "output_text": '{"answer":"ok"}',
                "usage": {"input_tokens": 2, "output_tokens": 1},
            },
        )

    adapter = HttpLlmAdapter(
        "openai",
        "gpt-test",
        "secret",
        base_url="https://provider.test",
        transport=httpx.MockTransport(handler),
    )
    result = await adapter.generate(LlmRequest("hello", None, SCHEMA, "run:1"))
    assert result.output == {"answer": "ok"}


class Stub:
    def __init__(
        self, name: str, output: dict[str, object], capability: LlmCapability | None = None
    ) -> None:
        self.name = name
        self.model = "test"
        self.output = output
        self.capability = capability or LlmCapability()
        self.calls = 0

    async def generate(self, request: LlmRequest) -> LlmResult:
        self.calls += 1
        return LlmResult(self.name, self.model, "event", self.output)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_router_falls_back_only_to_compatible_valid_provider() -> None:
    primary = Stub("openai", {"wrong": True})
    incompatible = Stub("google", {"answer": "bad"}, LlmCapability(structured_output=False))
    fallback = Stub("anthropic", {"answer": "ok"})
    result = await MultiProviderRouter(primary, (incompatible, fallback)).generate(
        LlmRequest("hi", None, SCHEMA, "run:2")
    )
    assert result.provider == "anthropic"
    assert incompatible.calls == 0


def test_redaction_is_recursive() -> None:
    assert redact({"api_key": "secret", "nested": {"token": "x", "safe": 1}}) == {
        "api_key": "[REDACTED]",
        "nested": {"token": "[REDACTED]", "safe": 1},
    }
    assert redact({"nested": {"apiKey": "x", "access_token": "y", "client_secret": "z"}}) == {
        "nested": {
            "apiKey": "[REDACTED]",
            "access_token": "[REDACTED]",
            "client_secret": "[REDACTED]",
        }
    }
