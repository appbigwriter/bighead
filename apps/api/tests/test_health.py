import os
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("APP_URL", "http://localhost:3000")
os.environ.setdefault("API_URL", "http://localhost:8000")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres")
os.environ.setdefault(
    "DIRECT_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres"
)
os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("SUPABASE_PUBLISHABLE_KEY", "test-publishable-key")
os.environ.setdefault("SUPABASE_SECRET_KEY", "test-secret-key")
os.environ.setdefault("STORAGE_BUCKET", "artifacts")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("QUEUE_NAME", "bighead:jobs")
os.environ.setdefault("JOB_LEASE_SECONDS", "300")
os.environ.setdefault("OTEL_SERVICE_NAME", "bighead-api-test")
os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
os.environ.setdefault("ENCRYPTION_KEY", "12345678901234567890123456789012")
os.environ.setdefault("WEBHOOK_SIGNING_SECRET", "test-webhook-secret")
os.environ.setdefault("PORTAL_TOKEN_PEPPER", "test-portal-pepper")

from bighead_api.main import REQUEST_ID_PATTERN, create_app


class FakeSettings:
    app_env = "test"
    app_url = "http://localhost:3000"
    api_url = "http://localhost:8000"
    api_port = 8000
    cors_origins = ["http://localhost:3000"]
    log_level = "INFO"


def test_liveness_does_not_touch_dependencies() -> None:
    with patch("bighead_api.main.run_readiness_checks", new_callable=AsyncMock) as readiness_mock:
        client = TestClient(create_app(settings=FakeSettings()))  # type: ignore[arg-type]
        response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}
    readiness_mock.assert_not_awaited()


def test_liveness_replaces_untrusted_request_id() -> None:
    client = TestClient(create_app(settings=FakeSettings()))  # type: ignore[arg-type]
    response = client.get("/health/live", headers={"x-request-id": "bad request id\nvalue"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] != "bad request id\nvalue"
    assert REQUEST_ID_PATTERN.fullmatch(response.headers["x-request-id"])


def test_readiness_reports_degraded_when_dependencies_are_down() -> None:
    async_mock = AsyncMock(
        return_value=type(
            "Result",
            (),
            {"ok": False, "checks": {"database": "unavailable", "redis": "ok"}},
        )()
    )
    with patch("bighead_api.main.run_readiness_checks", async_mock):
        client = TestClient(create_app(settings=FakeSettings()))  # type: ignore[arg-type]
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
