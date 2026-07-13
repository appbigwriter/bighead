from __future__ import annotations

import asyncio
import hashlib
import hmac
import ipaddress
import json
import os
import socket
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import urlparse
from uuid import UUID

import httpx


def canonical_hash(payload: object) -> str:
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


_SECRET_MARKERS = (
    "secret",
    "token",
    "password",
    "api_key",
    "apikey",
    "access_token",
    "client_secret",
    "authorization",
)


def redact_crm(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]"
            if any(marker in str(key).lower() for marker in _SECRET_MARKERS)
            else redact_crm(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_crm(item) for item in value]
    return value


def safe_error(exc: Exception) -> str:
    return type(exc).__name__


def validate_provider_endpoint(url: str) -> str:
    origin, _, _ = _resolve_provider_endpoint(url)
    return origin


def _resolve_provider_endpoint(url: str) -> tuple[str, str, tuple[str, ...]]:
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
    ):
        raise ValueError("CRM provider endpoint must be an HTTPS origin without credentials")
    host = parsed.hostname.rstrip(".").lower()
    if (
        host in {"localhost", "localhost.localdomain"}
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("CRM provider endpoint must be a public HTTPS origin")
    addresses = tuple(
        sorted({str(item[4][0]) for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)})
    )
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise ValueError("CRM provider endpoint resolves outside the public Internet")
    return f"https://{host}", host, addresses


def pin_provider_endpoint(url: str) -> tuple[str, str]:
    _, host, addresses = _resolve_provider_endpoint(url)
    address = str(addresses[0])
    literal = f"[{address}]" if ":" in address else address
    return f"https://{literal}", host


def verify_webhook_signature(
    *,
    body: bytes,
    signature: str,
    timestamp: str,
    secret: str,
    now: datetime | None = None,
    tolerance_seconds: int = 300,
) -> None:
    try:
        sent_at = datetime.fromtimestamp(int(timestamp), tz=UTC)
    except (ValueError, OSError) as exc:
        raise ValueError("invalid webhook timestamp") from exc
    current = now or datetime.now(UTC)
    if abs((current - sent_at).total_seconds()) > tolerance_seconds:
        raise ValueError("webhook timestamp outside replay window")
    expected = hmac.new(
        secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256
    ).hexdigest()
    supplied = signature.removeprefix("sha256=")
    if not hmac.compare_digest(expected, supplied):
        raise ValueError("invalid webhook signature")


@dataclass(frozen=True)
class CrmRecord:
    entity_type: str
    external_id: str
    updated_at: datetime
    fields: dict[str, Any]


@dataclass(frozen=True)
class CrmPage:
    records: tuple[CrmRecord, ...]
    next_cursor: str | None
    high_watermark: datetime | None


class CrmAdapter(Protocol):
    async def fetch_changes(
        self, *, cursor: str | None, high_watermark: datetime | None
    ) -> CrmPage: ...


@dataclass
class HttpCrmAdapter:
    base_url: str
    api_key: str = field(repr=False)
    transport: httpx.AsyncBaseTransport | None = field(default=None, repr=False)
    host_header: str | None = None

    async def fetch_changes(
        self, *, cursor: str | None, high_watermark: datetime | None
    ) -> CrmPage:
        params = {
            "cursor": cursor,
            "updated_after": high_watermark.isoformat() if high_watermark else None,
        }
        async with httpx.AsyncClient(
            transport=self.transport, timeout=30, trust_env=False
        ) as client:
            response = await client.get(
                self.base_url.rstrip("/") + "/changes",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Accept": "application/json",
                    **({"Host": self.host_header} if self.host_header else {}),
                },
                params={key: value for key, value in params.items() if value is not None},
                extensions={"sni_hostname": self.host_header.encode()} if self.host_header else {},
            )
        response.raise_for_status()
        payload = response.json()
        records = tuple(
            CrmRecord(
                entity_type=str(row["entityType"]),
                external_id=str(row["externalId"]),
                updated_at=datetime.fromisoformat(str(row["updatedAt"]).replace("Z", "+00:00")),
                fields=dict(row["fields"]),
            )
            for row in payload.get("records", [])
        )
        watermark = payload.get("highWatermark")
        return CrmPage(
            records,
            payload.get("nextCursor"),
            datetime.fromisoformat(watermark.replace("Z", "+00:00")) if watermark else None,
        )


