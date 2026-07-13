from arq import create_pool, cron
from arq.connections import RedisSettings
from redis.asyncio import Redis
from structlog import get_logger

from bighead_worker.artifact_scan import HttpMalwareScanner, SupabaseArtifactScanStore
from bighead_worker.config import get_settings
from bighead_worker.jobs import dispatch_outbox_job, heartbeat_job, scan_artifact_job
from bighead_worker.outbox import RedisEventPublisher, SupabaseOutboxStore

logger = get_logger(__name__)


class WorkerAppSettings:
    functions = [heartbeat_job, scan_artifact_job, dispatch_outbox_job]
    cron_jobs = [
        cron(
            dispatch_outbox_job,
            second=set(range(0, 60, 5)),
            run_at_startup=True,
            unique=True,
            max_tries=1,
        )
    ]

    @staticmethod
    async def on_startup(ctx: dict[str, object]) -> None:
        settings = get_settings()
        ctx["settings"] = settings
        ctx["artifact_scan_store"] = SupabaseArtifactScanStore(
            base_url=str(settings.supabase_url).rstrip("/"),
            secret_key=settings.supabase_secret_key.get_secret_value(),
            bucket=settings.storage_bucket,
        )
        ctx["malware_scanner"] = HttpMalwareScanner(settings.malware_scanner_url)
        ctx["outbox_store"] = SupabaseOutboxStore(
            base_url=str(settings.supabase_url).rstrip("/"),
            secret_key=settings.supabase_secret_key.get_secret_value(),
        )
        redis = Redis.from_url(settings.redis_url.get_secret_value(), decode_responses=True)
        ctx["event_publisher"] = RedisEventPublisher(redis)
        logger.info("worker.starting")

    @staticmethod
    async def on_shutdown(ctx: dict[str, object]) -> None:
        publisher = ctx.get("event_publisher")
        if isinstance(publisher, RedisEventPublisher):
            await publisher.client.aclose()


async def ping_worker() -> None:
    settings = get_settings()
    pool = await create_pool(RedisSettings.from_dsn(settings.redis_url.get_secret_value()))
    job = await pool.enqueue_job("heartbeat_job")
    if job is None:
        raise RuntimeError("ARQ did not enqueue heartbeat_job.")
    await job.result(timeout=5)
    await pool.aclose()
