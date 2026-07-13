from functools import lru_cache

from pydantic import AliasChoices, AnyHttpUrl, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True, extra="ignore")

    app_env: str = Field(validation_alias=AliasChoices("APP_ENV"))
    log_level: str = Field(default="INFO", validation_alias=AliasChoices("LOG_LEVEL"))
    redis_url: SecretStr = Field(validation_alias=AliasChoices("REDIS_URL"))
    queue_name: str = Field(validation_alias=AliasChoices("QUEUE_NAME"))
    job_lease_seconds: int = Field(
        ge=10, le=86400, validation_alias=AliasChoices("JOB_LEASE_SECONDS")
    )
    otel_service_name: str = Field(validation_alias=AliasChoices("OTEL_SERVICE_NAME"))
    otel_exporter_otlp_endpoint: AnyHttpUrl = Field(
        validation_alias=AliasChoices("OTEL_EXPORTER_OTLP_ENDPOINT")
    )
    otel_exporter_otlp_headers: str = Field(
        default="", validation_alias=AliasChoices("OTEL_EXPORTER_OTLP_HEADERS")
    )
    sentry_dsn: str = Field(default="", validation_alias=AliasChoices("SENTRY_DSN"))
    supabase_url: AnyHttpUrl = Field(validation_alias=AliasChoices("SUPABASE_URL"))
    supabase_secret_key: SecretStr = Field(validation_alias=AliasChoices("SUPABASE_SECRET_KEY"))
    storage_bucket: str = Field(
        default="artifacts", validation_alias=AliasChoices("STORAGE_BUCKET")
    )
    malware_scanner_url: str = Field(
        default="", validation_alias=AliasChoices("MALWARE_SCANNER_URL")
    )
    malware_scanner_api_key: SecretStr = Field(
        default=SecretStr(""), validation_alias=AliasChoices("MALWARE_SCANNER_API_KEY")
    )

    @field_validator("app_env")
    @classmethod
    def validate_app_env(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"development", "test", "staging", "production", "contract"}:
            raise ValueError("APP_ENV must be development, test, staging, production or contract.")
        return normalized

    @model_validator(mode="after")
    def validate_remote_environment(self) -> WorkerSettings:
        if self.app_env not in {"staging", "production"}:
            return self
        for name, value in {
            "SUPABASE_URL": str(self.supabase_url),
            "MALWARE_SCANNER_URL": self.malware_scanner_url,
        }.items():
            lowered = value.lower()
            if (
                not lowered.startswith("https://")
                or "localhost" in lowered
                or "127.0.0.1" in lowered
            ):
                raise ValueError(f"{name} must be a non-local HTTPS URL in {self.app_env}.")
        redis_url = self.redis_url.get_secret_value().lower()
        if (
            not redis_url.startswith("rediss://")
            or "localhost" in redis_url
            or "127.0.0.1" in redis_url
        ):
            raise ValueError(f"REDIS_URL must use remote TLS (rediss://) in {self.app_env}.")
        secret = self.supabase_secret_key.get_secret_value().strip()
        if len(secret) < 24 or "placeholder" in secret.lower():
            raise ValueError("SUPABASE_SECRET_KEY must be a non-placeholder server secret.")
        scanner_secret = self.malware_scanner_api_key.get_secret_value().strip()
        if len(scanner_secret) < 24 or "placeholder" in scanner_secret.lower():
            raise ValueError("MALWARE_SCANNER_API_KEY must be a non-placeholder server secret.")
        return self


@lru_cache
def get_settings() -> WorkerSettings:
    return WorkerSettings()  # type: ignore[call-arg]
