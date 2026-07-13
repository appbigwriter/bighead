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
        default="", validation_alias=AliasChoices("LLM_PROVIDER_DEFAULT")
    )
    llm_provider_fallback: str = Field(
        default="", validation_alias=AliasChoices("LLM_PROVIDER_FALLBACK")
    )
    llm_model_default: str = Field(default="", validation_alias=AliasChoices("LLM_MODEL_DEFAULT"))
    llm_model_fallback: str = Field(default="", validation_alias=AliasChoices("LLM_MODEL_FALLBACK"))
    llm_timeout_seconds: int = Field(
        default=60, ge=1, le=3600, validation_alias=AliasChoices("LLM_TIMEOUT_SECONDS")
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
        providers = {"openai", "anthropic", "google"}
        if (
            self.llm_provider_default not in providers
            or self.llm_provider_fallback not in providers
        ):
            raise ValueError(
                "LLM default and fallback providers must be openai, anthropic or google."
            )
        if self.llm_provider_default == self.llm_provider_fallback:
            raise ValueError("LLM fallback provider must differ from the default provider.")
        if not self.llm_model_default.strip() or not self.llm_model_fallback.strip():
            raise ValueError("LLM default and fallback models are required.")
        llm_keys = {
            "openai": self.openai_api_key,
            "anthropic": self.anthropic_api_key,
            "google": self.google_genai_api_key,
        }
        for provider in {self.llm_provider_default, self.llm_provider_fallback}:
            value = llm_keys[provider].get_secret_value().strip()
            if (
                len(value) < 20
                or "optional_until" in value.lower()
                or "placeholder" in value.lower()
            ):
                raise ValueError(f"A production API key is required for LLM provider {provider}.")
        if self.crm_provider_endpoints.strip() in {"", "{}"}:
            raise ValueError("CRM_PROVIDER_ENDPOINTS is required in production.")
        for name, value in {
            "SUPABASE_URL": str(self.supabase_url),
            "MALWARE_SCANNER_URL": self.malware_scanner_url,
            "RUN_PROVIDER_URL": self.run_provider_url,
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
        if len(provider_key) < 24 or "placeholder" in provider_key.lower():
            raise ValueError("RUN_PROVIDER_API_KEY must be a non-placeholder server secret.")
        return self


@lru_cache
def get_settings() -> WorkerSettings:
    return WorkerSettings()  # type: ignore[call-arg]
