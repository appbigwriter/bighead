from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Mapping
from typing import Any, Protocol, cast
from uuid import UUID, uuid4

import asyncpg  # type: ignore[import-untyped]
from fastapi import HTTPException

from bighead_api.governance.models import (
    AgentPatchRequest,
    ApprovalDecisionRequest,
    ApprovalDecisionResponse,
    ApprovalPolicyPatchRequest,
    ApprovalPolicyResponse,
    Page,
    PlaybookInstantiateRequest,
    PlaybookInstantiateResponse,
    PortalDecisionRequest,
    SkillValidateRequest,
    SkillValidateResponse,
    WorkflowRollbackRequest,
    WorkflowValidateRequest,
    WorkflowValidateResponse,
)
from bighead_api.identity.repository import Database


class GovernanceRepository(Protocol):
    async def list_approvals(self, user_id: UUID, organization_id: UUID) -> Page: ...
    async def decide(
        self,
        user_id: UUID,
        organization_id: UUID,
        approval_id: UUID,
        payload: ApprovalDecisionRequest,
    ) -> ApprovalDecisionResponse: ...
    async def scorecard(
        self, user_id: UUID, organization_id: UUID, approval_id: UUID
    ) -> dict[str, Any]: ...
    async def get_policy(self, user_id: UUID, organization_id: UUID) -> ApprovalPolicyResponse: ...
    async def patch_policy(
        self, user_id: UUID, organization_id: UUID, payload: ApprovalPolicyPatchRequest
    ) -> ApprovalPolicyResponse: ...
    async def portal_item(self, token: str) -> dict[str, Any]: ...
    async def portal_decide(
        self, token: str, key: str, payload: PortalDecisionRequest
    ) -> ApprovalDecisionResponse: ...
    async def list_agents(self, user_id: UUID, organization_id: UUID) -> Page: ...
    async def agent_detail(
        self, user_id: UUID, organization_id: UUID, agent_id: UUID
    ) -> dict[str, Any]: ...
    async def patch_agent(
        self, user_id: UUID, organization_id: UUID, agent_id: UUID, payload: AgentPatchRequest
    ) -> dict[str, Any]: ...
    async def list_skills(self, user_id: UUID, organization_id: UUID) -> Page: ...
    async def validate_skill(
        self, user_id: UUID, organization_id: UUID, skill_id: UUID, payload: SkillValidateRequest
    ) -> SkillValidateResponse: ...
    async def list_models(self, user_id: UUID, organization_id: UUID) -> dict[str, Any]: ...
    async def list_prompts(self, user_id: UUID, organization_id: UUID) -> Page: ...
    async def list_workflows(self, user_id: UUID, organization_id: UUID) -> Page: ...

    async def validate_workflow(
        self,
        user_id: UUID,
        organization_id: UUID,
        workflow_id: UUID,
        payload: WorkflowValidateRequest,
    ) -> WorkflowValidateResponse: ...
    async def workflow_versions(
        self,
        user_id: UUID,
        organization_id: UUID,
        workflow_id: UUID,
        cursor: int | None,
        include_diff: bool,
    ) -> dict[str, Any]: ...
    async def rollback_workflow(
        self,
        user_id: UUID,
        organization_id: UUID,
        workflow_id: UUID,
        payload: WorkflowRollbackRequest,
    ) -> dict[str, Any]: ...
    async def instantiate(
        self,
        user_id: UUID,
        organization_id: UUID,
        playbook_id: UUID,
        key: str,
        payload: PlaybookInstantiateRequest,
    ) -> PlaybookInstantiateResponse: ...


