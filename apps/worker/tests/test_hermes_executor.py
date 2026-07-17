from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import UUID

import httpx
import pytest
import respx
from bighead_pycore import AnythingLlmClient, HermesClient, HermesContractError, HermesResponse
from bighead_worker.runs import (
    HermesExecutionError,
    HermesRunExecutor,
    ProviderResult,
    RunJob,
    SupabaseRunStore,
)

RUN_ID = UUID("71000000-0000-0000-0000-000000000001")
ORG_ID = UUID("72000000-0000-0000-0000-000000000001")
TASK_ID = UUID("73000000-0000-0000-0000-000000000001")
AGENT_ID = UUID("74000000-0000-0000-0000-000000000001")
VERSION_ID = UUID("75000000-0000-0000-0000-000000000001")

SCHEMA = {
    "type": "object",
    "required": ["key"],
    "properties": {"key": {"type": "string"}},
    "additionalProperties": False,
}


def create_hermes_job(
    agent_enabled: bool = True,
    system_prompt: str = "Você é o Hermes.",
    output_schema: dict = SCHEMA,
    model_prices: dict = None,
    skills: list[dict] | None = None,
) -> RunJob:
    if model_prices is None:
        model_prices = {
            "hermes-model": {
                "modelId": "76000000-0000-0000-0000-000000000001",
                "inputCostPerMillion": "5",
                "outputCostPerMillion": "15",
            }
        }
    return RunJob(
        id=RUN_ID,
        organization_id=ORG_ID,
        task_id=TASK_ID,
        workflow_version_id=None,
        attempt=1,
        max_attempts=3,
        retry_backoff_seconds=7,
        policy_snapshot={
            "timeoutSeconds": 30,
            "maxAttempts": 3,
            "retryBackoffSeconds": 7,
            "skills": skills or [],
        },
        task_title="Criar próxima ação",
        task_objective="Criar próxima ação",
        task_metadata={"impact": "marketing"},
        agent_id=AGENT_ID,
        agent_name="Hermes Bot",
        agent_enabled=agent_enabled,
        agent_version_id=VERSION_ID,
        system_prompt=system_prompt,
        output_schema=output_schema,
        model_prices=model_prices,
    )


@pytest.fixture
def anything_mock():
    return AsyncMock(spec=AnythingLlmClient)


@pytest.mark.asyncio
async def test_hermes_executor_success(anything_mock) -> None:
    client_mock = AsyncMock(spec=HermesClient)
    client_mock.chat_completion.return_value = HermesResponse(
        provider_event_id="event-123",
        model="hermes-model",
        input_tokens=1000,
        output_tokens=200,
        content='{"key": "value"}',
        tool_calls=None,
    )

    executor = HermesRunExecutor(client_mock, anything_mock)
    run = create_hermes_job(skills=[{"slug": "query_knowledge_base"}])

    result = await executor.execute(run, idempotency_key=run.effect_key)

    assert result == ProviderResult(
        provider_event_id="hermes:event-123",
        amount=Decimal("0.008000"),  # (1000 * 5 + 200 * 15) / 1,000,000 = 0.008
        currency="USD",
        input_tokens=1000,
        output_tokens=200,
        model_id=UUID("76000000-0000-0000-0000-000000000001"),
    )

    # Verifica os parâmetros de chamada ao cliente
    client_mock.chat_completion.assert_called_once()
    kwargs = client_mock.chat_completion.call_args.kwargs
    assert kwargs["profile"] == str(VERSION_ID)
    assert kwargs["organization_id"] == str(ORG_ID)
    assert kwargs["run_id"] == str(RUN_ID)
    assert kwargs["idempotency_key"] == f"{run.effect_key}-0"


@pytest.mark.asyncio
async def test_hermes_executor_fails_when_agent_disabled(anything_mock) -> None:
    client_mock = AsyncMock(spec=HermesClient)
    executor = HermesRunExecutor(client_mock, anything_mock)
    run = create_hermes_job(agent_enabled=False)

    with pytest.raises(ValueError, match="enabled tenant agent"):
        await executor.execute(run, idempotency_key=run.effect_key)
    client_mock.chat_completion.assert_not_called()


@pytest.mark.asyncio
async def test_hermes_executor_fails_without_system_prompt(anything_mock) -> None:
    client_mock = AsyncMock(spec=HermesClient)
    executor = HermesRunExecutor(client_mock, anything_mock)
    run = create_hermes_job(system_prompt="")

    with pytest.raises(ValueError, match="published agent system prompt"):
        await executor.execute(run, idempotency_key=run.effect_key)
    client_mock.chat_completion.assert_not_called()


@pytest.mark.asyncio
async def test_hermes_executor_fails_without_output_schema(anything_mock) -> None:
    client_mock = AsyncMock(spec=HermesClient)
    executor = HermesRunExecutor(client_mock, anything_mock)
    run = create_hermes_job(output_schema={})

    with pytest.raises(ValueError, match="applicable output schema"):
        await executor.execute(run, idempotency_key=run.effect_key)
    client_mock.chat_completion.assert_not_called()


@pytest.mark.asyncio
async def test_hermes_executor_fails_on_schema_validation_error(anything_mock) -> None:
    client_mock = AsyncMock(spec=HermesClient)
    client_mock.chat_completion.return_value = HermesResponse(
        provider_event_id="event-123",
        model="hermes-model",
        input_tokens=100,
        output_tokens=50,
        content='{"wrong_key": "value"}',
        tool_calls=None,
    )

    executor = HermesRunExecutor(client_mock, anything_mock)
    run = create_hermes_job()

    with pytest.raises(HermesExecutionError, match="VALIDATION_FAILED"):
        await executor.execute(run, idempotency_key=run.effect_key)


