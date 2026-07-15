import asyncio
import hashlib
import io
import struct
import zipfile
from uuid import UUID

import pytest
from bighead_worker.artifact_scan import (
    ClamdMalwareScanner,
    PendingArtifact,
    ScannerUnavailable,
    ScanVerdict,
    _mime_matches,
    scan_artifact,
    sniff_mime,
)

ARTIFACT_ID = UUID("30000000-0000-0000-0000-000000000001")
PDF = b"%PDF-1.7\ntrusted test content"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (b"stream: OK\0", ScanVerdict.CLEAN),
        (b"stream: Eicar-Test-Signature FOUND\0", ScanVerdict.INFECTED),
    ],
)
async def test_clamd_scanner_uses_instream_protocol(response: bytes, expected: ScanVerdict) -> None:
    received = bytearray()

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        assert await reader.readexactly(len(b"zINSTREAM\0")) == b"zINSTREAM\0"
        while True:
            size = struct.unpack("!I", await reader.readexactly(4))[0]
            if size == 0:
                break
            received.extend(await reader.readexactly(size))
        writer.write(response)
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    async with server:
        assert await ClamdMalwareScanner("127.0.0.1", port).scan(PDF) == expected
    assert bytes(received) == PDF


class FakeStore:
    def __init__(self, content: bytes = PDF) -> None:
        self.content = content
        self.finalized: dict[str, object] | None = None
        self.retried: str | None = None
        self.artifact = PendingArtifact(
            id=ARTIFACT_ID,
            storage_path="org/user/object/report.pdf",
            expected_mime_type="application/pdf",
            expected_size_bytes=len(PDF),
            expected_checksum_sha256=hashlib.sha256(PDF).hexdigest(),
        )

    async def claim(self, worker: str, limit: int, lease_seconds: int) -> list[UUID]:
        return [self.artifact.id][:limit]

    async def pending(self, artifact_id: UUID) -> PendingArtifact | None:
        return self.artifact

    async def download(self, storage_path: str) -> bytes:
        return self.content

    async def finalize(self, artifact_id: UUID, **values: object) -> bool:
        self.finalized = values
        return True

    async def retry(self, artifact_id: UUID, worker: str, reason: str) -> bool:
        self.retried = reason
        return True


class FakeScanner:
    def __init__(
        self, verdict: ScanVerdict = ScanVerdict.CLEAN, *, unavailable: bool = False
    ) -> None:
        self.verdict = verdict
        self.unavailable = unavailable

    async def scan(self, content: bytes) -> ScanVerdict:
        if self.unavailable:
            raise ScannerUnavailable("offline")
        return self.verdict


@pytest.mark.asyncio
async def test_worker_promotes_only_verified_clean_content() -> None:
    store = FakeStore()
    assert await scan_artifact(store, FakeScanner(), ARTIFACT_ID, worker="worker-1") == "clean"
    assert store.finalized == {
        "worker": "worker-1",
        "clean": True,
        "actual_mime_type": "application/pdf",
        "actual_size_bytes": len(PDF),
        "actual_checksum_sha256": hashlib.sha256(PDF).hexdigest(),
        "reason": None,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["checksum", "mime", "infected", "scanner"])
async def test_worker_is_fail_closed(failure: str) -> None:
    store = FakeStore()
    scanner = FakeScanner()
    if failure == "checksum":
        store.artifact = PendingArtifact(
            **{
                **store.artifact.__dict__,
                "expected_checksum_sha256": "0" * 64,
            }
        )
    elif failure == "mime":
        store.artifact = PendingArtifact(
            **{
                **store.artifact.__dict__,
                "expected_mime_type": "image/png",
            }
        )
    elif failure == "infected":
        scanner = FakeScanner(ScanVerdict.INFECTED)
    else:
        scanner = FakeScanner(unavailable=True)
    expected = "retry" if failure == "scanner" else "rejected"
    assert await scan_artifact(store, scanner, ARTIFACT_ID, worker="worker-1") == expected
    if failure == "scanner":
        assert store.finalized is None
        assert store.retried == "scanner_error:ScannerUnavailable"
        return
    assert store.finalized is not None
    assert store.finalized["clean"] is False


def test_mime_sniffer_uses_magic_bytes_not_filename_or_client_metadata() -> None:
    assert sniff_mime(PDF) == "application/pdf"
    assert sniff_mime(b"\x89PNG\r\n\x1a\nbody") == "image/png"
    assert sniff_mime(b"not really a pdf") == "text/plain"


def test_openxml_requires_valid_zip_structure_and_expected_part() -> None:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<document/>")
    mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert _mime_matches(mime, "application/zip", stream.getvalue())
    fake = b"PK\x03\x04[Content_Types].xmlword/document.xml"
    assert not _mime_matches(mime, "application/zip", fake)


def test_openxml_rejects_zip_path_traversal() -> None:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<document/>")
        archive.writestr("../escape", "bad")
    mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert not _mime_matches(mime, "application/zip", stream.getvalue())