class PostgresGovernanceRepository:
    def __init__(self, database: Database, portal_pepper: str) -> None:
        self.database = database
        self.portal_pepper = portal_pepper

    async def list_approvals(self, user_id: UUID, organization_id: UUID) -> Page:
        async with self.database.authenticated(user_id, organization_id) as conn:
            rows = await conn.fetch(
                """select ar.id,ar.task_id,ar.artifact_id,ar.assigned_to,ar.status::text,
                          ar.risk_level::text,ar.round,ar.due_at,ar.created_at,t.title
                     from public.approval_requests ar join public.tasks t on t.id=ar.task_id
                    where ar.organization_id=$1 order by ar.created_at desc limit 101""",
                organization_id,
            )
        items = [dict(row) for row in rows[:100]]
        return Page(items=items, counters=dict(Counter(str(item["status"]) for item in items)))

    async def decide(
        self,
        user_id: UUID,
        organization_id: UUID,
        approval_id: UUID,
        payload: ApprovalDecisionRequest,
    ) -> ApprovalDecisionResponse:
        async with self.database.privileged() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """insert into public.approval_decisions(
                           organization_id,approval_request_id,decision,decided_by,comment)
                       select ar.organization_id,ar.id,$4,$3,$5
                         from public.approval_requests ar
                         join public.organization_members m
                           on m.organization_id=ar.organization_id and m.user_id=$3
                         join public.organizations o on o.id=ar.organization_id
                        where ar.id=$1 and ar.organization_id=$2 and ar.status='pending'
                          and ar.round=$6 and m.status='active'
                          and (m.role in ('owner','admin')
                            or (m.role='reviewer' and ar.assigned_to=$3))
                          and (not coalesce(
                            (o.settings->'approval_policy'->>'segregation')::boolean,true)
                            or ar.requested_by is distinct from $3)
                       on conflict (approval_request_id) do nothing
                       returning id""",
                    approval_id,
                    organization_id,
                    user_id,
                    payload.decision,
                    payload.comment,
                    payload.expected_round,
                )
                if not row:
                    raise HTTPException(
                        status_code=409, detail="Approval already decided or round changed"
                    )
                approval = await conn.fetchrow(
                    """update public.approval_requests
                          set status=$3,decided_at=now()
                        where id=$1 and organization_id=$2 and status='pending' and round=$4
                    returning id,task_id,artifact_id,status::text,risk_level::text,
                              round,decided_at""",
                    approval_id,
                    organization_id,
                    payload.decision,
                    payload.expected_round,
                )
                if not approval:
                    raise HTTPException(status_code=409, detail="Approval changed concurrently")
                await self._continue_waiting_work(
                    conn, organization_id, approval["task_id"], payload.decision
                )
                await _emit(
                    conn,
                    organization_id,
                    "approvals.decided",
                    "approval",
                    approval_id,
                    {"decision": payload.decision, "round": payload.expected_round},
                )
        actions = ["resume_task"] if payload.decision == "approved" else ["return_to_author"]
        return ApprovalDecisionResponse(
            approval=dict(approval), round_result=payload.decision, next_actions=actions
        )

    async def scorecard(
        self, user_id: UUID, organization_id: UUID, approval_id: UUID
    ) -> dict[str, Any]:
        async with self.database.authenticated(user_id, organization_id) as conn:
            approval = await conn.fetchrow(
                """select task_id,artifact_id from public.approval_requests
                    where id=$1 and organization_id=$2""",
                approval_id,
                organization_id,
            )
            if not approval:
                raise HTTPException(status_code=404, detail="Approval not found")
            rows = await conn.fetch(
                """select e.id,e.score,e.passed,e.results,e.created_at,s.name,s.version,s.criteria,
                          s.pass_threshold
                     from public.qa_evaluations e join public.qa_scorecards s on s.id=e.scorecard_id
                    where e.organization_id=$1 and e.task_id=$2
                      and ($3::uuid is null or e.artifact_id=$3) order by e.created_at desc""",
                organization_id,
                approval["task_id"],
                approval["artifact_id"],
            )
        return {"scores": [dict(row) for row in rows], "policyFindings": [], "trend": []}

    async def get_policy(self, user_id: UUID, organization_id: UUID) -> ApprovalPolicyResponse:
        async with self.database.authenticated(user_id, organization_id) as conn:
            settings = await conn.fetchval(
                "select settings from public.organizations where id=$1", organization_id
            )
        if settings is None:
            raise HTTPException(status_code=404, detail="Organization not found")
        decoded = json.loads(settings) if isinstance(settings, str) else settings
        return _policy_response(cast(dict[str, Any], decoded).get("approval_policy", {}))

    async def patch_policy(
        self, user_id: UUID, organization_id: UUID, payload: ApprovalPolicyPatchRequest
    ) -> ApprovalPolicyResponse:
        policy = {
            "rules": payload.rules,
            "segregation": payload.segregation,
            "thresholds": payload.thresholds,
            "version": payload.expected_version + 1,
        }
        async with self.database.privileged() as conn:
            row = await conn.fetchrow(
                """update public.organizations
                      set settings=jsonb_set(settings,'{approval_policy}',$3::jsonb,true)
                    where id=$1 and coalesce((settings->'approval_policy'->>'version')::int,0)=$2
                      and exists(select 1 from public.organization_members m
                        where m.organization_id=$1 and m.user_id=$4 and m.status='active'
                          and m.role in ('owner','admin'))
                    returning settings->'approval_policy' as policy""",
                organization_id,
                payload.expected_version,
                json.dumps(policy),
                user_id,
            )
            if not row:
                raise HTTPException(status_code=409, detail="Approval policy version conflict")
            await _emit(
                conn,
                organization_id,
                "policy.updated",
                "organization",
                organization_id,
                {"version": policy["version"]},
            )
        return _policy_response(policy)

    async def portal_item(self, token: str) -> dict[str, Any]:
        token_hash = hashlib.sha256(f"{self.portal_pepper}:{token}".encode()).hexdigest()
        await self._consume_portal_rate_limit(token_hash, "view", 60)
        async with self.database.privileged() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """select l.organization_id,l.approval_request_id,ar.status::text,
                              ar.risk_level::text,ar.round,t.title,t.objective,l.expires_at
                         from public.external_approval_links l
                         join public.approval_requests ar on ar.id=l.approval_request_id
                           and ar.organization_id=l.organization_id
                         join public.tasks t on t.id=ar.task_id
                          and t.organization_id=l.organization_id
                        where l.token_hash=$1 and l.revoked_at is null and l.expires_at>now()
                          and l.use_count<l.max_uses""",
                    token_hash,
                )
                if not row:
                    raise HTTPException(
                        status_code=410, detail="Portal token expired or unavailable"
                    )
                await _emit(
                    conn,
                    row["organization_id"],
                    "portal.viewed",
                    "approval",
                    row["approval_request_id"],
                    {},
                )
        return {
            "item": dict(row),
            "allowedActions": ["approve", "request_changes"],
            "portalBranding": {},
            "state": row["status"],
        }

    async def portal_decide(
        self, token: str, key: str, payload: PortalDecisionRequest
    ) -> ApprovalDecisionResponse:
        token_hash = hashlib.sha256(f"{self.portal_pepper}:{token}".encode()).hexdigest()
        await self._consume_portal_rate_limit(token_hash, "decision", 10)
        async with self.database.privileged() as conn:
            async with conn.transaction():
                await conn.execute(
                    "select pg_advisory_xact_lock(hashtextextended($1,0))",
                    f"portal:{token_hash}",
                )
                link = await conn.fetchrow(
                    """select l.id,l.organization_id,l.approval_request_id,l.use_count,l.max_uses,
                              ar.task_id,ar.round,ar.status::text
                         from public.external_approval_links l
                         join public.approval_requests ar on ar.id=l.approval_request_id
                          and ar.organization_id=l.organization_id
                        where l.token_hash=$1 and l.revoked_at is null and l.expires_at>now()
                        for update of l,ar""",
                    token_hash,
                )
                if not link:
                    raise HTTPException(
                        status_code=410, detail="Portal token expired or unavailable"
                    )
                replay = await conn.fetchrow(
                    """select ar.id,ar.task_id,ar.status::text,ar.risk_level::text,
                              ar.round,ar.decided_at,ad.decision::text,ad.comment
                         from public.approval_decisions ad
                         join public.approval_requests ar on ar.id=ad.approval_request_id
                          and ar.organization_id=ad.organization_id
                        where ad.organization_id=$1 and ad.approval_request_id=$2
                          and ad.idempotency_key=$3""",
                    link["organization_id"],
                    link["approval_request_id"],
                    key,
                )
                if replay:
                    if (
                        replay["decision"] != payload.decision
                        or replay["round"] != payload.expected_round
                        or replay["comment"] != payload.comment
                    ):
                        raise HTTPException(
                            status_code=409, detail="Idempotency-Key payload conflict"
                        )
                    return ApprovalDecisionResponse(
                        approval=dict(replay),
                        round_result=payload.decision,
                        next_actions=["resume_task"]
                        if payload.decision == "approved"
                        else ["return_to_author"],
                    )
                if (
                    link["use_count"] >= link["max_uses"]
                    or link["status"] != "pending"
                    or link["round"] != payload.expected_round
                ):
                    raise HTTPException(
                        status_code=410, detail="Portal token expired or unavailable"
                    )
                task_waiting = await conn.fetchval(
                    """select status='waiting_human' from public.tasks
                        where id=$1 and organization_id=$2 for update""",
                    link["task_id"],
                    link["organization_id"],
                )
                if task_waiting is not True:
                    raise HTTPException(status_code=409, detail="Task is not awaiting approval")
                decision = await conn.fetchrow(
                    """insert into public.approval_decisions(
                           organization_id,approval_request_id,decision,external_reviewer_name,
                           comment,idempotency_key)
                       values($1,$2,$3,'external portal',$4,$5)
                       returning id""",
                    link["organization_id"],
                    link["approval_request_id"],
                    payload.decision,
                    payload.comment,
                    key,
                )
                if not decision:
                    raise HTTPException(status_code=409, detail="Approval already decided")
                approval = await conn.fetchrow(
                    """update public.approval_requests set status=$3,decided_at=now()
                        where id=$1 and organization_id=$2 and status='pending'
                        returning id,task_id,artifact_id,status::text,risk_level::text,
                                  round,decided_at""",
                    link["approval_request_id"],
                    link["organization_id"],
                    payload.decision,
                )
                await conn.execute(
                    "update public.external_approval_links set use_count=use_count+1 where id=$1",
                    link["id"],
                )
                await self._continue_waiting_work(
                    conn, link["organization_id"], link["task_id"], payload.decision
                )
                await _emit(
                    conn,
                    link["organization_id"],
                    "approvals.decided",
                    "approval",
                    link["approval_request_id"],
                    {"decision": payload.decision, "external": True},
                )
        return ApprovalDecisionResponse(
            approval=dict(approval),
            round_result=payload.decision,
            next_actions=["resume_task"]
            if payload.decision == "approved"
            else ["return_to_author"],
        )

    async def _consume_portal_rate_limit(self, token_hash: str, action: str, limit: int) -> None:
        async with self.database.privileged() as conn:
            async with conn.transaction():
                await conn.execute(
                    "select pg_advisory_xact_lock(hashtextextended($1,0))",
                    f"portal-rate:{token_hash}:{action}",
                )
                recent = await conn.fetchval(
                    """select count(*) from private.portal_access_events
                        where token_hash=$1 and action=$2
                          and occurred_at>now()-interval '1 minute'""",
                    token_hash,
                    action,
                )
                if recent >= limit:
                    raise HTTPException(status_code=429, detail="Portal rate limit exceeded")
                await conn.execute(
                    """insert into private.portal_access_events(token_hash,action)
                       values($1,$2)""",
                    token_hash,
                    action,
                )

    @staticmethod
    async def _continue_waiting_work(
        conn: Any, organization_id: UUID, task_id: UUID, decision: str
    ) -> None:
        if decision != "approved":
            return
        await conn.execute(
            """update public.tasks set status='approved',version=version+1
                where id=$1 and organization_id=$2 and status='waiting_human'""",
            task_id,
            organization_id,
        )
        await conn.execute(
            """update public.runs set status='queued',locked_by=null,locked_until=null
                where task_id=$1 and organization_id=$2 and status='waiting'""",
            task_id,
            organization_id,
        )

    async def list_agents(self, user_id: UUID, organization_id: UUID) -> Page:
        return await self._simple_page(
            user_id,
            organization_id,
            "agents",
        )

    async def agent_detail(
        self, user_id: UUID, organization_id: UUID, agent_id: UUID
    ) -> dict[str, Any]:
        async with self.database.authenticated(user_id, organization_id) as conn:
            agent = await conn.fetchrow(
                "select * from public.agents where id=$1 and organization_id=$2",
                agent_id,
                organization_id,
            )
            versions = await conn.fetch(
                """select id,version,model_id,system_prompt,configuration,published_at,created_at
                     from public.agent_versions where agent_id=$1 and organization_id=$2
                     order by version desc""",
                agent_id,
                organization_id,
            )
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        return {
            "agent": dict(agent),
            "versions": [dict(row) for row in versions],
            "consumers": [],
            "confidence": float(agent["trust_score"]),
        }

    async def patch_agent(
        self, user_id: UUID, organization_id: UUID, agent_id: UUID, payload: AgentPatchRequest
    ) -> dict[str, Any]:
        async with self.database.privileged() as conn:
            async with conn.transaction():
                current = await conn.fetchrow(
                    """select a.*,coalesce(max(v.version),0) current_version
                         from public.agents a left join public.agent_versions v on v.agent_id=a.id
                        join public.organization_members m on m.organization_id=a.organization_id
                          and m.user_id=$3 and m.status='active' and m.role in ('owner','admin')
                        where a.id=$1 and a.organization_id=$2 group by a.id""",
                    agent_id,
                    organization_id,
                    user_id,
                )
                if not current:
                    raise HTTPException(status_code=404, detail="Agent not found")
                if current["current_version"] != payload.expected_version:
                    raise HTTPException(status_code=409, detail="Agent version conflict")
                if payload.is_enabled is False:
                    in_use = await conn.fetchval(
                        """select exists(select 1 from public.tasks where organization_id=$1
                              and agent_id=$2 and status not in ('done','canceled'))""",
                        organization_id,
                        agent_id,
                    )
                    if in_use:
                        raise HTTPException(status_code=409, detail="Agent has active consumers")
                await conn.execute(
                    """update public.agents set description=coalesce($3,description),
                              is_enabled=coalesce($4,is_enabled)
                        where id=$1 and organization_id=$2""",
                    agent_id,
                    organization_id,
                    payload.description,
                    payload.is_enabled,
                )
                if payload.prompt is not None:
                    version_id = uuid4()
                    inserted_version = await conn.fetchval(
                        """insert into public.agent_versions(
                               id,organization_id,agent_id,version,model_id,
                               system_prompt,configuration,created_by)
                           values($1,$2,$3,$4,$5,$6,$7::jsonb,$8)
                           on conflict (agent_id,version) do nothing returning id""",
                        version_id,
                        organization_id,
                        agent_id,
                        payload.expected_version + 1,
                        payload.model_id,
                        payload.prompt,
                        json.dumps({"limits": payload.limits}),
                        user_id,
                    )
                    if inserted_version is None:
                        raise HTTPException(status_code=409, detail="Agent changed concurrently")
                    for skill_id in dict.fromkeys(payload.skill_ids or []):
                        result = await conn.execute(
                            """insert into public.agent_version_skills(
                                   organization_id,agent_version_id,skill_id)
                               select $1,$2,id from public.skills
                                where id=$3 and organization_id=$1""",
                            organization_id,
                            version_id,
                            skill_id,
                        )
                        if result == "INSERT 0 0":
                            raise HTTPException(
                                status_code=422, detail=f"Skill {skill_id} not found"
                            )
                await _emit(
                    conn,
                    organization_id,
                    "agents.updated",
                    "agent",
                    agent_id,
                    {"version": payload.expected_version + (payload.prompt is not None)},
                )
        return await self.agent_detail(user_id, organization_id, agent_id)

    async def list_skills(self, user_id: UUID, organization_id: UUID) -> Page:
        return await self._simple_page(
            user_id,
            organization_id,
            "skills",
        )

    async def validate_skill(
        self, user_id: UUID, organization_id: UUID, skill_id: UUID, payload: SkillValidateRequest
    ) -> SkillValidateResponse:
        async with self.database.privileged() as conn:
            skill = await conn.fetchrow(
                """select s.input_schema,s.is_enabled,s.timeout_seconds,s.max_retries
                     from public.skills s
                    join public.organization_members m on m.organization_id=s.organization_id
                      and m.user_id=$3 and m.status='active' and m.role in ('owner','admin')
                    where s.id=$1 and s.organization_id=$2""",
                skill_id,
                organization_id,
                user_id,
            )
            if not skill:
                raise HTTPException(status_code=404, detail="Skill not found")
            findings = _validate_payload(payload.payload, skill["input_schema"])
            if not skill["is_enabled"]:
                findings.append("Skill is disabled")
            if payload.timeout_ms > skill["timeout_seconds"] * 1000:
                findings.append("Requested timeout exceeds skill limit")
            if payload.retries > skill["max_retries"]:
                findings.append("Requested retries exceed skill limit")
            redactions = _sensitive_paths(payload.payload)
            run_id = uuid4()
            await _emit(
                conn,
                organization_id,
                "skills.validation.completed",
                "skill",
                skill_id,
                {"run_id": str(run_id), "valid": not findings, "redactions": redactions},
            )
        return SkillValidateResponse(
            run_id=run_id,
            status="rejected" if findings else "accepted",
            findings=findings,
            redactions=redactions,
        )

    async def list_models(self, user_id: UUID, organization_id: UUID) -> dict[str, Any]:
        async with self.database.authenticated(user_id, organization_id) as conn:
            providers = await conn.fetch(
                """select id,name,provider_key,is_enabled,settings
                     from public.model_providers where organization_id=$1 order by name""",
                organization_id,
            )
            models = await conn.fetch(
                """select id,provider_id,model_key,capabilities,input_cost_per_million,
                          output_cost_per_million,price_valid_from,is_enabled from public.models
                     where organization_id=$1 order by model_key""",
                organization_id,
            )
        return {
            "providers": [dict(row) for row in providers],
            "models": [dict(row) for row in models],
            "priceTables": [dict(row) for row in models],
        }

    async def list_prompts(self, user_id: UUID, organization_id: UUID) -> Page:
        async with self.database.authenticated(user_id, organization_id) as conn:
            rows = await conn.fetch(
                """select v.id,v.agent_id,a.name as agent_name,v.version,v.system_prompt,
                          v.published_at,v.created_at from public.agent_versions v
                     join public.agents a on a.id=v.agent_id where v.organization_id=$1
                     order by v.created_at desc limit 100""",
                organization_id,
            )
        return Page(items=[dict(row) for row in rows])

    async def list_workflows(self, user_id: UUID, organization_id: UUID) -> Page:
        return await self._simple_page(
            user_id,
            organization_id,
            "workflows",
        )

    async def validate_workflow(
        self,
        user_id: UUID,
        organization_id: UUID,
        workflow_id: UUID,
        payload: WorkflowValidateRequest,
    ) -> WorkflowValidateResponse:
        async with self.database.authenticated(user_id, organization_id) as conn:
            exists = await conn.fetchval(
                "select exists(select 1 from public.workflows where id=$1 and organization_id=$2)",
                workflow_id,
                organization_id,
            )
        if not exists:
            raise HTTPException(status_code=404, detail="Workflow not found")
        return validate_workflow(payload)

    async def workflow_versions(
        self,
        user_id: UUID,
        organization_id: UUID,
        workflow_id: UUID,
        cursor: int | None,
        include_diff: bool,
    ) -> dict[str, Any]:
        async with self.database.authenticated(user_id, organization_id) as conn:
            rows = await conn.fetch(
                """select wv.id,wv.version,wv.definition,wv.published_at,wv.created_by,
                          wv.created_at,not exists(
                            select 1 from public.runs r join public.tasks t on t.id=r.task_id
                             where r.organization_id=wv.organization_id
                               and r.status in ('queued','running','waiting')
                               and (t.workflow_version_id=wv.id or r.workflow_version_id=wv.id)
                          ) rollback_safe
                     from public.workflow_versions wv
                    where wv.workflow_id=$1 and wv.organization_id=$2
                      and ($3::integer is null or wv.version<$3)
                    order by wv.version desc limit 51""",
                workflow_id,
                organization_id,
                cursor,
            )
        if not rows:
            raise HTTPException(status_code=404, detail="Workflow not found")
        page_rows = rows[:50]
        versions = []
        for row in page_rows:
            item = dict(row)
            if isinstance(item["definition"], str):
                item["definition"] = json.loads(item["definition"])
            versions.append(item)
        diffs = []
        if include_diff:
            for current, previous in zip(versions, versions[1:], strict=False):
                current_keys = set(current["definition"])
                previous_keys = set(previous["definition"])
                diffs.append(
                    {
                        "fromVersion": previous["version"],
                        "toVersion": current["version"],
                        "addedKeys": sorted(current_keys - previous_keys),
                        "removedKeys": sorted(previous_keys - current_keys),
                        "changedKeys": sorted(
                            key
                            for key in current_keys & previous_keys
                            if current["definition"][key] != previous["definition"][key]
                        ),
                    }
                )
        return {
            "versions": versions,
            "diffs": diffs,
            "nextCursor": str(page_rows[-1]["version"]) if len(rows) > 50 else None,
        }

    async def rollback_workflow(
        self,
        user_id: UUID,
        organization_id: UUID,
        workflow_id: UUID,
        payload: WorkflowRollbackRequest,
    ) -> dict[str, Any]:
        async with self.database.privileged() as conn:
            async with conn.transaction():
                await conn.execute(
                    "select pg_advisory_xact_lock(hashtextextended($1,0))",
                    f"workflow-rollback:{organization_id}:{workflow_id}",
                )
                allowed = await conn.fetchval(
                    """select exists(select 1 from public.organization_members
                        where organization_id=$1 and user_id=$2 and status='active'
                          and role in ('owner','admin'))""",
                    organization_id,
                    user_id,
                )
                if not allowed:
                    raise HTTPException(status_code=403, detail="Administrator role required")
                latest = await conn.fetchval(
                    """select max(version) from public.workflow_versions
                        where workflow_id=$1 and organization_id=$2""",
                    workflow_id,
                    organization_id,
                )
                if latest is None:
                    raise HTTPException(status_code=404, detail="Workflow not found")
                if latest != payload.expected_latest_version:
                    raise HTTPException(status_code=409, detail="Workflow version conflict")
                target = await conn.fetchrow(
                    """select id,definition from public.workflow_versions
                        where workflow_id=$1 and organization_id=$2 and version=$3""",
                    workflow_id,
                    organization_id,
                    payload.target_version,
                )
                if not target:
                    raise HTTPException(status_code=422, detail="Rollback target not found")
                created = await conn.fetchrow(
                    """insert into public.workflow_versions(
                           organization_id,workflow_id,version,definition,published_at,created_by)
                       values($1,$2,$3,$4,now(),$5)
                       returning id,version,published_at,created_at""",
                    organization_id,
                    workflow_id,
                    latest + 1,
                    target["definition"],
                    user_id,
                )
                await conn.execute(
                    """update public.playbooks p set workflow_version_id=$4
                        from public.workflow_versions old
                       where p.organization_id=$1 and old.organization_id=$1
                         and p.workflow_version_id=old.id and old.workflow_id=$2
                         and old.version=$3""",
                    organization_id,
                    workflow_id,
                    latest,
                    created["id"],
                )
                await _emit(
                    conn,
                    organization_id,
                    "workflowVersions.updated",
                    "workflow",
                    workflow_id,
                    {
                        "rollbackFrom": latest,
                        "rollbackTarget": payload.target_version,
                        "newVersion": created["version"],
                    },
                )
        return {
            "version": dict(created),
            "rollbackTarget": payload.target_version,
            "activeRunsPreserved": True,
        }

    async def instantiate(
        self,
        user_id: UUID,
        organization_id: UUID,
        playbook_id: UUID,
        key: str,
        payload: PlaybookInstantiateRequest,
    ) -> PlaybookInstantiateResponse:
        fingerprint = hashlib.sha256(
            json.dumps(payload.model_dump(mode="json"), sort_keys=True).encode()
        ).hexdigest()
        async with self.database.privileged() as conn:
            async with conn.transaction():
                await conn.execute(
                    "select pg_advisory_xact_lock(hashtextextended($1,0))",
                    f"playbook:{organization_id}:{key}",
                )
                membership = await conn.fetchval(
                    """select exists(select 1 from public.organization_members
                        where organization_id=$1 and user_id=$2 and status='active')""",
                    organization_id,
                    user_id,
                )
                if not membership:
                    raise HTTPException(status_code=403, detail="Active tenant membership required")
                if payload.owner_id is not None:
                    owner_valid = await conn.fetchval(
                        """select exists(select 1 from public.organization_members
                            where organization_id=$1 and user_id=$2 and status='active')""",
                        organization_id,
                        payload.owner_id,
                    )
                    if not owner_valid:
                        raise HTTPException(
                            status_code=422, detail="Owner must be active in tenant"
                        )
                existing = await conn.fetchrow(
                    """select r.id,r.task_id,t.metadata from public.runs r
                        join public.tasks t on t.id=r.task_id
                        where r.organization_id=$1 and r.idempotency_key=$2""",
                    organization_id,
                    key,
                )
                if existing:
                    metadata = existing["metadata"]
                    if isinstance(metadata, str):
                        metadata = json.loads(metadata)
                    if metadata.get("playbook_fingerprint") != fingerprint:
                        raise HTTPException(
                            status_code=409, detail="Idempotency-Key payload conflict"
                        )
                    return PlaybookInstantiateResponse(
                        task_id=existing["task_id"],
                        workflow_instance_id=existing["id"],
                        summary={"status": "queued"},
                        replayed=True,
                    )
                playbook = await conn.fetchrow(
                    """select p.name,p.workflow_version_id,p.default_inputs
                         from public.playbooks p join public.organization_members m
                           on m.organization_id=p.organization_id
                        where p.id=$1 and p.organization_id=$2 and p.is_enabled
                          and m.user_id=$3 and m.status='active'""",
                    playbook_id,
                    organization_id,
                    user_id,
                )
                if not playbook:
                    raise HTTPException(status_code=404, detail="Playbook not found")
                default_inputs = playbook["default_inputs"]
                if isinstance(default_inputs, str):
                    default_inputs = json.loads(default_inputs)
                required = cast(dict[str, Any], default_inputs).get("required", [])
                missing = [name for name in required if name not in payload.parameters]
                if missing:
                    raise HTTPException(
                        status_code=422,
                        detail=f"Missing playbook parameters: {', '.join(missing)}",
                    )
                task_id, run_id = uuid4(), uuid4()
                metadata = {
                    "playbook_id": str(playbook_id),
                    "playbook_fingerprint": fingerprint,
                    "context": payload.context,
                    "parameters": payload.parameters,
                }
                await conn.execute(
                    """insert into public.tasks(id,organization_id,title,objective,risk_level,
                           requester_id,assignee_id,workflow_version_id,metadata)
                       values($1,$2,$3,$4,'low',$5,$6,$7,$8::jsonb)""",
                    task_id,
                    organization_id,
                    playbook["name"],
                    f"Instantiate playbook {playbook['name']}",
                    user_id,
                    payload.owner_id,
                    playbook["workflow_version_id"],
                    json.dumps(metadata),
                )
                await conn.execute(
                    """insert into public.runs(
                           id,organization_id,task_id,workflow_version_id,idempotency_key)
                       values($1,$2,$3,$4,$5)""",
                    run_id,
                    organization_id,
                    task_id,
                    playbook["workflow_version_id"],
                    key,
                )
                await _emit(
                    conn,
                    organization_id,
                    "playbooks.instantiated",
                    "playbook",
                    playbook_id,
                    {"task_id": str(task_id), "run_id": str(run_id)},
                )
        return PlaybookInstantiateResponse(
            task_id=task_id, workflow_instance_id=run_id, summary={"status": "queued"}
        )

    async def _simple_page(self, user_id: UUID, organization_id: UUID, table: str) -> Page:
        queries = {
            "agents": """select id,name,slug,description,owner_user_id,risk_level::text,
                         trust_score,is_enabled,updated_at
                    from public.agents where organization_id=$1
                   order by updated_at desc limit 100""",
            "skills": """select id,name,slug,description,input_schema,output_schema,
                         risk_level::text,requires_approval,timeout_seconds,max_retries,
                         is_enabled,updated_at
                    from public.skills where organization_id=$1
                   order by updated_at desc limit 100""",
            "workflows": """select id,name,slug,description,owner_user_id,is_archived,updated_at
                    from public.workflows where organization_id=$1
                   order by updated_at desc limit 100""",
        }
        page_query = queries.get(table)
        if page_query is None:
            raise ValueError("Unsupported table")
        async with self.database.authenticated(user_id, organization_id) as conn:
            rows = await conn.fetch(page_query, organization_id)
        items = [dict(row) for row in rows]
        return Page(items=items, counters={"total": len(items)})


