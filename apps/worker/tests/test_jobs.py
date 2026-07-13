import hashlib
from uuid import UUID

import pytest
from bighead_worker.artifact_scan import PendingArtifact, ScanVerdict
from bighead_worker.jobs import heartbeat_job, scan_pending_artifacts_job


class SettingsStub:
    queue_name = "bighead:jobs"
    job_lease_seconds = 60


@pytest.mark.asyncio
async def test_heartbeat_job_returns_expected_payload() -> None:
    result = await heartbeat_job({"settings": SettingsStub()})
    assert result.status == "ok"
    assert result.queue_name == "bighead:jobs"


class PendingStore:
    artifact_id = UUID("30000000-0000-0000-0000-000000000001")
    content = b"%PDF-1.7\nclean"

    def __init__(self) -> None:
        self.finalized = False

    async def claim(self, worker: str, limit: int, lease_seconds: int) -> list[UUID]:
        return [self.artifact_id][:limit]

    async def pending(self, artifact_id: UUID) -> PendingArtifact | None:
        return PendingArtifact(
            id=artifact_id,
            storage_path="tenant/user/report.pdf",
            expected_mime_type="application/pdf",
            expected_size_bytes=len(self.content),
            expected_checksum_sha256=hashlib.sha256(self.content).hexdigest(),
        )

    async def download(self, storage_path: str) -> bytes:
        return self.content

    async def finalize(self, artifact_id: UUID, **values: object) -> bool:
        self.finalized = values.get("clean") is True
        return True

    async def retry(self, artifact_id: UUID, worker: str, reason: str) -> bool:
        return True


class CleanScanner:
    async def scan(self, content: bytes) -> ScanVerdict:
        return ScanVerdict.CLEAN


@pytest.mark.asyncio
async def test_pending_artifact_sweep_prevents_confirmed_uploads_from_stalling() -> None:
    store = PendingStore()
    result = await scan_pending_artifacts_job(
        {
            "artifact_scan_store": store,
            "malware_scanner": CleanScanner(),
            "settings": SettingsStub(),
            "worker_id": "worker-1",
        }
    )
    assert result == {"processed": 1, "clean": 1, "rejected": 0, "retried": 0}
    assert store.finalized is True
