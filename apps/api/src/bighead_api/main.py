import re
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.trace import get_current_span
from starlette.responses import JSONResponse, Response
from structlog import get_logger
from structlog.contextvars import bind_contextvars, clear_contextvars

from bighead_api.administration.routes import router as administration_router
from bighead_api.administration.service import (
    AdministrationRepository,
    PostgresAdministrationRepository,
)
from bighead_api.artifacts.routes import router as artifacts_router
from bighead_api.artifacts.service import (
    ArtifactService,
    PostgresArtifactRepository,
    SupabaseStorageGateway,
)
from bighead_api.collaboration.routes import router as collaboration_router
from bighead_api.collaboration.service import (
    CollaborationRepository,
    PostgresCollaborationRepository,
)
from bighead_api.commercial.routes import router as commercial_router
from bighead_api.commercial.service import CommercialRepository, PostgresCommercialRepository
from bighead_api.config import Settings, get_settings
from bighead_api.crm_integrations import router as crm_integrations_router
from bighead_api.discovery.routes import router as discovery_router
from bighead_api.discovery.service import DiscoveryRepository
from bighead_api.errors import http_exception_handler, validation_exception_handler
from bighead_api.governance.routes import router as governance_router
from bighead_api.governance.service import GovernanceRepository, PostgresGovernanceRepository
from bighead_api.health import run_readiness_checks
from bighead_api.identity.auth import AuthProvider, SupabaseAuthProvider
from bighead_api.identity.repository import Database, IdentityRepository, PostgresIdentityRepository
from bighead_api.identity.routes import router as identity_router
from bighead_api.logging import configure_logging
from bighead_api.observability import configure_observability

