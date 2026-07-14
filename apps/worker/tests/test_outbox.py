import asyncio
import json
from uuid import UUID

import pytest
from bighead_worker.outbox import OutboxEvent, dispatch_outbox

EVENT_ID = UUID("10000000-0000-0000-0000-000000000001")
ORG_ID = UUID("20000000-0000-0000-0000-000000000001")


def event(attempts: int = 1) -> OutboxEvent:
    return OutboxEvent(
        id=EVENT_ID,
        organization_id=ORG_ID,
        event_type="tasks.created",
        aggregate_type="task",
        aggregate_id=UUID("30000000-0000-0000-0000-000000000001"),
        payload={"taskId": "task-1"},
        attempts=attempts,
        lease_token=UUID("40000000-0000-0000-0000-000000000001"),
    )


class ConcurrentStore:
    def __init__(self, item: OutboxEvent) -> None:
        self.item = item
        self.lock = asyncio.Lock()
        self.leased = False
        self.acked = 0
        self.nacked = 0
        self.dead_lettered = False

    async def claim(self, worker: str, limit: int, lease_seconds: int) -> list[OutboxEvent]:
        async with self.lock:
            if self.leased:
                return []
            self.leased = True
            return [self.item]

    async def ack(self, event_id: UUID, worker: str, lease_token: UUID) -> bool:
        assert lease_token == self.item.lease_token
        self.acked += 1
        return True

    async def nack(
        self, event_id: UUID, worker: str, lease_token: UUID, error: str, max_attempts: int
    ) -> bool:
        assert lease_token == self.item.lease_token
        self.nacked += 1
        self.dead_lettered = self.item.attempts >= max_attempts
        return True


class Publisher:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.messages: list[tuple[str, str]] = []

    async def publish(self, channel: str, payload: str) -> None:
        if self.fail:
            raise ConnectionError("redis unavailable")
        self.messages.append((channel, payload))


@pytest.mark.asyncio
async def test_concurrent_dispatchers_publish_claimed_event_once() -> None:
    store = ConcurrentStore(event())
    publisher = Publisher()
    results = await asyncio.gather(
        dispatch_outbox(store, publisher, worker="worker-a"),
        dispatch_outbox(store, publisher, worker="worker-b"),
    )
    assert sum(result[0] for result in results) == 1
    assert store.acked == 1
    assert len(publisher.messages) == 1
    assert json.loads(publisher.messages[0][1])["id"] == str(EVENT_ID)


@pytest.mark.asyncio
async def test_failed_publish_is_nacked_and_dead_lettered_at_limit() -> None:
    store = ConcurrentStore(event(attempts=8))
    published, failed = await dispatch_outbox(
        store, Publisher(fail=True), worker="worker-a", max_attempts=8
    )
    assert (published, failed) == (0, 1)
    assert store.nacked == 1
    assert store.dead_lettered is True
