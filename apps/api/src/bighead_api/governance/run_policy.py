from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID


class PolicyConnection(Protocol):
    async def fetchrow(self, query: str, *args: object) -> Any: ...

    async def fetch(self, query: str, *args: object) -> list[Any]: ...


@dataclass(frozen=True)
class ResolvedRunPolicy:
    timeout_seconds: int
    max_attempts: int
    retry_backoff_seconds: int
    snapshot: dict[str, Any]


class RunPolicyError(ValueError):
    pass


async def resolve_run_policy(
    conn: PolicyConnection,
    organization_id: UUID,
    workflow_version_id: UUID,
    *,
    default_timeout_seconds: int = 60,
    default_max_attempts: int = 3,
    default_retry_backoff_seconds: int = 30,
) -> ResolvedRunPolicy:
    """Snapshot the strictest policy of skills referenced by a workflow version."""
    workflow = await conn.fetchrow(
        """select definition from public.workflow_versions
             where id=$1 and organization_id=$2""",
        workflow_version_id,
        organization_id,
    )
    if not workflow:
        raise RunPolicyError("Workflow version not found")
    definition = workflow["definition"]
    if isinstance(definition, str):
        try:
            definition = json.loads(definition)
        except json.JSONDecodeError as exc:
            raise RunPolicyError("Workflow definition must be valid JSON") from exc
    if not isinstance(definition, dict):
        raise RunPolicyError("Workflow definition must be an object")
    nodes = definition.get("nodes", [])
    if not isinstance(nodes, list):
        raise RunPolicyError("Workflow nodes must be an array")

    skill_ids: list[UUID] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        raw_id = node.get("skillId", node.get("skill_id"))
        if raw_id is None:
            continue
        try:
            skill_id = UUID(str(raw_id))
        except ValueError as exc:
            raise RunPolicyError("Workflow contains an invalid skill reference") from exc
        if skill_id not in skill_ids:
            skill_ids.append(skill_id)

    if not skill_ids:
        return ResolvedRunPolicy(
            default_timeout_seconds,
            default_max_attempts,
            default_retry_backoff_seconds,
            {
                "source": "workflow-default",
                "workflowVersionId": str(workflow_version_id),
                "timeoutSeconds": default_timeout_seconds,
                "maxAttempts": default_max_attempts,
                "retryBackoffSeconds": default_retry_backoff_seconds,
                "skills": [],
            },
        )

    rows = await conn.fetch(
        """select id,slug,timeout_seconds,max_retries,is_enabled,updated_at
             from public.skills
            where organization_id=$1 and id=any($2::uuid[])
            order by id""",
        organization_id,
        skill_ids,
    )
    by_id = {row["id"]: row for row in rows}
    missing = [skill_id for skill_id in skill_ids if skill_id not in by_id]
    if missing:
        raise RunPolicyError("Workflow references a missing tenant skill")
    if any(not by_id[skill_id]["is_enabled"] for skill_id in skill_ids):
        raise RunPolicyError("Workflow references a disabled skill")

    skills = []
    for skill_id in skill_ids:
        row = by_id[skill_id]
        updated_at = row["updated_at"]
        skills.append(
            {
                "id": str(skill_id),
                "slug": row["slug"],
                "timeoutSeconds": int(row["timeout_seconds"]),
                "maxRetries": int(row["max_retries"]),
                "updatedAt": (
                    updated_at.isoformat() if isinstance(updated_at, datetime) else str(updated_at)
                ),
            }
        )
    timeout_seconds = min(skill["timeoutSeconds"] for skill in skills)
    max_attempts = min(skill["maxRetries"] for skill in skills) + 1
    snapshot = {
        "source": "workflow-skills",
        "workflowVersionId": str(workflow_version_id),
        "timeoutSeconds": timeout_seconds,
        "maxAttempts": max_attempts,
        "retryBackoffSeconds": default_retry_backoff_seconds,
        "skills": skills,
    }
    return ResolvedRunPolicy(
        timeout_seconds,
        max_attempts,
        default_retry_backoff_seconds,
        snapshot,
    )
