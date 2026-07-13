from __future__ import annotations

import json
from base64 import urlsafe_b64decode, urlsafe_b64encode
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Protocol, cast
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import asyncpg
from fastapi import HTTPException

from bighead_api.administration.models import (
    AnalyticsView,
    AuditPage,
    ExperimentPage,
    ExperimentPatchRequest,
    OrganizationPatchRequest,
)
from bighead_api.identity.repository import Database


class AdministrationRepository(Protocol):
    async def experiments(self, user_id: UUID, organization_id: UUID) -> ExperimentPage: ...
    async def experiment(
        self, user_id: UUID, organization_id: UUID, experiment_id: UUID
    ) -> dict[str, Any]: ...
    async def patch_experiment(
        self,
        user_id: UUID,
        organization_id: UUID,
        experiment_id: UUID,
        payload: ExperimentPatchRequest,
    ) -> dict[str, Any]: ...
    async def analytics(
        self,
        user_id: UUID,
        organization_id: UUID,
        view: AnalyticsView,
        start: datetime,
        end: datetime,
        timezone: str | None,
        filters: dict[str, Any],
    ) -> dict[str, Any]: ...
    async def organization(self, user_id: UUID, organization_id: UUID) -> dict[str, Any]: ...
    async def patch_organization(
        self, user_id: UUID, organization_id: UUID, payload: OrganizationPatchRequest
    ) -> dict[str, Any]: ...
    async def integrations(
        self,
        user_id: UUID,
        organization_id: UUID,
        provider: str | None,
        status: str,
    ) -> dict[str, Any]: ...
    async def audit_events(
        self,
        user_id: UUID,
        organization_id: UUID,
        resource_type: str | None,
        actor_id: UUID | None,
        cursor: str | None,
        legal_hold: bool | None,
        limit: int,
    ) -> AuditPage: ...


class PostgresAdministrationRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def experiments(self, user_id: UUID, organization_id: UUID) -> ExperimentPage:
        async with self.database.authenticated(user_id, organization_id) as conn:
            rows = await conn.fetch(
                """select id,campaign_id,name,hypothesis,status::text,primary_metric,
                          allocation,stop_rule,starts_at,ends_at,result,created_at,updated_at
                     from public.experiments where organization_id=$1
                     order by updated_at desc limit 100""",
                organization_id,
            )
        items = [dict(row) for row in rows]
        return ExperimentPage(
            items=items, counters=dict(Counter(str(item["status"]) for item in items))
        )

    async def experiment(
        self, user_id: UUID, organization_id: UUID, experiment_id: UUID
    ) -> dict[str, Any]:
        async with self.database.authenticated(user_id, organization_id) as conn:
            experiment = await conn.fetchrow(
                "select * from public.experiments where id=$1 and organization_id=$2",
                experiment_id,
                organization_id,
            )
            variants = await conn.fetch(
                """select id,name,content_asset_id,weight,configuration,created_at
                     from public.experiment_variants where experiment_id=$1 and organization_id=$2
                     order by name""",
                experiment_id,
                organization_id,
            )
        if not experiment:
            raise HTTPException(status_code=404, detail="Experiment not found")
        immutable = [] if experiment["status"] == "draft" else ["hypothesis", "variants"]
        return {
            "experiment": dict(experiment),
            "variants": [dict(row) for row in variants],
            "result": experiment["result"],
            "immutableFields": immutable,
        }

    async def patch_experiment(
        self,
        user_id: UUID,
        organization_id: UUID,
        experiment_id: UUID,
        payload: ExperimentPatchRequest,
    ) -> dict[str, Any]:
        async with self.database.privileged() as conn:
            async with conn.transaction():
                current = await conn.fetchrow(
                    """select e.* from public.experiments e join public.organization_members m
                          on m.organization_id=e.organization_id and m.user_id=$3
                         and m.status='active' and m.role in ('owner','admin','analyst')
                        where e.id=$1 and e.organization_id=$2 for update of e""",
                    experiment_id,
                    organization_id,
                    user_id,
                )
                if not current:
                    raise HTTPException(status_code=404, detail="Experiment not found")
                if current["updated_at"] != payload.expected_updated_at:
                    raise HTTPException(status_code=409, detail="Experiment version conflict")
                if current["status"] != "draft" and (
                    payload.hypothesis or payload.variants is not None
                ):
                    raise HTTPException(
                        status_code=409, detail="Started experiment fields are immutable"
                    )
                starts_at = payload.window.get("start") if payload.window else None
                ends_at = payload.window.get("end") if payload.window else None
                row = await conn.fetchrow(
                    """update public.experiments set hypothesis=coalesce($3,hypothesis),
                              stop_rule=coalesce($4::jsonb,stop_rule),
                              starts_at=coalesce($5,starts_at),ends_at=coalesce($6,ends_at)
                        where id=$1 and organization_id=$2 returning *""",
                    experiment_id,
                    organization_id,
                    payload.hypothesis,
                    json.dumps(payload.stop_rule) if payload.stop_rule is not None else None,
                    starts_at,
                    ends_at,
                )
                if payload.variants is not None:
                    total = sum(item.weight for item in payload.variants)
                    if abs(total - 1.0) > 0.00001:
                        raise HTTPException(status_code=422, detail="Variant weights must total 1")
                    await conn.execute(
                        "delete from public.experiment_variants where experiment_id=$1",
                        experiment_id,
                    )
                    for variant in payload.variants:
                        await conn.execute(
                            """insert into public.experiment_variants(
                                   organization_id,experiment_id,name,content_asset_id,weight,configuration)
                               values($1,$2,$3,$4,$5,$6::jsonb)""",
                            organization_id,
                            experiment_id,
                            variant.name,
                            variant.content_asset_id,
                            variant.weight,
                            json.dumps(variant.configuration),
                        )
                await _emit(
                    conn,
                    organization_id,
                    "experiments.updated",
                    "experiment",
                    experiment_id,
                    {"updated_at": str(row["updated_at"])},
                )
        return await self.experiment(user_id, organization_id, experiment_id)

    async def analytics(
        self, user_id: UUID, organization_id: UUID, view: str, start: datetime, end: datetime
    ) -> dict[str, Any]:
        _validate_period(start, end)
        async with self.database.authenticated(user_id, organization_id) as conn:
            if view == "summary":
                row = await conn.fetchrow(
                    """select count(*) filter(where status='done') completed,
                              count(*) filter(where status='failed') failed,
                              count(*) total from public.tasks where organization_id=$1
                              and created_at between $2 and $3""",
                    organization_id,
                    start,
                    end,
                )
                return {"cards": [dict(row)], "alerts": [], "freshness": end}
            if view == "operations":
                rows = await conn.fetch(
                    """select status::text,count(*) count,
                              count(*) filter(
                                where sla_at<now() and status not in ('done','canceled')
                              ) breaches
                         from public.tasks where organization_id=$1 and created_at between $2 and $3
                         group by status order by status""",
                    organization_id,
                    start,
                    end,
                )
                return {
                    "trends": [dict(row) for row in rows],
                    "breaches": sum(row["breaches"] for row in rows),
                    "drilldowns": [],
                }
            if view == "agents":
                rows = await conn.fetch(
                    """select a.id,a.name,count(t.id) tasks,
                              count(t.id) filter(where t.status='failed') failures,
                              coalesce(sum(c.amount),0) cost
                         from public.agents a left join public.tasks t on t.agent_id=a.id
                           and t.created_at between $2 and $3
                         left join public.cost_events c on c.task_id=t.id
                        where a.organization_id=$1 group by a.id order by cost desc""",
                    organization_id,
                    start,
                    end,
                )
                return {
                    "metrics": [dict(row) for row in rows],
                    "degradations": [],
                    "costSpikes": [],
                }
            if view == "costs":
                rows = await conn.fetch(
                    """select currency,sum(amount) total,sum(input_tokens) input_tokens,
                              sum(output_tokens) output_tokens from public.cost_events
                         where organization_id=$1 and occurred_at between $2 and $3
                         group by currency""",
                    organization_id,
                    start,
                    end,
                )
                return {"totals": [dict(row) for row in rows], "budgetUsage": [], "quotaAlerts": []}
            if view == "funnel":
                rows = await conn.fetch(
                    """select event_name,count(*) count from public.analytics_events
                         where organization_id=$1 and occurred_at between $2 and $3
                         group by event_name order by count desc""",
                    organization_id,
                    start,
                    end,
                )
                revenue = await conn.fetchval(
                    """select coalesce(sum(amount),0) from public.opportunities
                         where organization_id=$1 and updated_at between $2 and $3
                           and stage='won'""",
                    organization_id,
                    start,
                    end,
                )
                return {
                    "stages": [dict(row) for row in rows],
                    "attributedRevenue": revenue,
                    "unknownSources": [],
                }
        raise HTTPException(status_code=404, detail="Analytics view not found")

    async def organization(self, user_id: UUID, organization_id: UUID) -> dict[str, Any]:
        async with self.database.authenticated(user_id, organization_id) as conn:
            row = await conn.fetchrow(
                """select id,name,slug,timezone,locale,settings,created_at,updated_at
                     from public.organizations where id=$1""",
                organization_id,
            )
        if not row:
            raise HTTPException(status_code=404, detail="Organization not found")
        settings = cast(dict[str, Any], row["settings"])
        return {
            "organization": dict(row),
            "brandingPreview": settings.get("branding", {}),
            "validation": [],
        }

    async def patch_organization(
        self, user_id: UUID, organization_id: UUID, payload: OrganizationPatchRequest
    ) -> dict[str, Any]:
        async with self.database.privileged() as conn:
            async with conn.transaction():
                current = await conn.fetchrow(
                    """select o.settings,o.updated_at from public.organizations o
                         join public.organization_members m on m.organization_id=o.id
                          and m.user_id=$2 and m.status='active' and m.role in ('owner','admin')
                        where o.id=$1 for update of o""",
                    organization_id,
                    user_id,
                )
                if not current:
                    raise HTTPException(status_code=404, detail="Organization not found")
                if current["updated_at"] != payload.expected_updated_at:
                    raise HTTPException(status_code=409, detail="Organization version conflict")
                settings = dict(current["settings"])
                for key, value in (
                    ("branding", payload.branding),
                    ("domains", payload.domains),
                    ("defaults", payload.defaults),
                ):
                    if value is not None:
                        settings[key] = value
                await conn.execute(
                    """update public.organizations
                          set timezone=coalesce($2,timezone),settings=$3::jsonb
                        where id=$1""",
                    organization_id,
                    payload.timezone,
                    json.dumps(settings),
                )
                await _emit(
                    conn,
                    organization_id,
                    "organization.updated",
                    "organization",
                    organization_id,
                    {"settings": list(settings)},
                )
        return await self.organization(user_id, organization_id)

    async def integrations(self, user_id: UUID, organization_id: UUID) -> dict[str, Any]:
        async with self.database.privileged() as conn:
            rows = await conn.fetch(
                """select id,url,event_types,is_enabled,created_at,updated_at
                     from public.webhook_endpoints w where organization_id=$1
                       and exists(select 1 from public.organization_members m
                         where m.organization_id=$1 and m.user_id=$2 and m.status='active'
                           and m.role in ('owner','admin')) order by updated_at desc""",
                organization_id,
                user_id,
            )
            if not rows:
                allowed = await conn.fetchval(
                    """select exists(select 1 from public.organization_members where
                         organization_id=$1 and user_id=$2 and status='active'
                         and role in ('owner','admin'))""",
                    organization_id,
                    user_id,
                )
                if not allowed:
                    raise HTTPException(status_code=403, detail="Administrator role required")
            pending = await conn.fetchval(
                """select count(*) from public.event_outbox
                    where organization_id=$1 and published_at is null""",
                organization_id,
            )
        return {
            "integrations": [dict(row) for row in rows],
            "webhooks": [dict(row) for row in rows],
            "deliveryHealth": {"pending": pending},
        }

    async def audit_events(
        self, user_id: UUID, organization_id: UUID, resource_type: str | None, actor_id: UUID | None
    ) -> AuditPage:
        async with self.database.authenticated(user_id, organization_id) as conn:
            rows = await conn.fetch(
                """select id,actor_user_id,actor_type,action,resource_type,resource_id,
                          risk_level::text,trace_id,changes_redacted,created_at
                     from public.audit_log where organization_id=$1
                      and ($2::text is null or resource_type=$2)
                      and ($3::uuid is null or actor_user_id=$3)
                     order by created_at desc,id desc limit 100""",
                organization_id,
                resource_type,
                actor_id,
            )
        return AuditPage(events=[dict(row) for row in rows])


def _validate_period(start: datetime, end: datetime) -> None:
    if end <= start or (end - start).days > 366:
        raise HTTPException(status_code=422, detail="Invalid analytics period")


async def _emit(
    conn: asyncpg.Connection[Any],
    organization_id: UUID,
    event_type: str,
    aggregate_type: str,
    aggregate_id: UUID,
    payload: dict[str, Any],
) -> None:
    await conn.execute(
        """insert into public.event_outbox(
               organization_id,event_type,aggregate_type,aggregate_id,payload)
           values($1,$2,$3,$4,$5::jsonb)""",
        organization_id,
        event_type,
        aggregate_type,
        aggregate_id,
        json.dumps(payload, default=str),
    )
