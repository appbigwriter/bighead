import asyncio
from decimal import Decimal
from uuid import UUID

import httpx
import pytest
from bighead_worker.jobs import dispatch_runs_job
from bighead_worker.llm_gateway import LlmResult, MultiProviderRouter
from bighead_worker.main import WorkerAppSettings
from bighead_worker.runs import (
    HttpRunExecutor,
    LlmRunExecutor,
    ProviderResult,
    RunJob,
    dispatch_runs,
)

RUN_ID = UUID("71000000-0000-0000-0000-000000000001")
ORG_ID = UUID("72000000-0000-0000-0000-000000000001")
TASK_ID = UUID("73000000-0000-0000-0000-000000000001")


def job(attempt: int = 1) -> RunJob:
    return RunJob(
        id=RUN_ID,
        organization_id=ORG_ID,
        task_id=TASK_ID,
        workflow_version_id=None,
        attempt=attempt,
        max_attempts=3,
        retry_backoff_seconds=7,
        policy_snapshot={
            "timeoutSeconds": 30,
            "maxAttempts": 3,
            "retryBackoffSeconds": 7,
        },
    )


class Store:
    def __init__(self, runs: list[RunJob], *, reserved: bool = True) -> None:
        self.runs = runs
        self.reserved = reserved
        self.completed = 0
        self.failures: list[str] = []
        self.heartbeats = 0

    async def claim(self, worker: str, limit: int, lease_seconds: int) -> list[RunJob]:
        return self.runs[:limit]

    async def register_effect(self, run: RunJob, worker: str) -> bool:
        return self.reserved

    async def heartbeat(self, run: RunJob, worker: str, lease_seconds: int) -> bool:
        self.heartbeats += 1
        return True

    async def complete(self, run: RunJob, worker: str, result: ProviderResult) -> bool:
        self.completed += 1
        return True

    async def fail(self, run: RunJob, worker: str, error: str) -> str:
        self.failures.append(error)
        return "queued"


class IdempotentProvider:
    def __init__(self) -> None:
        self.effects: dict[str, ProviderResult] = {}
        self.calls: list[str] = []

    async def execute(self, run: RunJob, *, idempotency_key: str) -> ProviderResult:
        self.calls.append(idempotency_key)
        return self.effects.setdefault(
            idempotency_key,
            ProviderResult("provider-event-1", Decimal("1.25"), "USD"),
        )


@pytest.mark.asyncio
async def test_replayed_delivery_uses_stable_provider_key_and_one_external_effect() -> None:
    provider = IdempotentProvider()
    first = Store([job()])
    replay = Store([job(attempt=2)], reserved=False)

    assert await dispatch_runs(first, provider, worker="worker-a") == (1, 0)
    assert await dispatch_runs(replay, provider, worker="worker-b") == (1, 0)

    assert provider.calls == [f"run:{RUN_ID}:primary", f"run:{RUN_ID}:primary"]
    assert len(provider.effects) == 1
    assert first.completed == replay.completed == 1


class FailingProvider:
    async def execute(self, run: RunJob, *, idempotency_key: str) -> ProviderResult:
        raise TimeoutError("provider timeout")


@pytest.mark.asyncio
async def test_provider_timeout_is_returned_to_database_retry_policy() -> None:
    store = Store([job()])

    assert await dispatch_runs(store, FailingProvider(), worker="worker-a") == (0, 1)
    assert len(store.failures) == 1
    assert "TimeoutError: provider timeout" in store.failures[0]
    assert store.completed == 0


@pytest.mark.asyncio
async def test_dispatcher_enforces_skill_timeout_snapshot() -> None:
    class SlowProvider:
        async def execute(self, run: RunJob, *, idempotency_key: str) -> ProviderResult:
            await asyncio.sleep(2)
            return ProviderResult("too-late")

    run = job()
    run = RunJob(
        **{
            **run.__dict__,
            "policy_snapshot": {
                **run.policy_snapshot,
                "timeoutSeconds": 1,
            },
        }
    )
    store = Store([run])

    assert await dispatch_runs(store, SlowProvider(), worker="worker-timeout") == (0, 1)
    assert store.failures == ["TimeoutError: run exceeded skill timeout of 1s"]


@pytest.mark.asyncio
async def test_invalid_or_drifted_policy_fails_closed_before_provider_effect() -> None:
    provider = IdempotentProvider()
    drifted = RunJob(
        **{
            **job().__dict__,
            "policy_snapshot": {
                "timeoutSeconds": 30,
                "maxAttempts": 4,
                "retryBackoffSeconds": 7,
            },
        }
    )
    store = Store([drifted])

    assert await dispatch_runs(store, provider, worker="worker-policy") == (0, 1)
    assert provider.calls == []
    assert "does not match persisted retry columns" in store.failures[0]


