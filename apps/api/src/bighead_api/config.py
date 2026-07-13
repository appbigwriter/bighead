from functools import lru_cache
from typing import Annotated, Any, cast

from pydantic import AliasChoices, AnyHttpUrl, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
    )

    app_env: str = Field(validation_alias=AliasChoices("APP_ENV"))
    app_url: AnyHttpUrl = Field(validation_alias=AliasChoices("APP_URL"))
    api_url: AnyHttpUrl = Field(validation_alias=AliasChoices("API_URL"))
    api_port: int = Field(default=8000, validation_alias=AliasChoices("API_PORT"))
    cors_origins: Annotated[list[AnyHttpUrl], NoDecode] = Field(
        validation_alias=AliasChoices("CORS_ORIGINS")
    )
    log_level: str = Field(default="INFO", validation_alias=AliasChoices("LOG_LEVEL"))
    database_url: SecretStr = Field(validation_alias=AliasChoices("DATABASE_URL"))
    direct_database_url: SecretStr = Field(validation_alias=AliasChoices("DIRECT_DATABASE_URL"))
    supabase_url: AnyHttpUrl = Field(validation_alias=AliasChoices("SUPABASE_URL"))
    supabase_publishable_key: SecretStr = Field(
        validation_alias=AliasChoices("SUPABASE_PUBLISHABLE_KEY")
    )
    supabase_secret_key: SecretStr = Field(validation_alias=AliasChoices("SUPABASE_SECRET_KEY"))
    storage_bucket: str = Field(validation_alias=AliasChoices("STORAGE_BUCKET"))
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
    sentry_dsn: str = Field(default="", validation_alias=AliasChoices("SENTRY_DSN"))
    encryption_key: SecretStr = Field(validation_alias=AliasChoices("ENCRYPTION_KEY"))
    webhook_signing_secret: SecretStr = Field(
        validation_alias=AliasChoices("WEBHOOK_SIGNING_SECRET")
    )
    portal_token_pepper: SecretStr = Field(validation_alias=AliasChoices("PORTAL_TOKEN_PEPPER"))

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("database_url", "direct_database_url", "redis_url", mode="before")
    @classmethod
    def reject_empty_secret_like_values(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            raise ValueError("Required setting cannot be blank.")
        return value


@lru_cache
def get_settings() -> Settings:
    # Values are loaded from the environment by pydantic-settings.
    settings_factory = cast(Any, Settings)
    return cast(Settings, settings_factory())
