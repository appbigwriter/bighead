from pathlib import Path
from typing import Any

import pytest
from bighead_worker.config import WorkerSettings
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
    }
    values.update(overrides)
    return WorkerSettings(**values)


def test_worker_production_settings_accept_remote_dependencies() -> None:
    assert production_settings().app_env == "production"


def test_production_compose_forwards_required_run_provider_configuration() -> None:
    compose = (Path(__file__).parents[3] / "compose.production.yml").read_text()
    worker = compose.split("  worker:", maxsplit=1)[1]
    assert "RUN_PROVIDER_URL: ${RUN_PROVIDER_URL:?RUN_PROVIDER_URL is required}" in worker
    assert (
        "RUN_PROVIDER_API_KEY: ${RUN_PROVIDER_API_KEY:?RUN_PROVIDER_API_KEY is required}"
        in worker
    )
    assert "RUN_PROVIDER_TIMEOUT_SECONDS: ${RUN_PROVIDER_TIMEOUT_SECONDS:-60}" in worker


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("REDIS_URL", "redis://default:secret@redis.example:6379/0"),
        ("REDIS_URL", "redis://127.0.0.1:6379/0"),
        ("MALWARE_SCANNER_URL", ""),
        ("SUPABASE_SECRET_KEY", "<service-role-placeholder>"),
        ("MALWARE_SCANNER_API_KEY", "<scanner-placeholder>"),
        ("RUN_PROVIDER_URL", ""),
        ("RUN_PROVIDER_API_KEY", "<provider-placeholder>"),
    ],
)
def test_worker_production_settings_reject_unsafe_dependencies(name: str, value: str) -> None:
    with pytest.raises(ValidationError):
        production_settings(**{name: value})