@pytest.mark.asyncio
async def test_lost_lease_cancels_slow_provider_before_external_completion() -> None:
    class LeaseLostStore(Store):
        async def heartbeat(self, run: RunJob, worker: str, lease_seconds: int) -> bool:
            self.heartbeats += 1
            return False

    class SlowProvider:
        completed = False

        async def execute(self, run: RunJob, *, idempotency_key: str) -> ProviderResult:
            await asyncio.sleep(2)
            self.completed = True
            return ProviderResult("too-late")

    store = LeaseLostStore([job()])
    provider = SlowProvider()

    assert await dispatch_runs(store, provider, worker="worker-lease", lease_seconds=1) == (0, 1)
    assert provider.completed is False
    assert store.heartbeats == 1
    assert "lease was lost during provider execution" in store.failures[0]


def test_fingerprint_is_stable_across_lease_recovery_attempts() -> None:
    assert job(attempt=1).request_fingerprint == job(attempt=3).request_fingerprint


@pytest.mark.asyncio
async def test_cron_fails_closed_before_claim_when_provider_is_not_configured() -> None:
    class NeverClaimStore:
        async def claim(self, worker: str, limit: int, lease_seconds: int) -> list[RunJob]:
            raise AssertionError("a disabled provider must not claim runs")

    class Settings:
        queue_name = "test"
        job_lease_seconds = 60

    with pytest.raises(RuntimeError, match="adapter is not configured"):
        await dispatch_runs_job({"settings": Settings(), "run_store": NeverClaimStore()})


def test_run_dispatcher_is_registered_with_worker() -> None:
    assert dispatch_runs_job in WorkerAppSettings.functions
    assert any(job.coroutine is dispatch_runs_job for job in WorkerAppSettings.cron_jobs)


@pytest.mark.asyncio
async def test_http_executor_forwards_stable_idempotency_contract() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"providerEventId": "provider-42", "amount": "0.75", "currency": "brl"},
        )

    executor = HttpRunExecutor(
        "https://provider.example/runs",
        "server-secret",
        transport=httpx.MockTransport(handler),
    )
    result = await executor.execute(job(), idempotency_key=job().effect_key)
    assert result == ProviderResult("provider-42", Decimal("0.75"), "BRL")
    assert requests[0].headers["Idempotency-Key"] == job().effect_key
    assert requests[0].headers["Authorization"] == "Bearer server-secret"
    assert b'"runId"' in requests[0].content


SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "string"}},
    "required": ["answer"],
    "additionalProperties": False,
}


class LlmStub:
    name = "openai"
    model = "gpt-priced"

    def __init__(self) -> None:
        from bighead_worker.llm_gateway import LlmCapability

        self.capability = LlmCapability()
        self.requests = []

    async def generate(self, request):
        self.requests.append(request)
        return LlmResult("openai", self.model, "response-7", {"answer": "ok"}, 2_000, 500)


def llm_job() -> RunJob:
    run = job()
    return RunJob(
        **{
            **run.__dict__,
            "task_title": "Qualificar lead",
            "task_objective": "Criar proxima acao",
            "task_metadata": {"source": "crm"},
            "agent_id": UUID("74000000-0000-0000-0000-000000000001"),
            "agent_name": "SDR",
            "agent_enabled": True,
            "agent_version_id": UUID("75000000-0000-0000-0000-000000000001"),
            "system_prompt": "Responda com JSON.",
            "output_schema": SCHEMA,
            "model_prices": {
                "gpt-priced": {
                    "modelId": "76000000-0000-0000-0000-000000000001",
                    "inputCostPerMillion": "5",
                    "outputCostPerMillion": "15",
                }
            },
        }
    )


@pytest.mark.asyncio
async def test_internal_llm_executor_uses_run_context_schema_idempotency_and_prices() -> None:
    adapter = LlmStub()
    executor = LlmRunExecutor(MultiProviderRouter(adapter))  # type: ignore[arg-type]
    run = llm_job()

    result = await executor.execute(run, idempotency_key=run.effect_key)

    assert result == ProviderResult(
        "llm:openai:response-7",
        Decimal("0.017500"),
        "USD",
        2_000,
        500,
        UUID("76000000-0000-0000-0000-000000000001"),
    )
    assert adapter.requests[0].idempotency_key == run.effect_key
    assert adapter.requests[0].schema == SCHEMA
    assert '"objective":"Criar proxima acao"' in adapter.requests[0].prompt


@pytest.mark.asyncio
async def test_internal_llm_executor_fails_closed_without_published_prompt_or_schema() -> None:
    adapter = LlmStub()
    executor = LlmRunExecutor(MultiProviderRouter(adapter))  # type: ignore[arg-type]
    run = llm_job()
    invalid = RunJob(**{**run.__dict__, "agent_version_id": None, "system_prompt": ""})

    with pytest.raises(ValueError, match="published agent system prompt"):
        await executor.execute(invalid, idempotency_key=invalid.effect_key)
    assert adapter.requests == []


@pytest.mark.asyncio
async def test_internal_llm_executor_fails_before_provider_when_price_is_missing() -> None:
    adapter = LlmStub()
    executor = LlmRunExecutor(MultiProviderRouter(adapter))  # type: ignore[arg-type]
    run = llm_job()
    unpriced = RunJob(**{**run.__dict__, "model_prices": {}})

    with pytest.raises(ValueError, match="pinned tenant pricing"):
        await executor.execute(unpriced, idempotency_key=unpriced.effect_key)
    assert adapter.requests == []
