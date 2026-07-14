import json
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

import httpx
from redis.asyncio import Redis


@dataclass(frozen=True)
class OutboxEvent:
    id: UUID
    organization_id: UUID
    event_type: str
    aggregate_type: str
    aggregate_id: UUID
    payload: dict[str, Any]
    attempts: int
    lease_token: UUID


class OutboxStore(Protocol):
    async def claim(self, worker: str, limit: int, lease_seconds: int) -> list[OutboxEvent]: ...
    async def ack(self, event_id: UUID, worker: str, lease_token: UUID) -> bool: ...
    async def nack(
        self, event_id: UUID, worker: str, lease_token: UUID, error: str, max_attempts: int
    ) -> bool: ...


class EventPublisher(Protocol):
    async def publish(self, channel: str, payload: str) -> None: ...


@dataclass
class RedisEventPublisher:
    client: Redis

    async def publish(self, channel: str, payload: str) -> None:
        # A Redis Stream is durable even when no consumer is connected. Consumers
        # deduplicate with the event id embedded in the envelope.
        await self.client.xadd(channel, {"event": payload}, maxlen=100_000, approximate=True)


@dataclass
class SupabaseOutboxStore:
    base_url: str
    secret_key: str

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.secret_key}",
            "apikey": self.secret_key,
            "Content-Type": "application/json",
        }

    async def claim(self, worker: str, limit: int, lease_seconds: int) -> list[OutboxEvent]:
        rows = await self._rpc(
            "claim_event_outbox",
            {
                "p_worker": worker,
                "p_limit": limit,
                "p_lease_seconds": lease_seconds,
            },
        )
        return [
            OutboxEvent(
                id=UUID(row["id"]),
                organization_id=UUID(row["organization_id"]),
                event_type=row["event_type"],
                aggregate_type=row["aggregate_type"],
                aggregate_id=UUID(row["aggregate_id"]),
                payload=row["payload"],
                attempts=int(row["attempts"]),
                lease_token=UUID(row["lease_token"]),
            )
            for row in rows
        ]

    async def ack(self, event_id: UUID, worker: str, lease_token: UUID) -> bool:
        return bool(
            await self._rpc(
                "ack_event_outbox",
                {
                    "p_id": str(event_id),
                    "p_worker": worker,
                    "p_lease_token": str(lease_token),
                },
            )
        )

    async def nack(
        self, event_id: UUID, worker: str, lease_token: UUID, error: str, max_attempts: int
    ) -> bool:
        return bool(
            await self._rpc(
                "nack_event_outbox",
                {
                    "p_id": str(event_id),
                    "p_worker": worker,
                    "p_lease_token": str(lease_token),
                    "p_error": error,
                    "p_max_attempts": max_attempts,
                },
            )
        )

    async def _rpc(self, function: str, payload: dict[str, Any]) -> Any:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{self.base_url}/rest/v1/rpc/{function}",
                headers=self._headers(),
                json=payload,
            )
        response.raise_for_status()
        return response.json()


async def dispatch_outbox(
    store: OutboxStore,
    publisher: EventPublisher,
    *,
    worker: str,
    limit: int = 50,
    lease_seconds: int = 30,
    max_attempts: int = 8,
) -> tuple[int, int]:
    published = failed = 0
    for event in await store.claim(worker, limit, lease_seconds):
        envelope = json.dumps(
            {
                "id": str(event.id),
                "organizationId": str(event.organization_id),
                "type": event.event_type,
                "aggregateType": event.aggregate_type,
                "aggregateId": str(event.aggregate_id),
                "payload": event.payload,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        try:
            await publisher.publish(f"bighead:events:{event.organization_id}", envelope)
            if not await store.ack(event.id, worker, event.lease_token):
                raise RuntimeError("outbox lease was lost before ack")
            published += 1
        except Exception as exc:
            await store.nack(
                event.id,
                worker,
                event.lease_token,
                f"{type(exc).__name__}: {exc}",
                max_attempts,
            )
            failed += 1
    return published, failed
