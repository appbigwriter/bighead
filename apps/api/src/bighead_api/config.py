from functools import lru_cache
from typing import Annotated, Any, cast
from urllib.parse import parse_qs, urlparse

from pydantic import AliasChoices, AnyHttpUrl, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env.local", ".env"),
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
    database_service_url: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("DATABASE_SERVICE_URL")
    )
    supabase_url: AnyHttpUrl = Field(validation_alias=AliasChoices("SUPABASE_URL"))
    supabase_public_url: AnyHttpUrl | None = Field(
        default=None, validation_alias=AliasChoices("SUPABASE_PUBLIC_URL")
    )
    supabase_publishable_key: SecretStr = Field(
        validation_alias=AliasChoices("SUPABASE_PUBLISHABLE_KEY")
    )
    supabase_secret_key: SecretStr = Field(validation_alias=AliasChoices("SUPABASE_SECRET_KEY"))
    storage_bucket: str = Field(validation_alias=AliasChoices("STORAGE_BUCKET"))
    redis_url: SecretStr = Field(validation_alias=AliasChoices("REDIS_URL"))
    queue_name: str = Field(validation_alias=AliasChoices("QUEUE_NAME"))
    job_lease_seconds: int = Field(validation_alias=AliasChoices("JOB_LEASE_SECONDS"))
    otel_service_name: str = Field(validation_alias=AliasChoices("OTEL_SERVICE_NAME"))
    otel_exporter_otlp_endpoint: AnyHttpUrl | None = Field(
        default=None, validation_alias=AliasChoices("OTEL_EXPORTER_OTLP_ENDPOINT")
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
    signed_url_ttl_seconds: int = Field(
        default=900, ge=60, le=86400, validation_alias=AliasChoices("SIGNED_URL_TTL_SECONDS")
    )
    hermes_api_url: AnyHttpUrl | str = Field(
        default="http://localhost:8642", validation_alias=AliasChoices("HERMES_API_URL")
    )
    hermes_api_key: SecretStr = Field(
        default=SecretStr(""), validation_alias=AliasChoices("HERMES_API_KEY")
    )
    hermes_profiles_dir: str = Field(
        default="", validation_alias=AliasChoices("HERMES_PROFILES_DIR")
    )
    hermes_default_model: str = Field(
        default="hermes", validation_alias=AliasChoices("HERMES_DEFAULT_MODEL")
    )
    hermes_timeout_seconds: int = Field(
        default=60, ge=1, le=3600, validation_alias=AliasChoices("HERMES_TIMEOUT_SECONDS")
    )
    anything_llm_api_url: AnyHttpUrl | str = Field(
        default="http://localhost:3001", validation_alias=AliasChoices("ANYTHING_LLM_API_URL")
    )
    anything_llm_api_key: SecretStr = Field(
        default=SecretStr(""), validation_alias=AliasChoices("ANYTHING_LLM_API_KEY")
    )
    anything_llm_default_workspace: str = Field(
        default="bighead-corporativo",
        validation_alias=AliasChoices("ANYTHING_LLM_DEFAULT_WORKSPACE"),
    )
    anything_llm_timeout_seconds: int = Field(
        default=60, ge=1, le=3600, validation_alias=AliasChoices("ANYTHING_LLM_TIMEOUT_SECONDS")
    )
    llm_provider_default: str = Field(
        default="hermes", validation_alias=AliasChoices("LLM_PROVIDER_DEFAULT")
    )
    knowledge_backend: str = Field(
        default="anythingllm", validation_alias=AliasChoices("KNOWLEDGE_BACKEND")
    )
    knowledge_backend_required: bool = Field(
        default=True, validation_alias=AliasChoices("KNOWLEDGE_BACKEND_REQUIRED")
    )

    @field_validator("app_env")
    @classmethod
    def validate_app_env(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"development", "test", "staging", "production", "contract"}:
            raise ValueError("APP_ENV must be development, test, staging, production or contract.")
        return normalized

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("database_url", "database_service_url", "redis_url", mode="before")
    @classmethod
    def reject_empty_secret_like_values(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            raise ValueError("Required setting cannot be blank.")
        return value

    @model_validator(mode="after")
    def validate_remote_environment(self) -> Settings:
        if self.app_env not in {"staging", "production"}:
            return self

        remote_urls = {
            "APP_URL": str(self.app_url),
            "API_URL": str(self.api_url),
            "SUPABASE_URL": str(self.supabase_url),
        }
        if self.supabase_public_url is not None:
            remote_urls["SUPABASE_PUBLIC_URL"] = str(self.supabase_public_url)
        for name, value in remote_urls.items():
            lowered = value.lower()
            if (
                not lowered.startswith("https://")
                or "localhost" in lowered
                or "127.0.0.1" in lowered
            ):
                raise ValueError(f"{name} must be a non-local HTTPS URL in {self.app_env}.")

        origins = [str(origin).rstrip("/") for origin in self.cors_origins]
        if not origins or any(
            origin == "*"
            or not origin.startswith("https://")
            or "localhost" in origin.lower()
            or "127.0.0.1" in origin
            for origin in origins
        ):
            raise ValueError("CORS_ORIGINS must contain only explicit remote HTTPS origins.")

        placeholders = {"optional_until_provider_selected", "changeme", "placeholder"}
        required_secrets = {
            "SUPABASE_PUBLISHABLE_KEY": self.supabase_publishable_key,
            "SUPABASE_SECRET_KEY": self.supabase_secret_key,
            "ENCRYPTION_KEY": self.encryption_key,
            "WEBHOOK_SIGNING_SECRET": self.webhook_signing_secret,
            "PORTAL_TOKEN_PEPPER": self.portal_token_pepper,
        }
        for name, secret in required_secrets.items():
            value = secret.get_secret_value().strip()
            lowered = value.lower()
            if len(value) < 24 or any(marker in lowered for marker in placeholders):
                raise ValueError(f"{name} must be a non-placeholder secret of at least 24 chars.")

        transport_secrets = {"DATABASE_URL": self.database_url, "REDIS_URL": self.redis_url}
        for name, secret in transport_secrets.items():
            lowered = secret.get_secret_value().lower()
            if "localhost" in lowered or "127.0.0.1" in lowered:
                raise ValueError(f"{name} cannot target localhost in {self.app_env}.")
        database = urlparse(self.database_url.get_secret_value())
        sslmode = parse_qs(database.query).get("sslmode", [""])[0].lower()
        if database.scheme not in {"postgres", "postgresql"} or sslmode not in {
            "require",
            "verify-ca",
            "verify-full",
        }:
            raise ValueError("DATABASE_URL must require TLS in staging and production.")
        if self.database_service_url is None:
            raise ValueError("DATABASE_SERVICE_URL is required in staging and production.")
        service_value = self.database_service_url.get_secret_value()
        service_database = urlparse(service_value)
        service_sslmode = parse_qs(service_database.query).get("sslmode", [""])[0].lower()
        if service_database.scheme not in {"postgres", "postgresql"} or service_sslmode not in {
            "require",
            "verify-ca",
            "verify-full",
        }:
            raise ValueError("DATABASE_SERVICE_URL must require TLS in staging and production.")
        if not database.username or not service_database.username:
            raise ValueError("Database URLs must include explicit roles.")
        if database.username == service_database.username:
            raise ValueError("DATABASE_URL and DATABASE_SERVICE_URL must use distinct roles.")
        redis = urlparse(self.redis_url.get_secret_value())
        redis_host = (redis.hostname or "").lower()
        is_private_docker_redis = (
            redis.scheme == "redis"
            and bool(redis_host)
            and "." not in redis_host
            and redis_host not in {"localhost"}
            and bool(redis.password)
        )
        is_tls_redis = redis.scheme == "rediss" and redis_host not in {
            "localhost",
            "127.0.0.1",
            "::1",
        }
        if not (is_private_docker_redis or is_tls_redis):
            raise ValueError(
                "REDIS_URL must use rediss:// or an authenticated private "
                f"Docker host in {self.app_env}."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    # Values are loaded from the environment by pydantic-settings.
    settings_factory = cast(Any, Settings)
    return cast(Settings, settings_factory())
