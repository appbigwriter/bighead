import asyncio
import hashlib
import hmac
import http.client
import ipaddress
import json
import socket
import ssl
import time
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlsplit
from uuid import UUID

import httpx


@dataclass(frozen=True)
class WebhookDelivery:
    id: UUID
    organization_id: UUID
    endpoint_id: UUID
    event_id: UUID
    url: str
    secret_reference: str
    event_type: str
    aggregate_type: str
    aggregate_id: UUID
    payload: dict[str, Any]
    attempts: int


class WebhookStore(Protocol):
    async def claim(self, worker: str, limit: int, lease_seconds: int) -> list[WebhookDelivery]: ...

    async def resolve_secret(self, reference: str) -> str: ...
    async def ack(
        self, delivery_id: UUID, worker: str, response_status: int, body_hash: str
    ) -> bool: ...

    async def nack(
        self,
        delivery_id: UUID,
        worker: str,
        error: str,
        response_status: int | None,
        max_attempts: int,
    ) -> bool: ...


class WebhookSender(Protocol):
    async def send(self, url: str, headers: dict[str, str], body: bytes) -> httpx.Response: ...


@dataclass
class HttpWebhookSender:
    timeout_seconds: float = 10

    async def send(self, url: str, headers: dict[str, str], body: bytes) -> httpx.Response:
        host, ip, port, target = await _resolve_public_destination(url)
        return await asyncio.to_thread(
            _send_pinned_https,
            host,
            ip,
            port,
            target,
            headers,
            body,
            self.timeout_seconds,
            url,
        )


@dataclass
class SupabaseWebhookStore:
    base_url: str
    secret_key: str

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.secret_key}",
            "apikey": self.secret_key,
            "Content-Type": "application/json",
        }

    async def claim(self, worker: str, limit: int, lease_seconds: int) -> list[WebhookDelivery]:
        rows = await self._rpc(
            "claim_webhook_deliveries",
            {"p_worker": worker, "p_limit": limit, "p_lease_seconds": lease_seconds},
        )
        return [
            WebhookDelivery(
                id=UUID(row["id"]),
                organization_id=UUID(row["organization_id"]),
                endpoint_id=UUID(row["endpoint_id"]),
                event_id=UUID(row["event_id"]),
                url=row["url"],
                secret_reference=row["secret_reference"],
                event_type=row["event_type"],
                aggregate_type=row["aggregate_type"],
                aggregate_id=UUID(row["aggregate_id"]),
                payload=row["payload"],
                attempts=int(row["attempts"]),
            )
            for row in rows
        ]

    async def resolve_secret(self, reference: str) -> str:
        return str(await self._rpc("resolve_webhook_secret", {"p_reference": reference}))

    async def ack(
        self, delivery_id: UUID, worker: str, response_status: int, body_hash: str
    ) -> bool:
        return bool(
            await self._rpc(
                "ack_webhook_delivery",
                {
                    "p_id": str(delivery_id),
                    "p_worker": worker,
                    "p_response_status": response_status,
                    "p_response_body_hash": body_hash,
                },
            )
        )

    async def nack(
        self,
        delivery_id: UUID,
        worker: str,
        error: str,
        response_status: int | None,
        max_attempts: int,
    ) -> bool:
        return bool(
            await self._rpc(
                "nack_webhook_delivery",
                {
                    "p_id": str(delivery_id),
                    "p_worker": worker,
                    "p_error": error,
                    "p_response_status": response_status,
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


async def dispatch_webhooks(
    store: WebhookStore,
    sender: WebhookSender,
    *,
    worker: str,
    limit: int = 25,
    lease_seconds: int = 30,
    max_attempts: int = 8,
) -> tuple[int, int]:
    delivered = failed = 0
    for delivery in await store.claim(worker, limit, lease_seconds):
        response_status: int | None = None
        try:
            secret = await store.resolve_secret(delivery.secret_reference)
            timestamp = str(int(time.time()))
            body = json.dumps(
                {
                    "id": str(delivery.event_id),
                    "type": delivery.event_type,
                    "organizationId": str(delivery.organization_id),
                    "aggregateType": delivery.aggregate_type,
                    "aggregateId": str(delivery.aggregate_id),
                    "payload": delivery.payload,
                },
                separators=(",", ":"),
                sort_keys=True,
            ).encode()
            signature = hmac.new(
                secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256
            ).hexdigest()
            response = await sender.send(
                delivery.url,
                {
                    "Content-Type": "application/json",
                    "Idempotency-Key": str(delivery.event_id),
                    "X-BigHead-Event-Id": str(delivery.event_id),
                    "X-BigHead-Timestamp": timestamp,
                    "X-BigHead-Signature": f"sha256={signature}",
                },
                body,
            )
            response_status = response.status_code
            response.raise_for_status()
            body_hash = hashlib.sha256(response.content).hexdigest()
            if not await store.ack(delivery.id, worker, response.status_code, body_hash):
                raise RuntimeError("webhook lease was lost before ack")
            delivered += 1
        except Exception as exc:
            await store.nack(
                delivery.id,
                worker,
                f"{type(exc).__name__}: {exc}",
                response_status,
                max_attempts,
            )
            failed += 1
    return delivered, failed


async def _resolve_public_destination(url: str) -> tuple[str, str, int, str]:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("webhook destination must be an unauthenticated HTTPS URL")
    port = parsed.port or 443
    addresses = await asyncio.to_thread(
        socket.getaddrinfo, parsed.hostname, port, type=socket.SOCK_STREAM
    )
    if not addresses:
        raise ValueError("webhook destination did not resolve")
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise ValueError("webhook destination resolves to a non-public address")
    selected = str(ipaddress.ip_address(addresses[0][4][0]))
    target = parsed.path or "/"
    if parsed.query:
        target += f"?{parsed.query}"
    return parsed.hostname, selected, port, target


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, ip: str, port: int, timeout: float) -> None:
        self._ssl_context = ssl.create_default_context()
        super().__init__(host, port, timeout=timeout, context=self._ssl_context)
        self._pinned_ip = ip

    def connect(self) -> None:
        raw_socket = socket.create_connection((self._pinned_ip, self.port), self.timeout)
        self.sock = self._ssl_context.wrap_socket(raw_socket, server_hostname=self.host)


def _send_pinned_https(
    host: str,
    ip: str,
    port: int,
    target: str,
    headers: dict[str, str],
    body: bytes,
    timeout: float,
    original_url: str,
) -> httpx.Response:
    connection = _PinnedHTTPSConnection(host, ip, port, timeout)
    try:
        connection.request("POST", target, body=body, headers={**headers, "Host": host})
        response = connection.getresponse()
        content = response.read(65_536)
        return httpx.Response(
            response.status,
            headers=dict(response.getheaders()),
            content=content,
            request=httpx.Request("POST", original_url),
        )
    finally:
        connection.close()
