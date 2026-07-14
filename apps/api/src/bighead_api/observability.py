from typing import Any
from urllib.parse import urlparse

import sentry_sdk
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from bighead_api.config import Settings


def _scrub_event(event: Any, hint: Any) -> Any:
    del hint
    request = event.get("request")
    if isinstance(request, dict):
        request.pop("data", None)
        request.pop("cookies", None)
        headers = request.get("headers")
        if isinstance(headers, dict):
            for name in list(headers):
                if str(name).lower() in {"authorization", "cookie", "x-api-key", "apikey"}:
                    headers.pop(name, None)
    return event


def _headers(raw: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in raw.split(","):
        key, separator, value = item.partition("=")
        if separator and key.strip() and value.strip():
            parsed[key.strip()] = value.strip()
    return parsed


def _trace_endpoint(raw: str) -> str:
    endpoint = raw.rstrip("/")
    path = urlparse(endpoint).path.rstrip("/")
    return endpoint if path.endswith("/v1/traces") else f"{endpoint}/v1/traces"


def configure_observability(settings: Settings) -> TracerProvider | None:
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

    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": settings.otel_service_name,
                "deployment.environment.name": settings.app_env,
            }
        )
    )
    exporter = OTLPSpanExporter(
        endpoint=_trace_endpoint(str(settings.otel_exporter_otlp_endpoint)),
        headers=_headers(settings.otel_exporter_otlp_headers),
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    return provider
