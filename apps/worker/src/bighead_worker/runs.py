import asyncio
import hashlib
import json
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

import httpx


@dataclass(frozen=True)
class RunJob:
    id: UUID
    organization_id: UUID
    task_id: UUID
    workflow_version_id: UUID | None
    attempt: int
    max_attempts: int
    retry_backoff_seconds: int
    policy_snapshot: dict[str, Any]

    @property
    def policy(self) -> RunPolicy:
        return RunPolicy.from_job(self)

    @property
    def effect_key(self) -> str:
        # Stable across lease recovery. The provider adapter must forward this
        # value as its idempotency key so a crash after the remote call is safe.
        return f"run:{self.id}:primary"

    @property
    def request_fingerprint(self) -> str:
        payload = json.dumps(
            {
                "organizationId": str(self.organization_id),
                "taskId": str(self.task_id),
                "workflowVersionId": (
                    str(self.workflow_version_id) if self.workflow_version_id else None
                ),
                "policy": self.policy_snapshot,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()


@dataclass(frozen=True)
class ProviderResult:
    provider_event_id: str
    amount: Decimal = Decimal("0")
    currency: str = "USD"


@dataclass(frozen=True)
class RunPolicy:
    """Immutable execution policy captured when the run is enqueued."""

    timeout_seconds: int
    max_attempts: int
    retry_backoff_seconds: int

    @classmethod
    def from_job(cls, run: RunJob) -> RunPolicy:
        snapshot = run.policy_snapshot
        timeout = snapshot.get("timeoutSeconds", 60)
        max_attempts = snapshot.get("maxAttempts", run.max_attempts)
        backoff = snapshot.get("retryBackoffSeconds", run.retry_backoff_seconds)
        values = (timeout, max_attempts, backoff)
        if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
            raise ValueError("run policy values must be integers")
        if not 1 <= timeout <= 3600:
            raise ValueError("run policy timeoutSeconds must be between 1 and 3600")
        if not 1 <= max_attempts <= 11:
            raise ValueError("run policy maxAttempts must be between 1 and 11")
        if not 1 <= backoff <= 3600:
            raise ValueError("run policy retryBackoffSeconds must be between 1 and 3600")
        if max_attempts != run.max_attempts or backoff != run.retry_backoff_seconds:
            raise ValueError("run policy snapshot does not match persisted retry columns")
        return cls(timeout, max_attempts, backoff)


class RunStore(Protocol):
    async def claim(self, worker: str, limit: int, lease_seconds: int) -> list[RunJob]: ...

    async def heartbeat(self, run: RunJob, worker: str, lease_seconds: int) -> bool: ...

    async def register_effect(self, run: RunJob, worker: str) -> bool: ...

    async def complete(self, run: RunJob, worker: str, result: ProviderResult) -> bool: ...

    async def fail(self, run: RunJob, worker: str, error: str) -> str: ...


class RunExecutor(Protocol):
    async def execute(self, run: RunJob, *, idempotency_key: str) -> ProviderResult:
        """Execute the provider call, forwarding idempotency_key unchanged."""
        ...


@dataclass
class HttpRunExecutor:
    endpoint: str
    api_key: str = field(repr=False)
    timeout_seconds: int = 60
    transport: httpx.AsyncBaseTransport | None = field(default=None, repr=False)

    async def execute(self, run: RunJob, *, idempotency_key: str) -> ProviderResult:
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds, transport=self.transport
        ) as client:
            response = await client.post(
                self.endpoint,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "Idempotency-Key": idempotency_key,
                },
                json={
                    "runId": str(run.id),
                    "organizationId": str(run.organization_id),
                    "taskId": str(run.task_id),
                    "workflowVersionId": (
                        str(run.workflow_version_id) if run.workflow_version_id else None
                    ),
                    "attempt": run.attempt,
                    "policy": run.policy_snapshot,
                },
            )
        response.raise_for_status()
        payload = response.json()
        provider_event_id = payload.get("providerEventId")
        if not isinstance(provider_event_id, str) or not provider_event_id.strip():
            raise ValueError("provider response requires providerEventId")
        try:
            amount = Decimal(str(payload.get("amount", "0")))
        except Exception as exc:
            raise ValueError("provider response amount is invalid") from exc
        currency = payload.get("currency", "USD")
        if not isinstance(currency, str) or len(currency.strip()) != 3:
            raise ValueError("provider response currency must have three letters")
        return ProviderResult(provider_event_id.strip(), amount, currency.upper())


