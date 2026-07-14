import hashlib
import hmac
from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest
from bighead_worker.crm_gateway import (
    CrmAdapterFactory,
    CrmConnectionRuntime,
    CrmPage,
    CrmRecord,
    CrmSyncJob,
    EnvironmentSecretResolver,
    dispatch_crm_sync_jobs,
    redact_crm,
    sync_incremental,
    validate_provider_endpoint,
    verify_webhook_signature,
)
from bighead_worker.jobs import dispatch_crm_sync_job


@pytest.mark.asyncio
async def test_external_crm_cron_is_noop_when_not_configured() -> None:
    assert await dispatch_crm_sync_job({}) == {"completed": 0, "failed": 0}


def test_webhook_hmac_and_replay_window() -> None:
    body = b'{"id":"evt-1"}'
    timestamp = "1704067200"
    signature = hmac.new(b"secret", timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    verify_webhook_signature(
        body=body,
        signature=signature,
        timestamp=timestamp,
        secret="secret",
        now=datetime(2024, 1, 1, tzinfo=UTC),
    )
    with pytest.raises(ValueError, match="replay"):
        verify_webhook_signature(
            body=body,
            signature=signature,
            timestamp=timestamp,
            secret="secret",
            now=datetime(2024, 1, 2, tzinfo=UTC),
        )


def test_recursive_redaction_and_per_connection_secret_resolution() -> None:
    assert redact_crm({"nested": {"access_token": "x", "client_secret": "y"}}) == {
        "nested": {"access_token": "[REDACTED]", "client_secret": "[REDACTED]"}
    }
    resolver = EnvironmentSecretResolver(
        {"CRM_SECRET_TENANT_A": "a" * 24, "CRM_SECRET_TENANT_B": "b" * 24}
    )
    assert resolver.resolve("env://CRM_SECRET_TENANT_A") != resolver.resolve(
        "env://CRM_SECRET_TENANT_B"
    )
    with pytest.raises(ValueError, match="unsupported"):
        resolver.resolve("env://OPENAI_API_KEY")


def test_ssrf_policy_rejects_userinfo_and_private_dns(monkeypatch) -> None:
    with pytest.raises(ValueError):
        validate_provider_endpoint("https://user:pass@example.com")
    monkeypatch.setattr(
        "socket.getaddrinfo", lambda *args, **kwargs: [(2, 1, 6, "", ("10.0.0.1", 443))]
    )
    with pytest.raises(ValueError, match="public Internet"):
        validate_provider_endpoint("https://internal.example")


def test_dns_is_resolved_once_and_validated_ip_is_pinned(monkeypatch) -> None:
    calls = 0

    def resolve(*args, **kwargs):
        nonlocal calls
        calls += 1
        address = "8.8.8.8" if calls == 1 else "10.0.0.1"
        return [(2, 1, 6, "", (address, 443))]

    monkeypatch.setattr("socket.getaddrinfo", resolve)
    factory = CrmAdapterFactory(
        {"hubspot": "https://provider.example"},
        EnvironmentSecretResolver({"CRM_SECRET_TENANT_A": "a" * 24}),
    )
    adapter = factory.create(CrmConnectionRuntime("hubspot", "env://CRM_SECRET_TENANT_A"))
    assert adapter.base_url == "https://8.8.8.8"
    assert calls == 1


@pytest.mark.asyncio
async def test_incremental_sync_advances_cursor_transactionally() -> None:
    record = CrmRecord(
        "contact", "c-1", datetime(2024, 1, 1, tzinfo=UTC), {"email": "a@example.com"}
    )

    class Adapter:
        async def fetch_changes(self, *, cursor, high_watermark):
            return CrmPage((record,), None, record.updated_at)

    class Store:
        async def load_cursor(self, connection_id):
            return None, None, 3

        async def apply_page(self, connection_id, page, expected_version):
            assert expected_version == 3
            return 4

    assert await sync_incremental("conn", Adapter(), Store()) == 1


@pytest.mark.asyncio
async def test_job_bridge_claims_http_sync_applies_cursor_and_acks() -> None:
    job = CrmSyncJob(
        UUID("10000000-0000-0000-0000-000000000001"),
        UUID("20000000-0000-0000-0000-000000000001"),
        1,
        UUID("30000000-0000-0000-0000-000000000001"),
    )

    async def provider(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer crm-secret-abcdefghijklmnopqrstuvwxyz"
        return httpx.Response(
            200,
            json={
                "records": [
                    {
                        "entityType": "contact",
                        "externalId": "contact-1",
                        "updatedAt": "2026-07-13T18:00:00Z",
                        "fields": {"name": "Ada"},
                    }
                ],
                "nextCursor": None,
                "highWatermark": "2026-07-13T18:00:00Z",
            },
        )

    class Store:
        acked = nacked = 0
        pages: list[CrmPage] = []

        async def claim_jobs(self, worker, limit, lease_seconds):
            return [job]

        async def heartbeat_job(self, job_id, worker, lease_token, lease_seconds):
            return True

        async def ack_job(self, job_id, worker, lease_token):
            self.acked += 1
            return True

        async def nack_job(self, job_id, worker, lease_token, error, max_attempts):
            self.nacked += 1
            return True

        async def load_cursor(self, connection_id):
            return None, None, 0

        async def load_connection(self, connection_id):
            return CrmConnectionRuntime("hubspot", "env://CRM_SECRET_TENANT_A")

        async def apply_page(self, connection_id, page, expected_version):
            self.pages.append(page)
            return 1

    store = Store()
    factory = CrmAdapterFactory(
        {"hubspot": "https://example.com"},
        EnvironmentSecretResolver({"CRM_SECRET_TENANT_A": "crm-secret-abcdefghijklmnopqrstuvwxyz"}),
        httpx.MockTransport(provider),
    )
    assert await dispatch_crm_sync_jobs(store, factory, worker="worker") == (1, 0)
    assert store.acked == 1 and store.nacked == 0
    assert store.pages[0].records[0].external_id == "contact-1"


@pytest.mark.asyncio
async def test_job_bridge_nacks_provider_failure_for_backoff_and_dlq_policy() -> None:
    job = CrmSyncJob(
        UUID("10000000-0000-0000-0000-000000000001"),
        UUID("20000000-0000-0000-0000-000000000001"),
        8,
        UUID("30000000-0000-0000-0000-000000000001"),
    )

    async def provider(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    class Store:
        error = ""

        async def claim_jobs(self, worker, limit, lease_seconds):
            return [job]

        async def heartbeat_job(self, job_id, worker, lease_token, lease_seconds):
            return True

        async def ack_job(self, job_id, worker, lease_token):
            return True

        async def nack_job(self, job_id, worker, lease_token, error, max_attempts):
            self.error = error
            assert max_attempts == 8
            return True

        async def load_cursor(self, connection_id):
            return None, None, 0

        async def load_connection(self, connection_id):
            return CrmConnectionRuntime("hubspot", "env://CRM_SECRET_TENANT_A")

        async def apply_page(self, connection_id, page, expected_version):
            return 1

    store = Store()
    factory = CrmAdapterFactory(
        {"hubspot": "https://example.com"},
        EnvironmentSecretResolver({"CRM_SECRET_TENANT_A": "crm-secret-abcdefghijklmnopqrstuvwxyz"}),
        httpx.MockTransport(provider),
    )
    assert await dispatch_crm_sync_jobs(store, factory, worker="worker") == (0, 1)
    assert store.error == "HTTPStatusError"
