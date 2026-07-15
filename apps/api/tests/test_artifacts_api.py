from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
import respx
from bighead_api.artifacts.models import QuarantineStatus, UploadInitiateRequest
from bighead_api.artifacts.routes import router
from bighead_api.artifacts.service import ArtifactRecord, ArtifactService, SupabaseStorageGateway
from bighead_api.identity.dependencies import TenantContext, tenant_context
from bighead_api.identity.models import AuthUser, MemberRole, Membership
from fastapi import FastAPI
from fastapi.testclient import TestClient

USER_ID = UUID("10000000-0000-0000-0000-000000000001")
ORG_ID = UUID("20000000-0000-0000-0000-000000000001")
CHECKSUM = "a" * 64


class FakeRepository:
    def __init__(self) -> None:
        self.records: dict[UUID, ArtifactRecord] = {}

    async def create(self, record: ArtifactRecord, payload: UploadInitiateRequest) -> None:
        self.records[record.id] = record

    async def get(self, artifact_id: UUID, organization_id: UUID) -> ArtifactRecord | None:
        record = self.records.get(artifact_id)
        return record if record and record.organization_id == organization_id else None

    async def mark_pending(self, artifact_id: UUID, checksum: str) -> ArtifactRecord | None:
        record = self.records.get(artifact_id)
        if not record or record.checksum_sha256 != checksum:
            return None
        record = ArtifactRecord(
            **{**record.__dict__, "quarantine_status": QuarantineStatus.PENDING}
        )
        self.records[artifact_id] = record
        return record


class FakeStorage:
    async def signed_upload(self, path: str) -> tuple[str, datetime]:
        return f"http://storage.test/upload/{path}", datetime.now(UTC) + timedelta(minutes=5)

    async def signed_download(self, path: str) -> tuple[str, datetime]:
        return f"http://storage.test/download/{path}", datetime.now(UTC) + timedelta(minutes=5)


def make_client(repository: FakeRepository) -> TestClient:
    app = FastAPI()
    app.state.artifact_service = ArtifactService(repository, FakeStorage())
    app.include_router(router)

    async def context() -> TenantContext:
        return TenantContext(
            user=AuthUser(id=USER_ID, email="owner@example.com"),
            token="valid",
            membership=Membership(
                id="membership",
                organization_id=ORG_ID,
                user_id=USER_ID,
                role=MemberRole.OWNER,
                status="active",
            ),
        )

    app.dependency_overrides[tenant_context] = context
    return TestClient(app)


def test_upload_is_tenant_scoped_and_starts_quarantined() -> None:
    repository = FakeRepository()
    response = make_client(repository).post(
        "/v1/artifacts/uploads",
        json={
            "filename": "report.pdf",
            "mimeType": "application/pdf",
            "sizeBytes": 42,
            "checksumSha256": CHECKSUM,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["quarantineStatus"] == "initiated"
    assert body["path"].startswith(f"{ORG_ID}/{USER_ID}/")
    assert body["requiredHeaders"]["x-upsert"] == "false"
    assert body["requiredHeaders"]["content-type"] == "application/pdf"
    assert "x-metadata" not in body["requiredHeaders"]
    assert "authorization" not in body["requiredHeaders"]


def test_upload_rejects_path_traversal_and_mime_spoof() -> None:
    client = make_client(FakeRepository())
    traversal = client.post(
        "/v1/artifacts/uploads",
        json={
            "filename": "../report.pdf",
            "mimeType": "application/pdf",
            "sizeBytes": 42,
            "checksumSha256": CHECKSUM,
        },
    )
    spoof = client.post(
        "/v1/artifacts/uploads",
        json={
            "filename": "report.pdf",
            "mimeType": "image/png",
            "sizeBytes": 42,
            "checksumSha256": CHECKSUM,
        },
    )
    assert traversal.status_code == 422
    assert spoof.status_code == 422


def test_confirmation_cannot_replace_expected_checksum() -> None:
    repository = FakeRepository()
    client = make_client(repository)
    created = client.post(
        "/v1/artifacts/uploads",
        json={
            "filename": "report.pdf",
            "mimeType": "application/pdf",
            "sizeBytes": 42,
            "checksumSha256": CHECKSUM,
        },
    ).json()
    response = client.post(
        f"/v1/artifacts/{created['artifactId']}/confirm", json={"checksumSha256": "b" * 64}
    )
    assert response.status_code == 409


def test_download_is_locked_until_worker_marks_record_clean() -> None:
    repository = FakeRepository()
    client = make_client(repository)
    created = client.post(
        "/v1/artifacts/uploads",
        json={
            "filename": "report.pdf",
            "mimeType": "application/pdf",
            "sizeBytes": 42,
            "checksumSha256": CHECKSUM,
        },
    ).json()
    artifact_id = UUID(created["artifactId"])
    assert client.get(f"/v1/artifacts/{artifact_id}/download").status_code == 423
    current = repository.records[artifact_id]
    repository.records[artifact_id] = ArtifactRecord(
        **{**current.__dict__, "quarantine_status": QuarantineStatus.CLEAN}
    )
    response = client.get(f"/v1/artifacts/{artifact_id}/download")
    assert response.status_code == 200
    assert "/download/" in response.json()["downloadUrl"]


@pytest.mark.asyncio
@respx.mock
async def test_signed_upload_expands_storage_relative_object_url() -> None:
    respx.post(
        "http://supabase.test/storage/v1/object/upload/sign/artifacts/tenant/file.txt"
    ).respond(200, json={"url": "/object/upload/sign/artifacts/tenant/file.txt?token=signed"})
    gateway = SupabaseStorageGateway("http://supabase.test", "secret")

    url, _ = await gateway.signed_upload("tenant/file.txt")

    assert url == (
        "http://supabase.test/storage/v1/object/upload/sign/artifacts/tenant/file.txt?token=signed"
    )


@pytest.mark.asyncio
@respx.mock
async def test_signed_upload_uses_public_origin_for_browser_url() -> None:
    respx.post(
        "http://supabase.internal/storage/v1/object/upload/sign/artifacts/tenant/file.txt"
    ).respond(200, json={"url": "/object/upload/sign/artifacts/tenant/file.txt?token=signed"})
    gateway = SupabaseStorageGateway(
        "http://supabase.internal", "secret", public_base_url="http://127.0.0.1:55321"
    )

    url, _ = await gateway.signed_upload("tenant/file.txt")

    assert url == (
        "http://127.0.0.1:55321/storage/v1/object/upload/sign/artifacts/tenant/file.txt?token=signed"
    )


@pytest.mark.asyncio
@respx.mock
async def test_signed_download_uses_configured_ttl() -> None:
    route = respx.post(
        "http://supabase.test/storage/v1/object/sign/artifacts/tenant/file.txt"
    ).respond(200, json={"signedURL": "/object/sign/artifacts/tenant/file.txt?token=signed"})
    gateway = SupabaseStorageGateway("http://supabase.test", "secret", download_ttl_seconds=600)

    url, expires_at = await gateway.signed_download("tenant/file.txt")

    assert url.endswith("/object/sign/artifacts/tenant/file.txt?token=signed")
    assert route.calls.last.request.content == b'{"expiresIn":600}'
    remaining = (expires_at - datetime.now(UTC)).total_seconds()
    assert 595 <= remaining <= 600
