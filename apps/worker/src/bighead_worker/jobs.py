import asyncio

from bighead_pycore.models import WorkerHeartbeat
from structlog import get_logger

from bighead_worker.artifact_scan import scan_artifact
from bighead_worker.outbox import dispatch_outbox
from bighead_worker.privacy import process_privacy_requests
from bighead_worker.webhooks import dispatch_webhooks

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


async def scan_pending_artifacts_job(ctx: dict[str, object]) -> dict[str, int]:
    store = ctx["artifact_scan_store"]
    scanner = ctx["malware_scanner"]
    settings = ctx["settings"]
    worker = str(ctx["worker_id"])
    artifact_ids = await store.claim(  # type: ignore[attr-defined]
        worker,
        25,
        settings.job_lease_seconds,  # type: ignore[attr-defined]
    )
    clean = 0
    rejected = 0
    retried = 0
    for artifact_id in artifact_ids:
        verdict = await scan_artifact(
            store,  # type: ignore[arg-type]
            scanner,  # type: ignore[arg-type]
            artifact_id,
            worker=worker,
        )
        clean += verdict == "clean"
        rejected += verdict == "rejected"
        retried += verdict == "retry"
    return {
        "processed": clean + rejected,
        "clean": clean,
        "rejected": rejected,
        "retried": retried,
    }


async def dispatch_outbox_job(ctx: dict[str, object]) -> dict[str, int]:
    settings = ctx["settings"]
    published, failed = await dispatch_outbox(
        ctx["outbox_store"],  # type: ignore[arg-type]
        ctx["event_publisher"],  # type: ignore[arg-type]
        worker=f"{settings.queue_name}:outbox",  # type: ignore[attr-defined]
        lease_seconds=settings.job_lease_seconds,  # type: ignore[attr-defined]
    )
    return {"published": published, "failed": failed}


async def dispatch_webhooks_job(ctx: dict[str, object]) -> dict[str, int]:
    settings = ctx["settings"]
    delivered, failed = await dispatch_webhooks(
        ctx["webhook_store"],  # type: ignore[arg-type]
        ctx["webhook_sender"],  # type: ignore[arg-type]
        worker=f"{settings.queue_name}:webhooks",  # type: ignore[attr-defined]
        lease_seconds=settings.job_lease_seconds,  # type: ignore[attr-defined]
    )
    return {"delivered": delivered, "failed": failed}


async def process_privacy_job(ctx: dict[str, object]) -> dict[str, int]:
    settings = ctx["settings"]
    completed, failed = await process_privacy_requests(
        ctx["privacy_store"],  # type: ignore[arg-type]
        worker=f"{settings.queue_name}:privacy",  # type: ignore[attr-defined]
        lease_seconds=settings.job_lease_seconds,  # type: ignore[attr-defined]
    )
    return {"completed": completed, "failed": failed}
