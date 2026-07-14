from typing import Any
from urllib.parse import urlparse

import sentry_sdk
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from bighead_worker.config import WorkerSettings


def _scrub_event(event: Any, hint: Any) -> Any:
    del hint
    event.pop("request", None)
    return event


def _headers(raw: str) -> dict[str, str]:
    return {
        key.strip(): value.strip()
        for item in raw.split(",")
        for key, separator, value in [item.partition("=")]
        if separator and key.strip() and value.strip()
    }


def configure_observability(settings: WorkerSettings) -> TracerProvider | None:
    if settings.app_env in {"test", "contract"}:
        return None
    if settings.sentry_dsn.strip():
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.app_env,
            send_default_pii=False,
            max_request_body_size="never",
            before_send=_scrub_event,
            traces_sample_rate=0.1 if settings.app_env == "production" else 1.0,
        )
    if settings.otel_exporter_otlp_endpoint is None:
        return None
    endpoint = str(settings.otel_exporter_otlp_endpoint).rstrip("/")
    if not urlparse(endpoint).path.rstrip("/").endswith("/v1/traces"):
        endpoint = f"{endpoint}/v1/traces"
    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": settings.otel_service_name,
                "deployment.environment.name": settings.app_env,
            }
        )
    )
    provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(
                endpoint=endpoint,
                headers=_headers(settings.otel_exporter_otlp_headers),
            )
        )
    )
    trace.set_tracer_provider(provider)
    return provider