@pytest.mark.asyncio
async def test_hermes_executor_fails_on_contract_error(anything_mock) -> None:
    client_mock = AsyncMock(spec=HermesClient)
    client_mock.chat_completion.side_effect = HermesContractError("Incomplete response")

    executor = HermesRunExecutor(client_mock, anything_mock)
    run = create_hermes_job()

    with pytest.raises(HermesExecutionError, match="CONTRACT_VIOLATION"):
        await executor.execute(run, idempotency_key=run.effect_key)


@pytest.mark.asyncio
@respx.mock
async def test_hermes_executor_function_calling_loop(anything_mock) -> None:
    client_mock = AsyncMock(spec=HermesClient)

    # 1ª resposta do Hermes: solicita chamar a skill query_knowledge_base
    first_resp = HermesResponse(
        provider_event_id="event-1",
        model="hermes-model",
        input_tokens=1000,
        output_tokens=150,
        content=None,
        tool_calls=[
            {
                "id": "call-abc",
                "type": "function",
                "function": {
                    "name": "query_knowledge_base",
                    "arguments": '{"query": "manual do bighead"}',
                },
            }
        ],
    )

    # 2ª resposta do Hermes: retorna a resposta final estruturada
    second_resp = HermesResponse(
        provider_event_id="event-2",
        model="hermes-model",
        input_tokens=1200,
        output_tokens=300,
        content='{"key": "manual contextualized"}',
        tool_calls=None,
    )

    client_mock.chat_completion.side_effect = [first_resp, second_resp]

    # Mock do AnythingLLM retornando a busca
    anything_mock.query_workspace.return_value = {
        "text": "Conteudo do manual de RAG",
        "sources": [{"title": "manual.pdf"}],
    }

    # Setup do store fictício para buscar o slug da organização no Supabase
    store = AsyncMock(spec=SupabaseRunStore)
    store.base_url = "http://supabase"
    store._headers.return_value = {"apikey": "test-key"}

    # Mock do GET no Supabase REST para buscar o slug
    respx.get("http://supabase/rest/v1/organizations").mock(
        return_value=httpx.Response(200, json=[{"slug": "org-slug-from-db"}])
    )

    executor = HermesRunExecutor(client_mock, anything_mock, run_store=store)
    run = create_hermes_job(skills=[{"slug": "query_knowledge_base"}])

    result = await executor.execute(run, idempotency_key=run.effect_key)

    # Verifica se os custos acumulados de todas as iterações foram considerados
    assert result == ProviderResult(
        provider_event_id="hermes:event-2",
        amount=Decimal("0.017750"),  # (2200 * 5 + 450 * 15) / 1,000,000 = 0.017750
        currency="USD",
        input_tokens=2200,
        output_tokens=450,
        model_id=UUID("76000000-0000-0000-0000-000000000001"),
    )

    # Verifica se a chamada à skill AnythingLLM foi feita no workspace_slug correto
    # (slug obtido do banco de dados)
    anything_mock.query_workspace.assert_called_once_with("org-slug-from-db", "manual do bighead")


@pytest.mark.asyncio
async def test_hermes_executor_does_not_offer_unapproved_rag_tool(anything_mock) -> None:
    client_mock = AsyncMock(spec=HermesClient)
    client_mock.chat_completion.return_value = HermesResponse(
        provider_event_id="event-123",
        model="hermes-model",
        input_tokens=10,
        output_tokens=5,
        content='{"key": "value"}',
        tool_calls=None,
    )
    executor = HermesRunExecutor(client_mock, anything_mock)

    await executor.execute(create_hermes_job(), idempotency_key="run:test")

    assert client_mock.chat_completion.call_args.kwargs["tools"] is None
    anything_mock.query_workspace.assert_not_called()


@pytest.mark.asyncio
async def test_hermes_executor_fails_on_http_status_error(anything_mock) -> None:
    client_mock = AsyncMock(spec=HermesClient)
    # Simula um erro HTTP 503 do Hermes
    request = httpx.Request("POST", "http://hermes/chat")
    response = httpx.Response(503, request=request)
    client_mock.chat_completion.side_effect = httpx.HTTPStatusError(
        "Service Unavailable", request=request, response=response
    )

    executor = HermesRunExecutor(client_mock, anything_mock)
    run = create_hermes_job()

    with pytest.raises(HermesExecutionError, match="PROVIDER_ERROR"):
        await executor.execute(run, idempotency_key=run.effect_key)


@pytest.mark.asyncio
async def test_hermes_executor_fails_on_http_request_error(anything_mock) -> None:
    client_mock = AsyncMock(spec=HermesClient)
    # Simula erro de conexão/resolução de DNS
    client_mock.chat_completion.side_effect = httpx.ConnectError("Connection timed out")

    executor = HermesRunExecutor(client_mock, anything_mock)
    run = create_hermes_job()

    with pytest.raises(HermesExecutionError, match="CONNECTIVITY_FAILED"):
        await executor.execute(run, idempotency_key=run.effect_key)


@pytest.mark.asyncio
async def test_hermes_executor_fails_on_timeout_error(anything_mock) -> None:
    client_mock = AsyncMock(spec=HermesClient)
    client_mock.chat_completion.side_effect = TimeoutError()

    executor = HermesRunExecutor(client_mock, anything_mock)
    run = create_hermes_job()

    with pytest.raises(HermesExecutionError, match="TIMEOUT"):
        await executor.execute(run, idempotency_key=run.effect_key)
