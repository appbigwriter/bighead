import asyncio
from uuid import UUID

from bighead_pycore.models import WorkerHeartbeat
from structlog import get_logger

from bighead_worker.artifact_scan import scan_artifact

logger = get_logger(__name__)


async def heartbeat_job(ctx: dict[str, object]) -> WorkerHeartbeat:
    await asyncio.sleep(0.05)
    settings = ctx["settings"]
    payload = WorkerHeartbeat(
        queue_name=settings.queue_name,  # type: ignore[attr-defined]
        status="ok",
    )
    logger.info("worker.heartbeat", queue_name=payload.queue_name, status=payload.status)
    return payload


async def scan_artifact_job(ctx: dict[str, object], artifact_id: str) -> str:
    store = ctx["artifact_scan_store"]
    scanner = ctx["malware_scanner"]
    return await scan_artifact(
        store,  # type: ignore[arg-type]
        scanner,  # type: ignore[arg-type]
        UUID(artifact_id),
    )