def validate_workflow(payload: WorkflowValidateRequest) -> WorkflowValidateResponse:
    node_ids = [str(node.get("id", "")) for node in payload.nodes]
    errors = []
    if any(not node_id for node_id in node_ids):
        errors.append("Every node requires an id")
    if len(node_ids) != len(set(node_ids)):
        errors.append("Node ids must be unique")
    graph: dict[str, list[str]] = defaultdict(list)
    for edge in payload.edges:
        source, target = str(edge.get("source", "")), str(edge.get("target", ""))
        if source not in node_ids or target not in node_ids:
            errors.append(f"Invalid edge {source}->{target}")
        else:
            graph[source].append(target)
    cycles: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str, trail: list[str]) -> None:
        if node in visiting:
            cycles.append(" -> ".join([*trail, node]))
            return
        if node in visited:
            return
        visiting.add(node)
        for target in graph[node]:
            visit(target, [*trail, node])
        visiting.remove(node)
        visited.add(node)

    for node in node_ids:
        visit(node, [])
    warnings = ["Workflow has no nodes"] if not node_ids else []
    return WorkflowValidateResponse(
        valid=not errors and not cycles, warnings=warnings, cycles=cycles, schema_errors=errors
    )


def _validate_payload(payload: dict[str, Any], schema: Mapping[str, Any]) -> list[str]:
    required = schema.get("required", [])
    findings = [f"Missing required field: {key}" for key in required if key not in payload]
    type_map: dict[str, type[Any] | tuple[type[Any], ...]] = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "object": dict,
        "array": list,
    }
    for key, definition in schema.get("properties", {}).items():
        expected = type_map.get(definition.get("type"))
        if key in payload and expected:
            value = payload[key]
            numeric_boolean = definition.get("type") in {"integer", "number"} and isinstance(
                value, bool
            )
            if numeric_boolean or not isinstance(value, expected):
                findings.append(f"Invalid type for field: {key}")
    return findings


def _sensitive_paths(payload: Mapping[str, Any], prefix: str = "") -> list[str]:
    paths: list[str] = []
    for key, value in payload.items():
        path = f"{prefix}.{key}" if prefix else key
        if any(mark in key.lower() for mark in ("secret", "token", "password")):
            paths.append(path)
        if isinstance(value, Mapping):
            paths.extend(_sensitive_paths(value, path))
    return paths


def _policy_response(policy: dict[str, Any]) -> ApprovalPolicyResponse:
    rules = policy.get("rules", [])
    return ApprovalPolicyResponse(
        policy=policy,
        simulation={"matchedRules": len(rules)},
        coverage={"ruleCount": len(rules), "hasFallback": bool(rules)},
    )


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
