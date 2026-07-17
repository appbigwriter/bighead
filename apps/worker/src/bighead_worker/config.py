from functools import lru_cache
from urllib.parse import urlparse

from pydantic import AliasChoices, AnyHttpUrl, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env.local", ".env"), env_ignore_empty=True, extra="ignore"
    )

    app_env: str = Field(validation_alias=AliasChoices("APP_ENV"))
    log_level: str = Field(default="INFO", validation_alias=AliasChoices("LOG_LEVEL"))
    redis_url: SecretStr = Field(validation_alias=AliasChoices("REDIS_URL"))
    queue_name: str = Field(validation_alias=AliasChoices("QUEUE_NAME"))
    job_lease_seconds: int = Field(
        ge=10, le=86400, validation_alias=AliasChoices("JOB_LEASE_SECONDS")
    )
    otel_service_name: str = Field(validation_alias=AliasChoices("OTEL_SERVICE_NAME"))
    otel_exporter_otlp_endpoint: AnyHttpUrl | None = Field(
        default=None, validation_alias=AliasChoices("OTEL_EXPORTER_OTLP_ENDPOINT")
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
    run_provider_url: str = Field(default="", validation_alias=AliasChoices("RUN_PROVIDER_URL"))
    run_provider_api_key: SecretStr = Field(
        default=SecretStr(""), validation_alias=AliasChoices("RUN_PROVIDER_API_KEY")
    )
    run_provider_timeout_seconds: int = Field(
        default=60,
        ge=1,
        le=3600,
        validation_alias=AliasChoices("RUN_PROVIDER_TIMEOUT_SECONDS"),
    )
    llm_provider_default: str = Field(
        default="hermes", validation_alias=AliasChoices("LLM_PROVIDER_DEFAULT")
    )
    llm_provider_fallback: str = Field(
        default="", validation_alias=AliasChoices("LLM_PROVIDER_FALLBACK")
    )
    llm_model_default: str = Field(
        default="hermes", validation_alias=AliasChoices("LLM_MODEL_DEFAULT")
    )
    llm_model_fallback: str = Field(default="", validation_alias=AliasChoices("LLM_MODEL_FALLBACK"))
    llm_timeout_seconds: int = Field(
        default=60, ge=1, le=3600, validation_alias=AliasChoices("LLM_TIMEOUT_SECONDS")
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
    knowledge_backend: str = Field(
        default="anythingllm", validation_alias=AliasChoices("KNOWLEDGE_BACKEND")
    )
    knowledge_backend_required: bool = Field(
        default=True, validation_alias=AliasChoices("KNOWLEDGE_BACKEND_REQUIRED")
    )
    openai_api_key: SecretStr = Field(
        default=SecretStr(""), validation_alias=AliasChoices("OPENAI_API_KEY")
    )
    anthropic_api_key: SecretStr = Field(
        default=SecretStr(""), validation_alias=AliasChoices("ANTHROPIC_API_KEY")
    )
    google_genai_api_key: SecretStr = Field(
        default=SecretStr(""), validation_alias=AliasChoices("GOOGLE_GENAI_API_KEY")
    )
    crm_provider_endpoints: str = Field(
        default="{}", validation_alias=AliasChoices("CRM_PROVIDER_ENDPOINTS")
    )

    @field_validator("app_env")
    @classmethod
    def validate_app_env(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"development", "test", "staging", "production", "contract"}:
            raise ValueError("APP_ENV must be development, test, staging, production or contract.")
        return normalized

    @field_validator("otel_exporter_otlp_endpoint", mode="before")
    @classmethod
    def blank_otel_endpoint_is_disabled(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value

    @model_validator(mode="after")
    def validate_remote_environment(self) -> WorkerSettings:
        provider_url = self.run_provider_url.strip()
        provider_key = self.run_provider_api_key.get_secret_value().strip()
        if bool(provider_url) != bool(provider_key):
            raise ValueError(
                "RUN_PROVIDER_URL and RUN_PROVIDER_API_KEY must be configured together."
            )
        if self.app_env not in {"staging", "production"}:
            return self
        providers = {"openai", "anthropic", "google", "hermes"}
        if self.llm_provider_default not in providers or (
            self.llm_provider_fallback and self.llm_provider_fallback not in providers
        ):
            raise ValueError(
                "LLM default and fallback providers must be openai, anthropic, google or hermes."
            )
        if self.llm_provider_default == self.llm_provider_fallback:
            raise ValueError("LLM fallback provider must differ from the default provider.")
        if not self.llm_model_default.strip() or (
            self.llm_provider_fallback and not self.llm_model_fallback.strip()
        ):
            raise ValueError("LLM default and fallback models are required.")
        llm_keys = {
            "openai": self.openai_api_key,
            "anthropic": self.anthropic_api_key,
            "google": self.google_genai_api_key,
            "hermes": self.hermes_api_key,
        }
        for provider in {self.llm_provider_default, self.llm_provider_fallback}:
            if not provider:
                continue
            value = llm_keys[provider].get_secret_value().strip()
            if (
                len(value) < 20
                or "optional_until" in value.lower()
                or "placeholder" in value.lower()
            ):
                raise ValueError(f"A production API key is required for LLM provider {provider}.")

        if self.knowledge_backend == "anythingllm" and self.knowledge_backend_required:
            anything_key = self.anything_llm_api_key.get_secret_value().strip()
            if (
                len(anything_key) < 20
                or "optional_until" in anything_key.lower()
                or "placeholder" in anything_key.lower()
            ):
                raise ValueError("A production API key is required for AnythingLLM.")
        for name, value in {
            "SUPABASE_URL": str(self.supabase_url),
        }.items():
            lowered = value.lower()
            if (
                not lowered.startswith("https://")
                or "localhost" in lowered
                or "127.0.0.1" in lowered
            ):
                raise ValueError(f"{name} must be a non-local HTTPS URL in {self.app_env}.")
        redis_url = self.redis_url.get_secret_value()
        parsed_redis = urlparse(redis_url)
        redis_host = (parsed_redis.hostname or "").lower()
        is_private_docker_redis = (
            parsed_redis.scheme == "redis"
            and bool(redis_host)
            and "." not in redis_host
            and redis_host not in {"localhost"}
            and bool(parsed_redis.password)
        )
        is_tls_redis = parsed_redis.scheme == "rediss" and redis_host not in {
            "localhost",
            "127.0.0.1",
            "::1",
        }
        if not (is_private_docker_redis or is_tls_redis):
            raise ValueError(
                "REDIS_URL must use rediss:// or an authenticated private "
                f"Docker host in {self.app_env}."
            )
        secret = self.supabase_secret_key.get_secret_value().strip()
        if len(secret) < 24 or "placeholder" in secret.lower():
            raise ValueError("SUPABASE_SECRET_KEY must be a non-placeholder server secret.")
        scanner_url = urlparse(self.malware_scanner_url)
        if scanner_url.scheme == "clamd":
            if (
                not scanner_url.hostname
                or "." in scanner_url.hostname
                or scanner_url.hostname in {"localhost", "127.0.0.1", "::1"}
                or scanner_url.username
                or scanner_url.password
                or scanner_url.path not in {"", "/"}
                or scanner_url.query
                or scanner_url.fragment
            ):
                raise ValueError(
                    "MALWARE_SCANNER_URL clamd:// must target a private Docker service."
                )
        elif scanner_url.scheme == "https" and scanner_url.hostname not in {
            "localhost",
            "127.0.0.1",
            "::1",
        }:
            scanner_secret = self.malware_scanner_api_key.get_secret_value().strip()
            if len(scanner_secret) < 24 or "placeholder" in scanner_secret.lower():
                raise ValueError("MALWARE_SCANNER_API_KEY must be a non-placeholder server secret.")
        else:
            raise ValueError("MALWARE_SCANNER_URL must use private clamd:// or non-local https://.")
        if provider_key and (len(provider_key) < 24 or "placeholder" in provider_key.lower()):
            raise ValueError("RUN_PROVIDER_API_KEY must be a non-placeholder server secret.")
        if provider_url:
            lowered = provider_url.lower()
            if (
                not lowered.startswith("https://")
                or "localhost" in lowered
                or "127.0.0.1" in lowered
            ):
                raise ValueError(
                    f"RUN_PROVIDER_URL must be a non-local HTTPS URL in {self.app_env}."
                )
        return self


@lru_cache
def get_settings() -> WorkerSettings:
    return WorkerSettings()  # type: ignore[call-arg]
