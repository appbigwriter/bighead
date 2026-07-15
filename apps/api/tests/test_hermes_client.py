import httpx
import pytest
import respx
from bighead_pycore.integrations.hermes import HermesClient, HermesContractError


@pytest.mark.asyncio
@respx.mock
async def test_hermes_client_success():
    client = HermesClient(api_url="http://localhost:8642", api_key="test-key")

    # Mock da resposta válida compatível com OpenAI
    respx.post("http://localhost:8642/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "chatcmpl-12345",
                "object": "chat.completion",
                "created": 1677652288,
                "model": "hermes-model-v1",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Olá, eu sou o Hermes!"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 15, "completion_tokens": 10, "total_tokens": 25},
            },
        )
    )

    response = await client.chat_completion(
        messages=[{"role": "user", "content": "Olá"}],
        idempotency_key="key-123",
        profile="test-profile",
    )

    assert response.provider_event_id == "chatcmpl-12345"
    assert response.model == "hermes-model-v1"
    assert response.input_tokens == 15
    assert response.output_tokens == 10
    assert response.content == "Olá, eu sou o Hermes!"


@pytest.mark.asyncio
@respx.mock
async def test_hermes_client_500_error():
    client = HermesClient(api_url="http://localhost:8642", api_key="test-key")

    respx.post("http://localhost:8642/v1/chat/completions").mock(
        return_value=httpx.Response(500, text="Internal Server Error")
    )

    with pytest.raises(RuntimeError) as exc_info:
        await client.chat_completion(
            messages=[{"role": "user", "content": "Olá"}], idempotency_key="key-123"
        )
    assert "Hermes HTTP call failed" in str(exc_info.value)


@pytest.mark.asyncio
@respx.mock
async def test_hermes_client_timeout():
    client = HermesClient(api_url="http://localhost:8642", api_key="test-key", timeout_seconds=0.1)

    respx.post("http://localhost:8642/v1/chat/completions").mock(
        side_effect=httpx.TimeoutException("Timeout")
    )

    with pytest.raises(RuntimeError) as exc_info:
        await client.chat_completion(
            messages=[{"role": "user", "content": "Olá"}], idempotency_key="key-123"
        )
    assert "Hermes HTTP call failed" in str(exc_info.value)


@pytest.mark.asyncio
@respx.mock
async def test_hermes_client_missing_fields_contract_error():
    client = HermesClient(api_url="http://localhost:8642", api_key="test-key")

    # Resposta sem o ID
    respx.post("http://localhost:8642/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "model": "hermes-model-v1",
                "choices": [{"message": {"content": "Erro"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 10},
            },
        )
    )

    with pytest.raises(HermesContractError) as exc_info:
        await client.chat_completion(
            messages=[{"role": "user", "content": "Olá"}], idempotency_key="key-123"
        )
    assert "Missing or invalid providerEventId" in str(exc_info.value)
