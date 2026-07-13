from arq import create_pool
from arq.connections import RedisSettings
from structlog import get_logger

from bighead_worker.artifact_scan import HttpMalwareScanner, SupabaseArtifactScanStore
from bighead_worker.config import get_settings
from bighead_worker.jobs import heartbeat_job, scan_artifact_job

logger = get_logger(__name__)


class WorkerAppSettings:
    functions = [heartbeat_job, scan_artifact_job]

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
        logger.info("worker.starting")


async def ping_worker() -> None:
    settings = get_settings()
    pool = await create_pool(RedisSettings.from_dsn(settings.redis_url.get_secret_value()))
    job = await pool.enqueue_job("heartbeat_job")
    if job is None:
        raise RuntimeError("ARQ did not enqueue heartbeat_job.")
    await job.result(timeout=5)
    await pool.aclose()
