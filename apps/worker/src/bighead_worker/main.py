import json
import os
import socket

from arq import create_pool, cron
from arq.connections import RedisSettings
from redis.asyncio import Redis
from structlog import get_logger

from bighead_worker.artifact_scan import HttpMalwareScanner, SupabaseArtifactScanStore
from bighead_worker.config import get_settings
from bighead_worker.crm_gateway import (
    CrmAdapterFactory,
    EnvironmentSecretResolver,
    SupabaseCrmJobStore,
)
from bighead_worker.jobs import (
    dispatch_crm_sync_job,
    dispatch_outbox_job,
    dispatch_runs_job,
    dispatch_webhooks_job,
    heartbeat_job,
    process_privacy_job,
    scan_pending_artifacts_job,
)
from bighead_worker.llm_gateway import build_router
from bighead_worker.observability import configure_observability
from bighead_worker.outbox import RedisEventPublisher, SupabaseOutboxStore
from bighead_worker.privacy import SupabasePrivacyStore
from bighead_worker.runs import HttpRunExecutor, SupabaseRunStore
from bighead_worker.webhooks import HttpWebhookSender, SupabaseWebhookStore

logger = get_logger(__name__)


class WorkerAppSettings:
    functions = [
        heartbeat_job,
        scan_pending_artifacts_job,
        dispatch_outbox_job,
        dispatch_webhooks_job,
        dispatch_runs_job,
        dispatch_crm_sync_job,
        process_privacy_job,
    ]
    cron_jobs = [
        cron(
            scan_pending_artifacts_job,
            minute=set(range(60)),
            second=1,
            run_at_startup=True,
            unique=True,
            max_tries=1,
        ),
        cron(
            dispatch_outbox_job,
            second=set(range(0, 60, 5)),
            run_at_startup=True,
            unique=True,
            max_tries=1,
        ),
        cron(
            dispatch_webhooks_job,
            second=set(range(2, 60, 5)),
            run_at_startup=True,
            unique=True,
            max_tries=1,
        ),
        cron(
            dispatch_runs_job,
            second=set(range(4, 60, 5)),
            run_at_startup=True,
            unique=True,
            max_tries=1,
        ),
        cron(
            process_privacy_job,
            minute={7, 22, 37, 52},
            run_at_startup=True,
            unique=True,
            max_tries=1,
        ),
        cron(
            dispatch_crm_sync_job,
            second=set(range(1, 60, 10)),
            run_at_startup=True,
            unique=True,
            max_tries=1,
        ),
    ]

    @staticmethod
    async def on_startup(ctx: dict[str, object]) -> None:
        settings = get_settings()
        ctx["settings"] = settings
        ctx["worker_id"] = f"{settings.queue_name}:{socket.gethostname()}:{os.getpid()}"
        ctx["tracer_provider"] = configure_observability(settings)
        ctx["artifact_scan_store"] = SupabaseArtifactScanStore(
            base_url=str(settings.supabase_url).rstrip("/"),
            secret_key=settings.supabase_secret_key.get_secret_value(),
            bucket=settings.storage_bucket,
        )
        ctx["malware_scanner"] = HttpMalwareScanner(
            settings.malware_scanner_url,
            settings.malware_scanner_api_key.get_secret_value(),
        )
        ctx["outbox_store"] = SupabaseOutboxStore(
            base_url=str(settings.supabase_url).rstrip("/"),
            secret_key=settings.supabase_secret_key.get_secret_value(),
        )
        ctx["webhook_store"] = SupabaseWebhookStore(
            base_url=str(settings.supabase_url).rstrip("/"),
            secret_key=settings.supabase_secret_key.get_secret_value(),
        )
        ctx["webhook_sender"] = HttpWebhookSender()
        ctx["privacy_store"] = SupabasePrivacyStore(
            base_url=str(settings.supabase_url).rstrip("/"),
            secret_key=settings.supabase_secret_key.get_secret_value(),
            export_bucket=settings.storage_bucket,
        )
        ctx["run_store"] = SupabaseRunStore(
            base_url=str(settings.supabase_url).rstrip("/"),
            secret_key=settings.supabase_secret_key.get_secret_value(),
        )
        ctx["crm_job_store"] = SupabaseCrmJobStore(
            base_url=str(settings.supabase_url).rstrip("/"),
            secret_key=settings.supabase_secret_key.get_secret_value(),
        )
        endpoints = json.loads(settings.crm_provider_endpoints)
        if not isinstance(endpoints, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in endpoints.items()
        ):
            raise ValueError("CRM_PROVIDER_ENDPOINTS must be a JSON provider-to-origin object")
        ctx["crm_adapter_factory"] = CrmAdapterFactory(endpoints, EnvironmentSecretResolver())
        ctx["run_executor"] = (
            HttpRunExecutor(
                endpoint=settings.run_provider_url,
                api_key=settings.run_provider_api_key.get_secret_value(),
                timeout_seconds=settings.run_provider_timeout_seconds,
            )
            if settings.run_provider_url
            else None
        )
        if ctx["run_executor"] is None:
            logger.warning("worker.run_provider_disabled")
        if settings.llm_provider_default and settings.llm_provider_fallback:
            ctx["llm_router"] = build_router(
                default_provider=settings.llm_provider_default,  # type: ignore[arg-type]
                fallback_provider=settings.llm_provider_fallback,  # type: ignore[arg-type]
                default_model=settings.llm_model_default,
                fallback_model=settings.llm_model_fallback,
                api_keys={
                    "openai": settings.openai_api_key.get_secret_value(),
                    "anthropic": settings.anthropic_api_key.get_secret_value(),
                    "google": settings.google_genai_api_key.get_secret_value(),
                },
                timeout_seconds=settings.llm_timeout_seconds,
            )
        redis = Redis.from_url(settings.redis_url.get_secret_value(), decode_responses=True)
        ctx["event_publisher"] = RedisEventPublisher(redis)
        logger.info("worker.starting")

    @staticmethod
    async def on_shutdown(ctx: dict[str, object]) -> None:
        publisher = ctx.get("event_publisher")
        if isinstance(publisher, RedisEventPublisher):
            await publisher.client.aclose()
        tracer_provider = ctx.get("tracer_provider")
        if tracer_provider is not None and hasattr(tracer_provider, "shutdown"):
            tracer_provider.shutdown()


async def ping_worker() -> None:
    settings = get_settings()
    pool = await create_pool(RedisSettings.from_dsn(settings.redis_url.get_secret_value()))
    job = await pool.enqueue_job("heartbeat_job")
    if job is None:
        raise RuntimeError("ARQ did not enqueue heartbeat_job.")
    await job.result(timeout=5)
    await pool.aclose()