logger = get_logger(__name__)
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def create_app(
    settings: Settings | None = None,
    *,
    auth_provider: AuthProvider | None = None,
    identity_repository: IdentityRepository | None = None,
    artifact_service: ArtifactService | None = None,
    governance_repository: GovernanceRepository | None = None,
    administration_repository: AdministrationRepository | None = None,
    collaboration_repository: CollaborationRepository | None = None,
    commercial_repository: CommercialRepository | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    database_url = getattr(resolved_settings, "database_url", None)
    dsn = (
        database_url.get_secret_value()
        if database_url is not None
        else "postgresql://postgres:postgres@localhost:5432/postgres"
    )
    service_url = getattr(resolved_settings, "database_service_url", None)
    service_dsn = service_url.get_secret_value() if service_url is not None else dsn
    database = Database(dsn, service_dsn)
    tracer_provider = configure_observability(resolved_settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        configure_logging(resolved_settings.log_level)
        logger.info("api.starting", app_env=resolved_settings.app_env)
        try:
            yield
        finally:
            close_auth = getattr(auth_provider, "close", None)
            if close_auth is not None:
                await close_auth()
            await database.close()
            if tracer_provider is not None:
                tracer_provider.shutdown()
            logger.info("api.stopped")

    app = FastAPI(
        title="BigHead API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin).rstrip("/") for origin in resolved_settings.cors_origins],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    if auth_provider is None:
        supabase_url = str(getattr(resolved_settings, "supabase_url", "http://localhost:54321"))
        publishable = getattr(resolved_settings, "supabase_publishable_key", None)
        secret = getattr(resolved_settings, "supabase_secret_key", None)
        auth_provider = SupabaseAuthProvider(
            base_url=supabase_url.rstrip("/"),
            publishable_key=(
                publishable.get_secret_value()
                if publishable is not None
                else "test-publishable-key"
            ),
            secret_key=secret.get_secret_value() if secret is not None else "test-secret-key",
        )
    app.state.auth_provider = auth_provider
    app.state.database = database
    app.state.identity_repository = identity_repository or PostgresIdentityRepository(database)
    if artifact_service is None:
        secret = getattr(resolved_settings, "supabase_secret_key", None)
        artifact_service = ArtifactService(
            repository=PostgresArtifactRepository(database),
            storage=SupabaseStorageGateway(
                base_url=str(
                    getattr(resolved_settings, "supabase_url", "http://localhost:54321")
                ).rstrip("/"),
                secret_key=secret.get_secret_value() if secret is not None else "test-secret-key",
                bucket=str(getattr(resolved_settings, "storage_bucket", "artifacts")),
                download_ttl_seconds=int(getattr(resolved_settings, "signed_url_ttl_seconds", 900)),
                public_base_url=str(
                    getattr(resolved_settings, "supabase_public_url", None)
                    or getattr(resolved_settings, "supabase_url", "http://localhost:54321")
                ).rstrip("/"),
            ),
        )
    app.state.artifact_service = artifact_service
    portal_pepper = getattr(resolved_settings, "portal_token_pepper", None)
    app.state.governance_repository = governance_repository or PostgresGovernanceRepository(
        database,
        portal_pepper.get_secret_value() if portal_pepper is not None else "test-portal-pepper",
        hermes_profiles_dir=str(getattr(resolved_settings, "hermes_profiles_dir", "")),
    )
    if administration_repository is None:
        secret = getattr(resolved_settings, "supabase_secret_key", None)
        administration_repository = PostgresAdministrationRepository(
            database,
            SupabaseStorageGateway(
                base_url=str(
                    getattr(resolved_settings, "supabase_url", "http://localhost:54321")
                ).rstrip("/"),
                secret_key=secret.get_secret_value() if secret is not None else "test-secret-key",
                bucket=str(getattr(resolved_settings, "storage_bucket", "artifacts")),
                download_ttl_seconds=int(getattr(resolved_settings, "signed_url_ttl_seconds", 900)),
                public_base_url=str(
                    getattr(resolved_settings, "supabase_public_url", None)
                    or getattr(resolved_settings, "supabase_url", "http://localhost:54321")
                ).rstrip("/"),
            ),
        )
    app.state.administration_repository = administration_repository
    app.state.collaboration_repository = (
        collaboration_repository or PostgresCollaborationRepository(database)
    )
    app.state.commercial_repository = commercial_repository or PostgresCommercialRepository(
        database
    )
    app.include_router(identity_router)
    app.include_router(artifacts_router)
    app.include_router(governance_router)
    app.include_router(administration_router)
    app.include_router(collaboration_router)
    app.include_router(commercial_router)
    app.include_router(crm_integrations_router)
    app.state.discovery_repository = DiscoveryRepository(database)
    app.include_router(discovery_router)

    @app.middleware("http")
    async def request_context(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        supplied_request_id = request.headers.get("x-request-id", "")
        request_id = (
            supplied_request_id
            if REQUEST_ID_PATTERN.fullmatch(supplied_request_id)
            else str(uuid4())
        )
        request.state.request_id = request_id
        span_context = get_current_span().get_span_context()
        context = {"request_id": request_id}
        if span_context.is_valid:
            context["trace_id"] = format(span_context.trace_id, "032x")
        bind_contextvars(**context)
        started = perf_counter()
        try:
            response = await call_next(request)
            response.headers["x-request-id"] = request_id
            logger.info(
                "api.request.completed",
                method=request.method,
                status_code=response.status_code,
                duration_ms=round((perf_counter() - started) * 1000, 2),
            )
            return response
        except Exception:
            logger.exception(
                "api.request.failed",
                method=request.method,
                duration_ms=round((perf_counter() - started) * 1000, 2),
            )
            raise
        finally:
            clear_contextvars()

    @app.get("/health/live", tags=["health"])
    async def live() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/health/ready", tags=["health"])
    async def ready() -> Response:
        result = await run_readiness_checks(resolved_settings)
        status = "ready" if result.ok else "degraded"
        return JSONResponse(
            {"status": status, "checks": result.checks}, status_code=200 if result.ok else 503
        )

    @app.get("/v1/meta/modules", tags=["meta"])
    async def list_modules() -> dict[str, list[str]]:
        return {
            "modules": [
                "identity",
                "organizations",
                "collaboration",
                "tasks",
                "orchestration",
                "agents",
                "skills",
                "workflows",
                "approvals",
                "artifacts",
                "memory",
                "crm",
                "content",
                "experiments",
                "analytics",
                "notifications",
                "audit",
            ]
        }

    FastAPIInstrumentor.instrument_app(app, tracer_provider=tracer_provider)
    return app


app = create_app()
