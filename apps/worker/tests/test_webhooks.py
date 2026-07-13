import hashlib
import hmac
import json
from dataclasses import dataclass, field
from uuid import UUID, uuid4

import httpx
import pytest
from bighead_worker.webhooks import (
    WebhookDelivery,
    _resolve_public_destination,
    dispatch_webhooks,
)


@dataclass
class Store:
    deliveries: list[WebhookDelivery]
    secret: str = "tenant-secret"
    acked: list[UUID] = field(default_factory=list)
    nacked: list[tuple[UUID, int | None]] = field(default_factory=list)

    async def claim(self, worker: str, limit: int, lease_seconds: int) -> list[WebhookDelivery]:
        return self.deliveries[:limit]

    async def resolve_secret(self, reference: str) -> str:
        assert reference == "vault/webhook-a"
        return self.secret

    async def ack(
        self, delivery_id: UUID, worker: str, response_status: int, body_hash: str
    ) -> bool:
        assert response_status == 204
        assert body_hash == hashlib.sha256(b"").hexdigest()
        self.acked.append(delivery_id)
        return True

    async def nack(
        self,
        delivery_id: UUID,
        worker: str,
        error: str,
        response_status: int | None,
        max_attempts: int,
    ) -> bool:
        self.nacked.append((delivery_id, response_status))
        return True


@dataclass
class Sender:
    status: int = 204
    calls: list[tuple[dict[str, str], bytes]] = field(default_factory=list)

    async def send(self, url: str, headers: dict[str, str], body: bytes) -> httpx.Response:
        assert url == "https://hooks.example.test/events"
        self.calls.append((headers, body))
        return httpx.Response(
            self.status,
            request=httpx.Request("POST", url),
        )


def delivery() -> WebhookDelivery:
    return WebhookDelivery(
        id=uuid4(),
        organization_id=uuid4(),
        endpoint_id=uuid4(),
        event_id=uuid4(),
        url="https://hooks.example.test/events",
        secret_reference="vault/webhook-a",
        event_type="task.updated",
        aggregate_type="task",
        aggregate_id=uuid4(),
        payload={"status": "done"},
        attempts=1,
    )


@pytest.mark.asyncio
async def test_delivery_is_signed_and_idempotently_identified() -> None:
    item = delivery()
    store = Store([item])
    sender = Sender()

    assert await dispatch_webhooks(store, sender, worker="worker-a") == (1, 0)
    assert store.acked == [item.id]
    headers, body = sender.calls[0]
    timestamp = headers["X-BigHead-Timestamp"]
    expected = hmac.new(
        store.secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256
    ).hexdigest()
    assert headers["X-BigHead-Signature"] == f"sha256={expected}"
    assert headers["X-BigHead-Event-Id"] == str(item.event_id)
    assert headers["Idempotency-Key"] == str(item.event_id)
    assert json.loads(body)["id"] == str(item.event_id)


@pytest.mark.asyncio
async def test_failed_delivery_is_nacked_for_database_retry() -> None:
    item = delivery()
    store = Store([item])
    sender = Sender(status=503)

    assert await dispatch_webhooks(store, sender, worker="worker-a") == (0, 1)
    assert store.acked == []
    assert store.nacked == [(item.id, 503)]


@pytest.mark.asyncio
async def test_ssrf_guard_rejects_any_private_dns_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "bighead_worker.webhooks.socket.getaddrinfo",
        lambda *args, **kwargs: [
            (2, 1, 6, "", ("93.184.216.34", 443)),
            (2, 1, 6, "", ("127.0.0.1", 443)),
        ],
    )
    with pytest.raises(ValueError, match="non-public"):
        await _resolve_public_destination("https://hooks.example.test/events")


@pytest.mark.asyncio
async def test_ssrf_guard_returns_the_ip_that_transport_must_pin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "bighead_worker.webhooks.socket.getaddrinfo",
        lambda *args, **kwargs: [(2, 1, 6, "", ("93.184.216.34", 443))],
    )
    assert await _resolve_public_destination("https://hooks.example.test/events?attempt=1") == (
        "hooks.example.test",
        "93.184.216.34",
        443,
        "/events?attempt=1",
    )
