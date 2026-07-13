from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from starlette.responses import Response
from structlog import get_logger

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
from bighead_api.governance.routes import router as governance_router
from bighead_api.governance.service import GovernanceRepository, PostgresGovernanceRepository
from bighead_api.health import run_readiness_checks
from bighead_api.identity.auth import AuthProvider, SupabaseAuthProvider
from bighead_api.identity.repository import Database, IdentityRepository, PostgresIdentityRepository
from bighead_api.identity.routes import router as identity_router
from bighead_api.logging import configure_logging

logger = get_logger(__name__)


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
    database = Database(dsn)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        configure_logging(resolved_settings.log_level)
        logger.info("api.starting", app_env=resolved_settings.app_env)
        yield
        await database.close()
        logger.info("api.stopped")

    app = FastAPI(
        title="BigHead API",
        version="0.1.0",
        lifespan=lifespan,
    )
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
            ),
        )
    app.state.artifact_service = artifact_service
    portal_pepper = getattr(resolved_settings, "portal_token_pepper", None)
    app.state.governance_repository = governance_repository or PostgresGovernanceRepository(
        database,
        portal_pepper.get_secret_value() if portal_pepper is not None else "test-portal-pepper",
    )
    app.state.administration_repository = (
        administration_repository or PostgresAdministrationRepository(database)
    )
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

    @app.middleware("http")
    async def request_context(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("x-request-id", str(uuid4()))
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response

    @app.get("/health/live", tags=["health"])
    async def live() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/health/ready", tags=["health"])
    async def ready() -> dict[str, object]:
        result = await run_readiness_checks(resolved_settings)
        status = "ready" if result.ok else "degraded"
        return {"status": status, "checks": result.checks}

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

    FastAPIInstrumentor.instrument_app(app)
    return app


app = create_app()
