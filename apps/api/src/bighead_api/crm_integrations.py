import hashlib
import json
from datetime import datetime
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import Field, field_validator

from bighead_api.identity.dependencies import TenantContext, tenant_context
from bighead_api.identity.models import ApiModel
from bighead_api.identity.repository import Database

router = APIRouter(prefix="/v1/crm", tags=["crm-integrations"])


def _secret_reference(organization_id: UUID, provider_key: str) -> str:
    provider_hash = hashlib.sha256(provider_key.encode()).hexdigest()[:24].upper()
    return f"env://CRM_SECRET_{organization_id.hex.upper()}_{provider_hash}"


class CrmConnectionCreate(ApiModel):
    provider_key: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,62}$")
    display_name: str = Field(min_length=1, max_length=200)
    configuration: dict[str, Any] = Field(default_factory=dict)

    @field_validator("configuration")
    @classmethod
    def configuration_has_no_secrets_or_endpoints(cls, value: dict[str, Any]) -> dict[str, Any]:
        forbidden = (
            "secret",
            "token",
            "password",
            "api_key",
            "apikey",
            "access_token",
            "client_secret",
            "authorization",
            "url",
            "endpoint",
        )

        def inspect(item: Any) -> None:
            if isinstance(item, dict):
                for key, nested in item.items():
                    if any(marker in str(key).lower() for marker in forbidden):
                        raise ValueError(
                            "configuration cannot contain secrets or provider endpoints"
                        )
                    inspect(nested)
            elif isinstance(item, list):
                for nested in item:
                    inspect(nested)

        inspect(value)
        return value


class CrmConnection(ApiModel):
    id: UUID
    provider_key: str
    display_name: str
    status: str
    configuration: dict[str, Any]
    last_synced_at: datetime | None = None


def _database(request: Request) -> Database:
    return cast(Database, request.app.state.database)


def _admin(context: TenantContext) -> UUID:
    if context.membership.role.value not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="CRM connection administration requires admin")
    if context.user.id is None:
        raise HTTPException(status_code=401, detail="Authenticated user required")
    return context.user.id


def _user(context: TenantContext) -> UUID:
    if context.user.id is None:
        raise HTTPException(status_code=401, detail="Authenticated user required")
    return context.user.id


@router.get("/connections", response_model=list[CrmConnection], operation_id="crmConnectionsGet")
async def list_connections(
    context: Annotated[TenantContext, Depends(tenant_context)],
    database: Annotated[Database, Depends(_database)],
) -> list[dict[str, Any]]:
    async with database.authenticated(_user(context), context.organization_id) as conn:
        rows = await conn.fetch(
            """select id,provider_key,display_name,status,configuration,last_synced_at
                 from public.crm_connections where organization_id=$1 order by created_at desc""",
            context.organization_id,
        )
    return [
        {**dict(row), "configuration": _sanitize_configuration(row["configuration"])}
        for row in rows
    ]


@router.post(
    "/connections",
    response_model=CrmConnection,
    status_code=status.HTTP_201_CREATED,
    operation_id="crmConnectionsPost",
)
async def create_connection(
    payload: CrmConnectionCreate,
    context: Annotated[TenantContext, Depends(tenant_context)],
    database: Annotated[Database, Depends(_database)],
) -> dict[str, Any]:
    user_id = _admin(context)
    secret_ref = _secret_reference(context.organization_id, payload.provider_key)
    async with database.authenticated(user_id, context.organization_id) as conn:
        row = await conn.fetchrow(
            """insert into public.crm_connections
                 (organization_id,provider_key,display_name,secret_ref,webhook_secret_ref,configuration,created_by)
               values($1,$2,$3,$4,$5,$6::jsonb,$7)
               returning id,provider_key,display_name,status,configuration,last_synced_at""",
            context.organization_id,
            payload.provider_key,
            payload.display_name,
            secret_ref,
            None,
            json.dumps(payload.configuration),
            user_id,
        )
    return dict(cast(Any, row))


@router.post(
    "/connections/{connection_id}/sync", status_code=202, operation_id="crmConnectionSyncPost"
)
async def request_sync(
    connection_id: UUID,
    context: Annotated[TenantContext, Depends(tenant_context)],
    database: Annotated[Database, Depends(_database)],
) -> dict[str, Any]:
    user_id = _admin(context)
    async with database.privileged() as conn:
        row = await conn.fetchrow(
            """select id from public.crm_connections c where c.id=$1 and c.organization_id=$2
               and exists(select 1 from public.organization_members m where m.organization_id=$2
                 and m.user_id=$3 and m.status='active' and m.role in ('owner','admin'))""",
            connection_id,
            context.organization_id,
            user_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="CRM connection not found")
        job_id = await conn.fetchval(
            "select public.request_crm_sync($1,$2)", connection_id, user_id
        )
    return {"connectionId": connection_id, "jobId": job_id, "status": "queued"}


def _sanitize_configuration(value: Any) -> dict[str, Any]:
    forbidden = (
        "secret",
        "token",
        "password",
        "api_key",
        "apikey",
        "access_token",
        "client_secret",
        "authorization",
    )
    if not isinstance(value, dict):
        return {}
    result: dict[str, Any] = {}
    for key, item in value.items():
        if any(marker in str(key).lower() for marker in forbidden):
            result[str(key)] = "[REDACTED]"
        elif isinstance(item, dict):
            result[str(key)] = _sanitize_configuration(item)
        elif isinstance(item, list):
            result[str(key)] = [
                _sanitize_configuration(entry) if isinstance(entry, dict) else entry
                for entry in item
            ]
        else:
            result[str(key)] = item
    return result
