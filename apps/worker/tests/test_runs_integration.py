import os
from dataclasses import dataclass
from decimal import Decimal
from uuid import uuid4

import asyncpg
import pytest
from bighead_worker.runs import ProviderResult, RunJob, SupabaseRunStore, dispatch_runs

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        os.getenv("BIGHEAD_RUN_RUNS_INTEGRATION") != "1",
        reason="real Supabase run dispatcher smoke is opt-in",
    ),
]


@dataclass
class DeterministicIntegrationExecutor:
    provider_event_id: str
    keys: list[str]

    async def execute(self, run: RunJob, *, idempotency_key: str) -> ProviderResult:
        self.keys.append(idempotency_key)
        return ProviderResult(self.provider_event_id, Decimal("2.50"), "USD")


async def test_real_postgrest_rpc_claim_dispatch_completion_and_cost() -> None:
    database_url = os.environ["SUPABASE_INTEGRATION_DATABASE_URL"]
    supabase_url = os.environ["SUPABASE_INTEGRATION_URL"].rstrip("/")
    secret_key = os.environ["SUPABASE_INTEGRATION_SECRET_KEY"]
    organization_id, task_id, run_id = uuid4(), uuid4(), uuid4()
    provider_event_id = f"integration-provider-{uuid4()}"
    worker = f"integration-runs-{uuid4()}"
    database = await asyncpg.connect(database_url)
    try:
        await database.execute(
            "insert into public.organizations(id,name,slug) values($1,$2,$3)",
            organization_id,
            "Run dispatcher integration",
            f"run-dispatch-{organization_id}",
        )
        await database.execute(
            """insert into public.tasks(id,organization_id,title,objective)
               values($1,$2,'RPC dispatcher','integration')""",
            task_id,
            organization_id,
        )
        await database.execute(
            """insert into public.runs(
                 id,organization_id,task_id,idempotency_key,available_at,created_at
               ) values($1,$2,$3,$4,'1900-01-01T00:00:00Z','1900-01-01T00:00:00Z')""",
            run_id,
            organization_id,
            task_id,
            f"integration-{run_id}",
        )
        executor = DeterministicIntegrationExecutor(provider_event_id, [])
        result = await dispatch_runs(
            SupabaseRunStore(base_url=supabase_url, secret_key=secret_key),
            executor,
            worker=worker,
            limit=1,
            lease_seconds=60,
        )
        assert result == (1, 0)
        assert executor.keys == [f"run:{run_id}:primary"]
        row = await database.fetchrow(
            "select status::text,locked_by,locked_until from public.runs where id=$1", run_id
        )
        assert row is not None and row["status"] == "succeeded"
        assert row["locked_by"] is None and row["locked_until"] is None
        cost = await database.fetchrow(
            "select amount,currency from public.cost_events where provider_event_id=$1",
            provider_event_id,
        )
        assert cost is not None and cost["amount"] == Decimal("2.50")
        assert cost["currency"].strip() == "USD"
    finally:
        await database.execute("delete from public.organizations where id=$1", organization_id)
        await database.close()