@dataclass
class SupabaseRunStore:
    base_url: str
    secret_key: str

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.secret_key}",
            "apikey": self.secret_key,
            "Content-Type": "application/json",
        }

    async def claim(self, worker: str, limit: int, lease_seconds: int) -> list[RunJob]:
        rows = await self._rpc(
            "claim_runs",
            {"p_worker": worker, "p_limit": limit, "p_lease_seconds": lease_seconds},
        )
        return [
            RunJob(
                id=UUID(row["id"]),
                organization_id=UUID(row["organization_id"]),
                task_id=UUID(row["task_id"]),
                workflow_version_id=(
                    UUID(row["workflow_version_id"]) if row["workflow_version_id"] else None
                ),
                attempt=int(row["attempt"]),
                max_attempts=int(row["max_attempts"]),
                retry_backoff_seconds=int(row["retry_backoff_seconds"]),
                policy_snapshot=row.get("policy_snapshot") or {},
            )
            for row in rows
        ]

    async def register_effect(self, run: RunJob, worker: str) -> bool:
        return bool(
            await self._rpc(
                "register_run_effect",
                {
                    "p_run_id": str(run.id),
                    "p_worker": worker,
                    "p_effect_key": run.effect_key,
                    "p_effect_type": "provider.call",
                    "p_request_fingerprint": run.request_fingerprint,
                },
            )
        )

    async def heartbeat(self, run: RunJob, worker: str, lease_seconds: int) -> bool:
        return bool(
            await self._rpc(
                "heartbeat_run",
                {
                    "p_id": str(run.id),
                    "p_worker": worker,
                    "p_lease_seconds": lease_seconds,
                },
            )
        )

    async def complete(self, run: RunJob, worker: str, result: ProviderResult) -> bool:
        return bool(
            await self._rpc(
                "complete_run",
                {
                    "p_id": str(run.id),
                    "p_worker": worker,
                    "p_effect_key": run.effect_key,
                    "p_provider_event_id": result.provider_event_id,
                    "p_amount": str(result.amount),
                    "p_currency": result.currency,
                },
            )
        )

    async def fail(self, run: RunJob, worker: str, error: str) -> str:
        return str(
            await self._rpc(
                "fail_run",
                {"p_id": str(run.id), "p_worker": worker, "p_error": error[:2000]},
            )
        )

    async def _rpc(self, function: str, payload: dict[str, Any]) -> Any:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url}/rest/v1/rpc/{function}",
                headers=self._headers(),
                json=payload,
            )
        response.raise_for_status()
        return response.json()


async def dispatch_runs(
    store: RunStore,
    executor: RunExecutor,
    *,
    worker: str,
    limit: int = 10,
    lease_seconds: int = 60,
) -> tuple[int, int]:
    completed = failed = 0
    for run in await store.claim(worker, limit, lease_seconds):
        try:
            policy = run.policy
            # A false result means a previous delivery reserved this effect. We
            # deliberately retry the provider with the same key: a compliant
            # provider returns the original result without applying it twice.
            await store.register_effect(run, worker)
            try:
                async with asyncio.timeout(policy.timeout_seconds) as timeout_scope:
                    result = await _execute_with_heartbeat(
                        store,
                        executor,
                        run,
                        worker=worker,
                        lease_seconds=lease_seconds,
                    )
            except TimeoutError:
                if timeout_scope.expired():
                    raise TimeoutError(
                        f"run exceeded skill timeout of {policy.timeout_seconds}s"
                    ) from None
                raise
            if not await store.complete(run, worker, result):
                raise RuntimeError("run lease was lost before completion")
            completed += 1
        except Exception as exc:
            try:
                await store.fail(run, worker, f"{type(exc).__name__}: {exc}")
            except Exception:
                # Lease recovery is authoritative when this worker no longer
                # owns the run; do not hide the original execution failure.
                pass
            failed += 1
    return completed, failed


async def _execute_with_heartbeat(
    store: RunStore,
    executor: RunExecutor,
    run: RunJob,
    *,
    worker: str,
    lease_seconds: int,
) -> ProviderResult:
    async def maintain_lease() -> None:
        interval = max(1.0, min(30.0, lease_seconds / 3))
        while True:
            await asyncio.sleep(interval)
            if not await store.heartbeat(run, worker, lease_seconds):
                raise RuntimeError("run lease was lost during provider execution")

    execution = asyncio.create_task(executor.execute(run, idempotency_key=run.effect_key))
    heartbeat = asyncio.create_task(maintain_lease())
    try:
        done, _ = await asyncio.wait(
            {execution, heartbeat}, return_when=asyncio.FIRST_COMPLETED
        )
        if execution in done:
            return await execution
        await heartbeat
        raise RuntimeError("run lease heartbeat stopped unexpectedly")
    finally:
        for task in (execution, heartbeat):
            if not task.done():
                task.cancel()
        await asyncio.gather(execution, heartbeat, return_exceptions=True)
