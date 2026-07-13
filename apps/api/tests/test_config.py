from typing import Any

import pytest
from bighead_api.config import Settings
from pydantic import ValidationError


def production_settings(**overrides: object) -> Settings:
    values: dict[str, Any] = {
        "APP_ENV": "production",
        "APP_URL": "https://app.bighead.example",
        "API_URL": "https://api.bighead.example",
        "CORS_ORIGINS": "https://app.bighead.example",
        "DATABASE_URL": "postgresql://app:secret@pooler.example:6543/postgres?sslmode=require",
        "DATABASE_SERVICE_URL": "postgresql://service:secret@pooler.example:6543/postgres?sslmode=require",
        "SUPABASE_URL": "https://project.supabase.co",
        "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_abcdefghijklmnopqrstuvwxyz",
        "SUPABASE_SECRET_KEY": "sb_" + "secret_abcdefghijklmnopqrstuvwxyz",
        "STORAGE_BUCKET": "artifacts",
        "REDIS_URL": "rediss://default:secret@redis.example:6380/0",
        "QUEUE_NAME": "bighead:production",
        "JOB_LEASE_SECONDS": 300,
        "OTEL_SERVICE_NAME": "bighead-api-production",
        "OTEL_EXPORTER_OTLP_ENDPOINT": "https://otel.example/v1/traces",
        "ENCRYPTION_KEY": "encryption-key-abcdefghijklmnopqrstuvwxyz",
        "WEBHOOK_SIGNING_SECRET": "webhook-secret-abcdefghijklmnopqrstuvwxyz",
        "PORTAL_TOKEN_PEPPER": "portal-pepper-abcdefghijklmnopqrstuvwxyz",
        "SIGNED_URL_TTL_SECONDS": 900,
    }
    values.update(overrides)
    return Settings(**values)


def test_production_settings_accept_explicit_remote_services() -> None:
    settings = production_settings()
    assert settings.app_env == "production"
    assert settings.signed_url_ttl_seconds == 900


def test_production_requires_distinct_tenant_and_service_database_roles() -> None:
    tenant_url = production_settings().database_url.get_secret_value()
    with pytest.raises(ValidationError):
        production_settings(DATABASE_SERVICE_URL=tenant_url)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("APP_URL", "http://localhost:3000"),
        ("CORS_ORIGINS", "*"),
        ("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/postgres"),
        ("DATABASE_URL", "postgresql://app:secret@pooler.example:6543/postgres"),
        ("REDIS_URL", "redis://default:secret@redis.example:6379/0"),
        (
            "DATABASE_SERVICE_URL",
            "postgresql://service:secret@pooler.example:6543/postgres",
        ),
        ("SUPABASE_SECRET_KEY", "<service-role-placeholder>"),
    ],
)
def test_production_settings_reject_local_or_placeholder_values(name: str, value: str) -> None:
    with pytest.raises(ValidationError):
        production_settings(**{name: value})
