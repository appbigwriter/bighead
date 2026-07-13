import hashlib
import io
import zipfile
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from urllib.parse import quote
from uuid import UUID

import httpx


class ScanVerdict(StrEnum):
    CLEAN = "clean"
    INFECTED = "infected"


@dataclass(frozen=True)
class PendingArtifact:
    id: UUID
    storage_path: str
    expected_mime_type: str
    expected_size_bytes: int
    expected_checksum_sha256: str


class ArtifactScanStore(Protocol):
    async def pending(self, artifact_id: UUID) -> PendingArtifact | None: ...
    async def download(self, storage_path: str) -> bytes: ...
    async def finalize(
        self,
        artifact_id: UUID,
        *,
        clean: bool,
        actual_mime_type: str,
        actual_size_bytes: int,
        actual_checksum_sha256: str,
        reason: str | None,
    ) -> None: ...


class MalwareScanner(Protocol):
    async def scan(self, content: bytes) -> ScanVerdict: ...


class ScannerUnavailable(RuntimeError):
    pass


@dataclass
class HttpMalwareScanner:
    url: str

    async def scan(self, content: bytes) -> ScanVerdict:
        if not self.url:
            raise ScannerUnavailable("malware scanner is not configured")
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(self.url, content=content)
        if response.is_error:
            raise ScannerUnavailable(f"malware scanner returned {response.status_code}")
        verdict = response.json().get("verdict")
        if verdict not in {ScanVerdict.CLEAN.value, ScanVerdict.INFECTED.value}:
            raise ScannerUnavailable("malware scanner returned an invalid verdict")
        return ScanVerdict(verdict)


@dataclass
class SupabaseArtifactScanStore:
    base_url: str
    secret_key: str
    bucket: str = "artifacts"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.secret_key}", "apikey": self.secret_key}

    async def pending(self, artifact_id: UUID) -> PendingArtifact | None:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{self.base_url}/rest/v1/artifacts",
                headers=self._headers(),
                params={
                    "id": f"eq.{artifact_id}",
                    "select": "id,storage_path,metadata",
                    "quarantine_status": "eq.pending",
                    "limit": "1",
                },
            )
        response.raise_for_status()
        rows = response.json()
        if not rows:
            return None
        row = rows[0]
        metadata = row["metadata"]
        return PendingArtifact(
            id=UUID(row["id"]),
            storage_path=row["storage_path"],
            expected_mime_type=metadata["expected_mime_type"],
            expected_size_bytes=int(metadata["expected_size_bytes"]),
            expected_checksum_sha256=metadata["expected_checksum_sha256"],
        )

    async def download(self, storage_path: str) -> bytes:
        encoded = quote(storage_path, safe="/")
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(
                f"{self.base_url}/storage/v1/object/authenticated/{self.bucket}/{encoded}",
                headers=self._headers(),
            )
        response.raise_for_status()
        return response.content

    async def finalize(
        self,
        artifact_id: UUID,
        *,
        clean: bool,
        actual_mime_type: str,
        actual_size_bytes: int,
        actual_checksum_sha256: str,
        reason: str | None,
    ) -> None:
        status = "clean" if clean else "rejected"
        # The service-role worker is the only actor in this flow allowed to write
        # the authoritative scan result. Client-provided Storage metadata is ignored.
        patch = {
            "quarantine_status": status,
            "metadata": {
                "actual_mime_type": actual_mime_type,
                "actual_size_bytes": actual_size_bytes,
                "actual_checksum_sha256": actual_checksum_sha256,
                "rejection_reason": reason,
            },
        }
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.patch(
                f"{self.base_url}/rest/v1/artifacts",
                headers={**self._headers(), "Prefer": "return=minimal"},
                params={"id": f"eq.{artifact_id}", "quarantine_status": "eq.pending"},
                json=patch,
            )
        response.raise_for_status()


def sniff_mime(content: bytes) -> str:
    if content.startswith(b"%PDF-"):
        return "application/pdf"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "image/webp"
    if content.startswith(b"PK\x03\x04"):
        return "application/zip"
    try:
        content.decode("utf-8")
    except UnicodeDecodeError:
        return "application/octet-stream"
    return "text/plain"


async def scan_artifact(
    store: ArtifactScanStore, scanner: MalwareScanner, artifact_id: UUID
) -> str:
    artifact = await store.pending(artifact_id)
    if artifact is None:
        return "ignored"
    try:
        content = await store.download(artifact.storage_path)
        actual_size = len(content)
        actual_checksum = hashlib.sha256(content).hexdigest()
        actual_mime = sniff_mime(content)
        reason: str | None = None
        if actual_size != artifact.expected_size_bytes:
            reason = "size_mismatch"
        elif actual_checksum != artifact.expected_checksum_sha256:
            reason = "checksum_mismatch"
        elif not _mime_matches(artifact.expected_mime_type, actual_mime, content):
            reason = "mime_mismatch"
        elif await scanner.scan(content) != ScanVerdict.CLEAN:
            reason = "malware_detected"
    except Exception as exc:  # scanner/storage failures must never promote content
        actual_size = len(locals().get("content", b""))
        actual_checksum = locals().get("actual_checksum", "")
        actual_mime = locals().get("actual_mime", "application/octet-stream")
        reason = f"scanner_error:{type(exc).__name__}"
    await store.finalize(
        artifact_id,
        clean=reason is None,
        actual_mime_type=actual_mime,
        actual_size_bytes=actual_size,
        actual_checksum_sha256=actual_checksum,
        reason=reason,
    )
    return "clean" if reason is None else "rejected"


def _mime_matches(expected: str, actual: str, content: bytes) -> bool:
    if expected in {"text/markdown", "text/csv", "application/csv", "application/json"}:
        return actual == "text/plain"
    if expected.startswith("application/vnd.openxmlformats"):
        return actual == "application/zip" and _valid_openxml(expected, content)
    return expected == actual


def _valid_openxml(expected: str, content: bytes) -> bool:
    required = {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (
            "word/document.xml"
        ),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xl/workbook.xml",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": (
            "ppt/presentation.xml"
        ),
    }.get(expected)
    if required is None:
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            infos = archive.infolist()
            names = {info.filename for info in infos}
            if "[Content_Types].xml" not in names or required not in names:
                return False
            if any(_unsafe_zip_name(info.filename) for info in infos):
                return False
            if sum(info.file_size for info in infos) > 200 * 1024 * 1024:
                return False
            return archive.testzip() is None
    except zipfile.BadZipFile, OSError, RuntimeError:
        return False


def _unsafe_zip_name(name: str) -> bool:
    normalized = name.replace("\\", "/")
    parts = normalized.split("/")
    return normalized.startswith("/") or ".." in parts or not normalized
