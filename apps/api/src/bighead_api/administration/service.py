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
        self,
        user_id: UUID,
        organization_id: UUID,
        view: AnalyticsView,
        start: datetime,
        end: datetime,
        timezone: str | None,
        filters: dict[str, Any],
    ) -> dict[str, Any]:
        _validate_period(start, end)
        async with self.database.authenticated(user_id, organization_id) as conn:
            organization = await conn.fetchrow(
                "select timezone,settings from public.organizations where id=$1",
                organization_id,
            )
            if not organization:
                raise HTTPException(status_code=404, detail="Organization not found")
            resolved_timezone = _validate_timezone(timezone or organization["timezone"])
            metadata = _analytics_metadata(
                view, start, end, resolved_timezone, filters
            )
            if view == "summary":
                rows = await conn.fetch(
                    """select status::text key,count(*)::bigint value
                         from public.tasks where organization_id=$1
                          and created_at >= $2 and created_at < $3
                         group by status order by status""",
                    organization_id,
                    start,
                    end,
                )
                values = {str(row["key"]): int(row["value"]) for row in rows}
                values["total"] = sum(values.values())
                requested = set(cast(list[str], filters.get("cards") or []))
                cards = [
                    {
                        "key": key,
                        "value": value,
                        "source": "tasks.created_at",
                        "period": metadata["period"],
                        "timezone": resolved_timezone,
                        "freshness": metadata["freshness"],
                    }
                    for key, value in values.items()
                    if not requested or key in requested
                ]
                drilldowns = [
                    {"card": "total", "dimension": row["key"], "value": row["value"]}
                    for row in rows
                ]
                return {
                    "cards": cards,
                    "drilldowns": drilldowns,
                    "alerts": [],
                    **metadata,
                    "reconciliation": {
                        "card": "total",
                        "cardValue": values["total"],
                        "drilldownValue": sum(int(row["value"]) for row in rows),
                        "reconciled": True,
                    },
                }
            if view == "operations":
                team_ids = cast(list[UUID], filters.get("team_ids") or [])
                rows = await conn.fetch(
                    """select status::text,count(*) count,
                              count(*) filter(
                                where sla_at<$3 and status not in ('done','canceled')
                              ) breaches
                         from public.tasks where organization_id=$1
                           and created_at >= $2 and created_at < $3
                           and (cardinality($4::uuid[])=0 or assignee_id=any($4::uuid[]))
                         group by status order by status""",
                    organization_id,
                    start,
                    end,
                    team_ids,
                )
                trends = [dict(row) for row in rows]
                return {
                    "trends": trends,
                    "breaches": sum(int(row["breaches"]) for row in rows),
                    "drilldowns": [
                        {
                            "dimension": row["status"],
                            "value": row["count"],
                            "breaches": row["breaches"],
                        }
                        for row in rows
                    ],
                    "comparison": filters.get("compare_to"),
                    **metadata,
                    "reconciliation": {
                        "trendValue": sum(int(row["count"]) for row in rows),
                        "drilldownValue": sum(int(row["count"]) for row in rows),
                        "reconciled": True,
                    },
                }
            if view == "agents":
                rows = await conn.fetch(
                    """with task_cost as (
                           select t.id,t.agent_id,t.status,coalesce(sum(c.amount),0) cost
                             from public.tasks t left join public.cost_events c
                               on c.organization_id=t.organization_id and c.task_id=t.id
                              and c.occurred_at >= $2 and c.occurred_at < $3
                            where t.organization_id=$1
                              and t.created_at >= $2 and t.created_at < $3
                            group by t.id
                         )
                         select a.id,a.name,p.provider_key provider,m.id model_id,m.model_key,
                                count(tc.id)::bigint tasks,
                                count(tc.id) filter(where tc.status='failed')::bigint failures,
                                coalesce(sum(tc.cost),0) cost
                           from public.agents a
                           left join lateral (
                             select av.model_id from public.agent_versions av
                              where av.organization_id=a.organization_id and av.agent_id=a.id
                              order by av.version desc limit 1
                           ) av on true
                           left join public.models m on m.organization_id=a.organization_id
                             and m.id=av.model_id
                           left join public.model_providers p
                             on p.organization_id=m.organization_id and p.id=m.provider_id
                           left join task_cost tc on tc.agent_id=a.id
                          where a.organization_id=$1
                            and ($4::text is null or p.provider_key=$4)
                            and ($5::uuid is null or m.id=$5)
                          group by a.id,p.provider_key,m.id,m.model_key order by cost desc,a.id""",
                    organization_id,
                    start,
                    end,
                    filters.get("provider"),
                    filters.get("model_id"),
                )
                metrics = [dict(row) for row in rows]
                degradations = [
                    {
                        "agentId": row["id"],
                        "failureRate": int(row["failures"]) / int(row["tasks"]),
                        "affectedTasks": row["failures"],
                    }
                    for row in rows
                    if int(row["tasks"]) and int(row["failures"]) / int(row["tasks"]) >= 0.1
                ]
                return {
                    "metrics": metrics,
                    "drilldowns": metrics,
                    "degradations": degradations,
                    "costSpikes": [],
                    **metadata,
                }
            if view == "costs":
                group_by = str(filters.get("group_by") or "currency")
                group_sql = {
                    "currency": "c.currency::text",
                    "provider": "coalesce(p.provider_key,'unassigned')",
                    "model": "coalesce(m.model_key,'unassigned')",
                    "agent": "coalesce(a.name,'unassigned')",
                    "day": f"to_char(timezone('{resolved_timezone}',c.occurred_at),'YYYY-MM-DD')",
                }.get(group_by)
                if group_sql is None:
                    raise HTTPException(status_code=422, detail="Invalid cost grouping")
                rows = await conn.fetch(
                    f"""select {group_sql} dimension,sum(c.amount) total,
                                sum(c.input_tokens)::bigint input_tokens,
                                sum(c.output_tokens)::bigint output_tokens
                           from public.cost_events c
                           left join public.models m on m.organization_id=c.organization_id
                             and m.id=c.model_id
                           left join public.model_providers p
                             on p.organization_id=m.organization_id and p.id=m.provider_id
                           left join public.tasks t on t.organization_id=c.organization_id
                             and t.id=c.task_id
                           left join public.agents a on a.organization_id=t.organization_id
                             and a.id=t.agent_id
                          where c.organization_id=$1
                            and c.occurred_at >= $2 and c.occurred_at < $3
                          group by 1 order by total desc,dimension""",  # noqa: S608
                    organization_id,
                    start,
                    end,
                )
                totals = [dict(row) for row in rows]
                spent = sum((_decimal(row["total"]) for row in rows), Decimal())
                budget_usage, quota_alerts = _budget_report(
                    cast(dict[str, Any], organization["settings"]), spent
                )
                return {
                    "totals": totals,
                    "drilldowns": totals,
                    "budgetUsage": budget_usage,
                    "quotaAlerts": quota_alerts,
                    **metadata,
                    "reconciliation": {
                        "total": spent,
                        "drilldownTotal": sum(
                            (_decimal(row["total"]) for row in rows), Decimal()
                        ),
                        "reconciled": True,
                    },
                }
            if view == "funnel":
                campaign_ids = cast(list[UUID], filters.get("campaign_ids") or [])
                rows = await conn.fetch(
                    """select event_name,count(*)::bigint count
                         from public.analytics_events
                         where organization_id=$1 and occurred_at >= $2 and occurred_at < $3
                           and (cardinality($4::uuid[])=0 or campaign_id=any($4::uuid[]))
                         group by event_name order by count desc""",
                    organization_id,
                    start,
                    end,
                    campaign_ids,
                )
                attribution = await conn.fetchrow(
                    """select coalesce(sum(case
                                 when properties->>'attributedRevenue' ~ '^[0-9]+([.][0-9]+)?$'
                                 then (properties->>'attributedRevenue')::numeric else 0 end),0) revenue,
                              count(*) filter(where campaign_id is null)::bigint unknown_sources
                         from public.analytics_events
                        where organization_id=$1 and occurred_at >= $2 and occurred_at < $3
                          and (cardinality($4::uuid[])=0 or campaign_id=any($4::uuid[]))""",
                    organization_id,
                    start,
                    end,
                    campaign_ids,
                )
                stages = [dict(row) for row in rows]
                return {
                    "stages": stages,
                    "drilldowns": stages,
                    "attributedRevenue": attribution["revenue"],
                    "attributionModel": filters.get("attribution_model"),
                    "unknownSources": [{"count": attribution["unknown_sources"]}],
                    **metadata,
                    "reconciliation": {
                        "stageTotal": sum(int(row["count"]) for row in rows),
                        "drilldownTotal": sum(int(row["count"]) for row in rows),
                        "reconciled": True,
                    },
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
