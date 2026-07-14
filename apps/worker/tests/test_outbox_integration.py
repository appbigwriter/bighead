import json
import os
from uuid import uuid4

import asyncpg
import pytest
from bighead_worker.outbox import RedisEventPublisher, SupabaseOutboxStore, dispatch_outbox
from redis.asyncio import Redis

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        os.getenv("BIGHEAD_RUN_OUTBOX_INTEGRATION") != "1",
        reason="real Supabase/Redis outbox smoke is opt-in",
    ),
]


async def test_real_rpc_stream_reconnect_and_event_deduplication() -> None:
    database_url = os.environ["SUPABASE_INTEGRATION_DATABASE_URL"]
    supabase_url = os.environ["SUPABASE_INTEGRATION_URL"].rstrip("/")
    secret_key = os.environ["SUPABASE_INTEGRATION_SECRET_KEY"]
    redis_url = os.environ["REDIS_URL"]
    organization_id = uuid4()
    event_id = uuid4()
    aggregate_id = uuid4()
    worker = f"integration-{uuid4()}"
    channel = f"bighead:events:{organization_id}"
    stream_ids: list[str] = []

    database = await asyncpg.connect(database_url)
    redis = Redis.from_url(redis_url, decode_responses=True)
    try:
        await database.execute(
            "insert into public.organizations(id,name,slug) values($1,$2,$3)",
            organization_id,
            "Outbox integration smoke",
            f"outbox-smoke-{organization_id}",
        )
        await database.execute(
            """insert into public.event_outbox(
                 id,organization_id,event_type,aggregate_type,aggregate_id,payload,available_at
               ) values($1,$2,'tasks.created','task',$3,$4::jsonb,'2000-01-01T00:00:00Z')""",
            event_id,
            organization_id,
            aggregate_id,
            json.dumps({"source": "integration-smoke"}),
        )
        store = SupabaseOutboxStore(base_url=supabase_url, secret_key=secret_key)
        published, failed = await dispatch_outbox(
            store,
            RedisEventPublisher(redis),
            worker=worker,
            limit=1,
            lease_seconds=30,
        )
        assert (published, failed) == (1, 0)
        row = await database.fetchrow(
            "select published_at,attempts from public.event_outbox where id=$1", event_id
        )
        assert row is not None and row["published_at"] is not None and row["attempts"] == 1
        lease_token = await database.fetchval(
            "select lease_token from public.event_outbox where id=$1", event_id
        )
        assert lease_token is None

        await redis.aclose()
        redis = Redis.from_url(redis_url, decode_responses=True)
        entries = await redis.xrange(channel, min="-", max="+")
        matching = []
        for stream_id, fields in entries:
            envelope = json.loads(fields["event"])
            if envelope["id"] == str(event_id):
                matching.append(envelope)
                stream_ids.append(stream_id)
        assert len(matching) == 1
        assert matching[0]["organizationId"] == str(organization_id)
    finally:
        if stream_ids:
            await redis.xdel(channel, *stream_ids)
        await redis.aclose()
        await database.execute("delete from public.organizations where id=$1", organization_id)
        await database.close()
