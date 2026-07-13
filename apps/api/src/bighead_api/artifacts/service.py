import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import PurePath
from typing import Any, Protocol
from urllib.parse import quote
from uuid import UUID, uuid4

import httpx
from fastapi import HTTPException

from bighead_api.artifacts.models import (
    ArtifactDownloadResponse,
    ArtifactStatusResponse,
    QuarantineStatus,
    UploadConfirmRequest,
    UploadInitiateRequest,
    UploadInitiateResponse,
)
from bighead_api.identity.repository import Database

ALLOWED_MIME_BY_EXTENSION = {
    "pdf": {"application/pdf"},
    "png": {"image/png"},
    "jpg": {"image/jpeg"},
    "jpeg": {"image/jpeg"},
    "webp": {"image/webp"},
    "txt": {"text/plain"},
    "md": {"text/markdown", "text/plain"},
    "csv": {"text/csv", "application/csv"},
    "json": {"application/json"},
    "docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    "xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    "pptx": {"application/vnd.openxmlformats-officedocument.presentationml.presentation"},
    "zip": {"application/zip", "application/x-zip-compressed"},
}


@dataclass(frozen=True)
class ArtifactRecord:
    id: UUID
    organization_id: UUID
    created_by: UUID
    storage_path: str
    checksum_sha256: str
    quarantine_status: QuarantineStatus


class ArtifactRepository(Protocol):
    async def create(self, record: ArtifactRecord, payload: UploadInitiateRequest) -> None: ...
    async def get(self, artifact_id: UUID, organization_id: UUID) -> ArtifactRecord | None: ...
    async def mark_pending(self, artifact_id: UUID, checksum: str) -> ArtifactRecord | None: ...


class StorageGateway(Protocol):
    async def signed_upload(self, path: str) -> tuple[str, datetime]: ...
    async def signed_download(self, path: str) -> tuple[str, datetime]: ...


@dataclass
class PostgresArtifactRepository:
    database: Database

    async def create(self, record: ArtifactRecord, payload: UploadInitiateRequest) -> None:
        metadata = {
            "expected_mime_type": payload.mime_type.lower(),
            "expected_size_bytes": payload.size_bytes,
            "expected_checksum_sha256": payload.checksum_sha256,
        }
        async with self.database.authenticated(record.created_by, record.organization_id) as conn:
            await conn.execute(
                """insert into public.artifacts
                     (id, organization_id, name, kind, storage_bucket, storage_path,
                      mime_type, size_bytes, checksum_sha256, metadata, created_by,
                      quarantine_status)
                   values ($1,$2,$3,'upload','artifacts',$4,$5,$6,$7,$8::jsonb,$9,'initiated')""",
                record.id,
                record.organization_id,
                payload.filename,
                record.storage_path,
                payload.mime_type.lower(),
                payload.size_bytes,
                payload.checksum_sha256,
                json.dumps(metadata),
                record.created_by,
            )

    async def get(self, artifact_id: UUID, organization_id: UUID) -> ArtifactRecord | None:
        pool = await self.database.pool()
        row = await pool.fetchrow(
            """select id, organization_id, created_by, storage_path, checksum_sha256,
                      quarantine_status::text status
                 from public.artifacts where id=$1 and organization_id=$2""",
            artifact_id,
            organization_id,
        )
        return _record(row) if row else None

    async def mark_pending(self, artifact_id: UUID, checksum: str) -> ArtifactRecord | None:
        pool = await self.database.pool()
        row = await pool.fetchrow(
            """update public.artifacts
                  set quarantine_status = 'pending'
                where id=$1 and checksum_sha256=$2
                  and quarantine_status in ('initiated','pending')
            returning id, organization_id, created_by, storage_path, checksum_sha256,
                      quarantine_status::text status""",
            artifact_id,
            checksum,
        )
        return _record(row) if row else None


def _record(row: Any) -> ArtifactRecord:
    return ArtifactRecord(
        id=row["id"],
        organization_id=row["organization_id"],
        created_by=row["created_by"],
        storage_path=row["storage_path"],
        checksum_sha256=row["checksum_sha256"],
        quarantine_status=QuarantineStatus(row["status"]),
    )


