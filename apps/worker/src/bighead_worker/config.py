from functools import lru_cache

from pydantic import AliasChoices, AnyHttpUrl, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True, extra="ignore")

    app_env: str = Field(validation_alias=AliasChoices("APP_ENV"))
    log_level: str = Field(default="INFO", validation_alias=AliasChoices("LOG_LEVEL"))
    redis_url: SecretStr = Field(validation_alias=AliasChoices("REDIS_URL"))
    queue_name: str = Field(validation_alias=AliasChoices("QUEUE_NAME"))
    job_lease_seconds: int = Field(validation_alias=AliasChoices("JOB_LEASE_SECONDS"))
    otel_service_name: str = Field(validation_alias=AliasChoices("OTEL_SERVICE_NAME"))
    otel_exporter_otlp_endpoint: AnyHttpUrl = Field(
        validation_alias=AliasChoices("OTEL_EXPORTER_OTLP_ENDPOINT")
    )
    otel_exporter_otlp_headers: str = Field(
        default="", validation_alias=AliasChoices("OTEL_EXPORTER_OTLP_HEADERS")
    )
    api_url: AnyHttpUrl = Field(validation_alias=AliasChoices("API_URL"))
    supabase_url: AnyHttpUrl = Field(validation_alias=AliasChoices("SUPABASE_URL"))
    supabase_secret_key: SecretStr = Field(validation_alias=AliasChoices("SUPABASE_SECRET_KEY"))
    storage_bucket: str = Field(
        default="artifacts", validation_alias=AliasChoices("STORAGE_BUCKET")
    )
    malware_scanner_url: str = Field(
        default="", validation_alias=AliasChoices("MALWARE_SCANNER_URL")
    )


@lru_cache
def get_settings() -> WorkerSettings:
    return WorkerSettings()  # type: ignore[call-arg]
