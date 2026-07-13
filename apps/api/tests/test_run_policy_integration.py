import json
import os
from uuid import uuid4

import asyncpg  # type: ignore[import-untyped]
import pytest
from bighead_api.governance.run_policy import resolve_run_policy

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        os.getenv("BIGHEAD_RUN_SUPABASE_INTEGRATION") != "1",
        reason="requires the local Supabase stack",
    ),
]


async def test_skill_policy_snapshot_drives_backoff_and_dead_letter() -> None:
    conn = await asyncpg.connect(os.environ["SUPABASE_INTEGRATION_DATABASE_URL"])
    transaction = conn.transaction()
    await transaction.start()
    organization_id, workflow_id, workflow_version_id = uuid4(), uuid4(), uuid4()
    skill_id, task_id, run_id = uuid4(), uuid4(), uuid4()
    try:
        await conn.execute(
            "insert into public.organizations(id,name,slug) values($1,'Policy integration',$2)",
            organization_id,
            f"policy-{organization_id}",
        )
        await conn.execute(
            """insert into public.skills(
                 id,organization_id,name,slug,timeout_seconds,max_retries)
               values($1,$2,'Provider lookup','provider-lookup',7,1)""",
            skill_id,
            organization_id,
        )
        await conn.execute(
            """insert into public.workflows(id,organization_id,name,slug)
               values($1,$2,'Policy','policy')""",
            workflow_id,
            organization_id,
        )
        await conn.execute(
            """insert into public.workflow_versions(
                 id,organization_id,workflow_id,version,definition,published_at)
               values($1,$2,$3,1,$4::jsonb,now())""",
            workflow_version_id,
            organization_id,
            workflow_id,
            json.dumps({"nodes": [{"id": "provider", "skillId": str(skill_id)}]}),
        )
        policy = await resolve_run_policy(conn, organization_id, workflow_version_id)
        assert policy.timeout_seconds == 7
        assert policy.max_attempts == 2
        await conn.execute(
            """insert into public.tasks(id,organization_id,title,objective,workflow_version_id)
               values($1,$2,'Policy run','exercise retry policy',$3)""",
            task_id,
            organization_id,
            workflow_version_id,
        )
        await conn.execute(
            """insert into public.runs(
                 id,organization_id,task_id,workflow_version_id,idempotency_key,
                 max_attempts,retry_backoff_seconds,policy_snapshot,available_at)
               values($1,$2,$3,$4,'policy-integration',$5,$6,$7::jsonb,'1900-01-01')""",
            run_id,
            organization_id,
            task_id,
            workflow_version_id,
            policy.max_attempts,
            policy.retry_backoff_seconds,
            json.dumps(policy.snapshot),
        )

        await conn.execute("set local role service_role")
        claimed = await conn.fetchrow("select * from public.claim_runs('policy-worker',1,60)")
        assert claimed is not None and claimed["attempt"] == 1
        first_status = await conn.fetchval(
            "select public.fail_run($1,'policy-worker','timeout')::text", run_id
        )
        assert first_status == "queued"
        first = await conn.fetchrow(
            "select available_at>now(),error_code from public.runs where id=$1", run_id
        )
        assert first is not None and first[0] is True and first["error_code"] == "retry_scheduled"

        await conn.execute("update public.runs set available_at='1900-01-01' where id=$1", run_id)
        claimed = await conn.fetchrow("select * from public.claim_runs('policy-worker',1,60)")
        assert claimed is not None and claimed["attempt"] == 2
        final_status = await conn.fetchval(
            "select public.fail_run($1,'policy-worker','timeout')::text", run_id
        )
        assert final_status == "dead_letter"
        final = await conn.fetchrow(
            "select error_code,finished_at is not null from public.runs where id=$1", run_id
        )
        assert final is not None and final["error_code"] == "retry_exhausted" and final[1] is True
    finally:
        await transaction.rollback()
        await conn.close()
