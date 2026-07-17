from pathlib import Path
from typing import Any

import pytest
from bighead_worker.config import WorkerSettings
from bighead_worker.observability import configure_observability
from pydantic import ValidationError


def production_settings(**overrides: object) -> WorkerSettings:
    values: dict[str, Any] = {
        "APP_ENV": "production",
        "REDIS_URL": "rediss://default:secret@redis.example:6380/0",
        "QUEUE_NAME": "bighead:production",
        "JOB_LEASE_SECONDS": 300,
        "OTEL_SERVICE_NAME": "bighead-worker-production",
        "OTEL_EXPORTER_OTLP_ENDPOINT": "https://otel.example",
        "SUPABASE_URL": "https://project.supabase.co",
        "SUPABASE_SECRET_KEY": "sb_" + "secret_abcdefghijklmnopqrstuvwxyz",
        "STORAGE_BUCKET": "artifacts",
        "MALWARE_SCANNER_URL": "https://scanner.bighead.example/scan",
        "MALWARE_SCANNER_API_KEY": "scanner-secret-abcdefghijklmnopqrstuvwxyz",
        "RUN_PROVIDER_URL": "https://provider.bighead.example/runs",
        "RUN_PROVIDER_API_KEY": "provider-secret-abcdefghijklmnopqrstuvwxyz",
        "LLM_PROVIDER_DEFAULT": "openai",
        "LLM_PROVIDER_FALLBACK": "anthropic",
        "LLM_MODEL_DEFAULT": "gpt-production",
        "LLM_MODEL_FALLBACK": "claude-production",
        "OPENAI_API_KEY": "openai-secret-abcdefghijklmnopqrstuvwxyz",
        "ANTHROPIC_API_KEY": "anthropic-secret-abcdefghijklmnopqrstuvwxyz",
        "ANYTHING_LLM_API_URL": "https://knowledge.bighead.example",
        "ANYTHING_LLM_API_KEY": "anythingllm-secret-abcdefghijklmnopqrstuvwxyz",
        "CRM_PROVIDER_ENDPOINTS": '{"hubspot":"https://api.hubapi.com"}',
    }
    values.update(overrides)
    return WorkerSettings(**values)


def test_worker_production_settings_accept_remote_dependencies() -> None:
    assert production_settings().app_env == "production"


def test_worker_accepts_authenticated_private_redis_and_clamd_without_api_key() -> None:
    settings = production_settings(
        REDIS_URL="redis://:strong-internal-password@redis:6379/0",
        MALWARE_SCANNER_URL="clamd://clamav:3310",
        MALWARE_SCANNER_API_KEY="",
        CRM_PROVIDER_ENDPOINTS="{}",
    )
    assert settings.malware_scanner_url == "clamd://clamav:3310"


def test_worker_runs_without_otel_and_still_initializes_sentry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialized: list[dict[str, object]] = []
    monkeypatch.setattr(
        "bighead_worker.observability.sentry_sdk.init",
        lambda **kwargs: initialized.append(kwargs),
    )
    settings = production_settings(
        OTEL_EXPORTER_OTLP_ENDPOINT="",
        SENTRY_DSN="https://public@sentry.example/1",
    )
    assert configure_observability(settings) is None
    assert initialized and initialized[0]["dsn"] == "https://public@sentry.example/1"


def test_production_compose_keeps_http_run_provider_as_optional_override() -> None:
    compose = (Path(__file__).parents[3] / "compose.production.yml").read_text()
    worker = compose.split("  worker:", maxsplit=1)[1]
    assert "RUN_PROVIDER_URL: ${RUN_PROVIDER_URL:-}" in worker
    assert "RUN_PROVIDER_API_KEY: ${RUN_PROVIDER_API_KEY:-}" in worker
    assert "RUN_PROVIDER_TIMEOUT_SECONDS: ${RUN_PROVIDER_TIMEOUT_SECONDS:-60}" in worker


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("REDIS_URL", "redis://default:secret@redis.example:6379/0"),
        ("REDIS_URL", "redis://127.0.0.1:6379/0"),
        ("REDIS_URL", "redis://redis.example:6379/0"),
        ("REDIS_URL", "redis://redis:6379/0"),
        ("MALWARE_SCANNER_URL", ""),
        ("MALWARE_SCANNER_URL", "clamd://localhost:3310"),
        ("MALWARE_SCANNER_URL", "http://scanner.example/scan"),
        ("SUPABASE_SECRET_KEY", "<service-role-placeholder>"),
        ("MALWARE_SCANNER_API_KEY", "<scanner-placeholder>"),
        ("RUN_PROVIDER_API_KEY", "<provider-placeholder>"),
        ("LLM_PROVIDER_FALLBACK", "openai"),
        ("OPENAI_API_KEY", "<provider-placeholder>"),
    ],
)
def test_worker_production_settings_reject_unsafe_dependencies(name: str, value: str) -> None:
    with pytest.raises(ValidationError):
        production_settings(**{name: value})


def test_worker_production_settings_accept_internal_llm_executor_without_http_override() -> None:
    settings = production_settings(RUN_PROVIDER_URL="", RUN_PROVIDER_API_KEY="")
    assert settings.run_provider_url == ""