class CrmSyncStore(Protocol):
    async def load_cursor(self, connection_id: str) -> tuple[str | None, datetime | None, int]: ...
    async def apply_page(self, connection_id: str, page: CrmPage, expected_version: int) -> int: ...


async def sync_incremental(
    connection_id: str, adapter: CrmAdapter, store: CrmSyncStore, *, max_pages: int = 100
) -> int:
    cursor, watermark, version = await store.load_cursor(connection_id)
    processed = 0
    for _ in range(max_pages):
        page = await adapter.fetch_changes(cursor=cursor, high_watermark=watermark)
        # Store must upsert records and advance cursor in one transaction using
        # expected_version. A crash therefore replays the same idempotent page.
        version = await store.apply_page(connection_id, page, version)
        processed += len(page.records)
        cursor, watermark = page.next_cursor, page.high_watermark or watermark
        if cursor is None:
            return processed
    raise RuntimeError("CRM pagination exceeded safety limit")


@dataclass(frozen=True)
class CrmSyncJob:
    id: UUID
    connection_id: UUID
    attempts: int
    lease_token: UUID


@dataclass(frozen=True)
class CrmConnectionRuntime:
    provider_key: str
    secret_ref: str


@dataclass(frozen=True)
class EnvironmentSecretResolver:
    environment: dict[str, str] | None = None

    def resolve(self, reference: str) -> str:
        if not reference.startswith("env://CRM_SECRET_"):
            raise ValueError("unsupported CRM secret reference")
        name = reference.removeprefix("env://")
        if not name or name.upper() != name or not name.replace("_", "").isalnum():
            raise ValueError("invalid CRM environment secret reference")
        value = (self.environment or os.environ).get(name, "").strip()
        if len(value) < 20:
            raise ValueError("CRM secret reference is unresolved")
        return value


@dataclass(frozen=True)
class CrmAdapterFactory:
    endpoints: dict[str, str]
    resolver: EnvironmentSecretResolver
    transport: httpx.AsyncBaseTransport | None = field(default=None, repr=False)

    def create(self, runtime: CrmConnectionRuntime) -> HttpCrmAdapter:
        endpoint = self.endpoints.get(runtime.provider_key)
        if endpoint is None:
            raise ValueError("CRM provider is not allowlisted")
        pinned_url, host = pin_provider_endpoint(endpoint)
        return HttpCrmAdapter(
            pinned_url,
            self.resolver.resolve(runtime.secret_ref),
            self.transport,
            host,
        )


class CrmJobStore(CrmSyncStore, Protocol):
    async def claim_jobs(self, worker: str, limit: int, lease_seconds: int) -> list[CrmSyncJob]: ...
    async def heartbeat_job(
        self, job_id: UUID, worker: str, lease_token: UUID, lease_seconds: int
    ) -> bool: ...
    async def ack_job(self, job_id: UUID, worker: str, lease_token: UUID) -> bool: ...
    async def nack_job(
        self, job_id: UUID, worker: str, lease_token: UUID, error: str, max_attempts: int
    ) -> bool: ...
    async def load_connection(self, connection_id: UUID) -> CrmConnectionRuntime: ...