@dataclass
class SupabaseStorageGateway:
    base_url: str
    secret_key: str
    bucket: str = "artifacts"
    download_ttl_seconds: int = 900
    # Supabase signed upload URLs have a fixed two-hour validity.
    upload_ttl_seconds: int = 7200

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.secret_key}", "apikey": self.secret_key}

    async def signed_upload(self, path: str) -> tuple[str, datetime]:
        encoded = quote(path, safe="/")
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{self.base_url}/storage/v1/object/upload/sign/{self.bucket}/{encoded}",
                headers=self._headers(),
                json={},
            )
        if response.is_error:
            raise HTTPException(status_code=502, detail="Storage upload URL unavailable")
        body = response.json()
        url = body.get("signedURL") or body.get("url")
        if not isinstance(url, str):
            raise HTTPException(status_code=502, detail="Invalid Storage response")
        if url.startswith("/"):
            url = (
                f"{self.base_url}/storage/v1{url}"
                if url.startswith("/object/")
                else f"{self.base_url}{url}"
            )
        return url, datetime.now(UTC) + timedelta(seconds=self.upload_ttl_seconds)

    async def signed_download(self, path: str) -> tuple[str, datetime]:
        encoded = quote(path, safe="/")
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{self.base_url}/storage/v1/object/sign/{self.bucket}/{encoded}",
                headers=self._headers(),
                json={"expiresIn": self.download_ttl_seconds},
            )
        if response.is_error:
            raise HTTPException(status_code=502, detail="Storage download URL unavailable")
        url = response.json().get("signedURL")
        if not isinstance(url, str):
            raise HTTPException(status_code=502, detail="Invalid Storage response")
        if url.startswith("/"):
            url = (
                f"{self.base_url}/storage/v1{url}"
                if url.startswith("/object/")
                else f"{self.base_url}{url}"
            )
        return url, datetime.now(UTC) + timedelta(seconds=self.download_ttl_seconds)


@dataclass
class ArtifactService:
    repository: ArtifactRepository
    storage: StorageGateway

    async def initiate(
        self, organization_id: UUID, user_id: UUID, payload: UploadInitiateRequest
    ) -> UploadInitiateResponse:
        extension = PurePath(payload.filename).suffix.removeprefix(".").lower()
        if payload.mime_type.lower() not in ALLOWED_MIME_BY_EXTENSION.get(extension, set()):
            raise HTTPException(status_code=422, detail="MIME type does not match file extension")
        safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", payload.filename)
        artifact_id = uuid4()
        path = f"{organization_id}/{user_id}/{artifact_id}/{safe_name}"
        record = ArtifactRecord(
            id=artifact_id,
            organization_id=organization_id,
            created_by=user_id,
            storage_path=path,
            checksum_sha256=payload.checksum_sha256,
            quarantine_status=QuarantineStatus.INITIATED,
        )
        await self.repository.create(record, payload)
        url, expires_at = await self.storage.signed_upload(path)
        return UploadInitiateResponse(
            artifact_id=artifact_id,
            path=path,
            upload_url=url,
            expires_at=expires_at,
            required_headers={
                "content-type": payload.mime_type.lower(),
                "x-upsert": "false",
            },
        )

    async def confirm(
        self, organization_id: UUID, artifact_id: UUID, payload: UploadConfirmRequest
    ) -> ArtifactStatusResponse:
        record = await self.repository.get(artifact_id, organization_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Artifact not found")
        if record.checksum_sha256 != payload.checksum_sha256:
            raise HTTPException(status_code=409, detail="Checksum does not match upload initiation")
        pending = await self.repository.mark_pending(artifact_id, payload.checksum_sha256)
        if pending is None:
            raise HTTPException(status_code=409, detail="Artifact confirmation conflict")
        return ArtifactStatusResponse(
            artifact_id=artifact_id, quarantine_status=QuarantineStatus.PENDING
        )

    async def download(self, organization_id: UUID, artifact_id: UUID) -> ArtifactDownloadResponse:
        record = await self.repository.get(artifact_id, organization_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Artifact not found")
        if record.quarantine_status != QuarantineStatus.CLEAN:
            raise HTTPException(status_code=423, detail="Artifact is not cleared for download")
        url, expires_at = await self.storage.signed_download(record.storage_path)
        return ArtifactDownloadResponse(
            artifact_id=artifact_id, download_url=url, expires_at=expires_at
        )