@dataclass
class SupabaseCrmJobStore:
    base_url: str
    secret_key: str = field(repr=False)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.secret_key}",
            "apikey": self.secret_key,
            "Content-Type": "application/json",
        }

    async def claim_jobs(self, worker: str, limit: int, lease_seconds: int) -> list[CrmSyncJob]:
        rows = await self._rpc(
            "claim_crm_sync_jobs",
            {"p_worker": worker, "p_limit": limit, "p_lease_seconds": lease_seconds},
        )
        return [
            CrmSyncJob(
                UUID(row["id"]),
                UUID(row["connection_id"]),
                int(row["attempts"]),
                UUID(row["lease_token"]),
            )
            for row in rows
        ]

    async def heartbeat_job(
        self, job_id: UUID, worker: str, lease_token: UUID, lease_seconds: int
    ) -> bool:
        return bool(
            await self._rpc(
                "heartbeat_crm_sync_job",
                {
                    "p_id": str(job_id),
                    "p_worker": worker,
                    "p_lease_token": str(lease_token),
                    "p_lease_seconds": lease_seconds,
                },
            )
        )

    async def ack_job(self, job_id: UUID, worker: str, lease_token: UUID) -> bool:
        return bool(
            await self._rpc(
                "ack_crm_sync_job",
                {"p_id": str(job_id), "p_worker": worker, "p_lease_token": str(lease_token)},
            )
        )

    async def nack_job(
        self, job_id: UUID, worker: str, lease_token: UUID, error: str, max_attempts: int
    ) -> bool:
        return bool(
            await self._rpc(
                "nack_crm_sync_job",
                {
                    "p_id": str(job_id),
                    "p_worker": worker,
                    "p_lease_token": str(lease_token),
                    "p_error": error[:2000],
                    "p_max_attempts": max_attempts,
                },
            )
        )

    async def load_cursor(self, connection_id: str) -> tuple[str | None, datetime | None, int]:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{self.base_url}/rest/v1/crm_sync_cursors",
                headers=self._headers(),
                params={
                    "connection_id": f"eq.{connection_id}",
                    "select": "cursor,high_watermark,version",
                },
            )
        response.raise_for_status()
        rows = response.json()
        if not rows:
            return None, None, 0
        watermark = rows[0].get("high_watermark")
        return (
            rows[0].get("cursor"),
            datetime.fromisoformat(watermark.replace("Z", "+00:00")) if watermark else None,
            int(rows[0]["version"]),
        )

    async def load_connection(self, connection_id: UUID) -> CrmConnectionRuntime:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{self.base_url}/rest/v1/crm_connections",
                headers=self._headers(),
                params={
                    "id": f"eq.{connection_id}",
                    "status": "eq.active",
                    "select": "provider_key,secret_ref",
                },
            )
        response.raise_for_status()
        rows = response.json()
        if len(rows) != 1:
            raise ValueError("CRM connection is unavailable")
        return CrmConnectionRuntime(str(rows[0]["provider_key"]), str(rows[0]["secret_ref"]))

    async def apply_page(self, connection_id: str, page: CrmPage, expected_version: int) -> int:
        records = [
            {
                "entityType": row.entity_type,
                "externalId": row.external_id,
                "updatedAt": row.updated_at.isoformat(),
                "fields": row.fields,
            }
            for row in page.records
        ]
        return int(
            await self._rpc(
                "apply_crm_sync_page",
                {
                    "p_connection_id": connection_id,
                    "p_records": records,
                    "p_next_cursor": page.next_cursor,
                    "p_high_watermark": page.high_watermark.isoformat()
                    if page.high_watermark
                    else None,
                    "p_expected_version": expected_version,
                },
            )
        )

    async def _rpc(self, function: str, payload: dict[str, Any]) -> Any:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url}/rest/v1/rpc/{function}", headers=self._headers(), json=payload
            )
        response.raise_for_status()
        return response.json()


async def dispatch_crm_sync_jobs(
    store: CrmJobStore,
    adapter_factory: CrmAdapterFactory,
    *,
    worker: str,
    limit: int = 5,
    lease_seconds: int = 60,
    max_attempts: int = 8,
) -> tuple[int, int]:
    completed = failed = 0
    for job in await store.claim_jobs(worker, limit, lease_seconds):
        execution: asyncio.Task[int] | None = None
        heartbeat: asyncio.Task[None] | None = None
        try:
            adapter = adapter_factory.create(await store.load_connection(job.connection_id))
            execution = asyncio.create_task(
                sync_incremental(str(job.connection_id), adapter, store)
            )
            heartbeat = asyncio.create_task(_maintain_job_lease(store, job, worker, lease_seconds))
            done, _ = await asyncio.wait(
                {execution, heartbeat}, return_when=asyncio.FIRST_COMPLETED
            )
            if heartbeat in done:
                await heartbeat
                raise RuntimeError("CRM sync lease heartbeat stopped")
            await execution
            if not await store.ack_job(job.id, worker, job.lease_token):
                raise RuntimeError("CRM sync lease lost before ack")
            completed += 1
        except Exception as exc:
            await store.nack_job(job.id, worker, job.lease_token, safe_error(exc), max_attempts)
            failed += 1
        finally:
            for task in (execution, heartbeat):
                if task is None:
                    continue
                if not task.done():
                    task.cancel()
            await asyncio.gather(
                *(task for task in (execution, heartbeat) if task is not None),
                return_exceptions=True,
            )
    return completed, failed


async def _maintain_job_lease(
    store: CrmJobStore, job: CrmSyncJob, worker: str, lease_seconds: int
) -> None:
    while True:
        await asyncio.sleep(max(1.0, lease_seconds / 3))
        if not await store.heartbeat_job(job.id, worker, job.lease_token, lease_seconds):
            raise RuntimeError("CRM sync lease lost")
