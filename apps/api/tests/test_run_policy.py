import json
from datetime import UTC, datetime
from uuid import UUID

import pytest
from bighead_api.governance.run_policy import RunPolicyError, resolve_run_policy

ORG = UUID("72000000-0000-0000-0000-000000000001")
WORKFLOW = UUID("74000000-0000-0000-0000-000000000001")
SKILL_A = UUID("75000000-0000-0000-0000-000000000001")
SKILL_B = UUID("75000000-0000-0000-0000-000000000002")


class Connection:
    def __init__(
        self, definition: dict[str, object] | str, skills: list[dict[str, object]]
    ) -> None:
        self.definition = definition
        self.skills = skills

    async def fetchrow(self, query: str, *args: object) -> dict[str, object]:
        return {"definition": self.definition}

    async def fetch(self, query: str, *args: object) -> list[dict[str, object]]:
        return self.skills


@pytest.mark.asyncio
async def test_policy_snapshots_strictest_skill_timeout_and_retry_limit() -> None:
    updated_at = datetime(2026, 7, 13, tzinfo=UTC)
    conn = Connection(
        {"nodes": [{"skillId": str(SKILL_A)}, {"skill_id": str(SKILL_B)}]},
        [
            {
                "id": SKILL_A,
                "slug": "search",
                "timeout_seconds": 45,
                "max_retries": 4,
                "is_enabled": True,
                "updated_at": updated_at,
            },
            {
                "id": SKILL_B,
                "slug": "publish",
                "timeout_seconds": 20,
                "max_retries": 2,
                "is_enabled": True,
                "updated_at": updated_at,
            },
        ],
    )

    policy = await resolve_run_policy(conn, ORG, WORKFLOW)

    assert policy.timeout_seconds == 20
    assert policy.max_attempts == 3
    assert policy.retry_backoff_seconds == 30
    assert policy.snapshot["source"] == "workflow-skills"
    assert [skill["id"] for skill in policy.snapshot["skills"]] == [str(SKILL_A), str(SKILL_B)]


@pytest.mark.asyncio
async def test_policy_fails_closed_for_missing_or_disabled_skill() -> None:
    missing = Connection({"nodes": [{"skillId": str(SKILL_A)}]}, [])
    with pytest.raises(RunPolicyError, match="missing tenant skill"):
        await resolve_run_policy(missing, ORG, WORKFLOW)

    disabled = Connection(
        {"nodes": [{"skillId": str(SKILL_A)}]},
        [
            {
                "id": SKILL_A,
                "slug": "unsafe",
                "timeout_seconds": 10,
                "max_retries": 1,
                "is_enabled": False,
                "updated_at": datetime.now(UTC),
            }
        ],
    )
    with pytest.raises(RunPolicyError, match="disabled skill"):
        await resolve_run_policy(disabled, ORG, WORKFLOW)


@pytest.mark.asyncio
async def test_policy_uses_explicit_defaults_when_workflow_has_no_skill_nodes() -> None:
    connection = Connection({"nodes": [{"id": "start"}]}, [])
    connection.definition = json.dumps(connection.definition)
    policy = await resolve_run_policy(connection, ORG, WORKFLOW)

    assert policy.snapshot == {
        "source": "workflow-default",
        "workflowVersionId": str(WORKFLOW),
        "timeoutSeconds": 60,
        "maxAttempts": 3,
        "retryBackoffSeconds": 30,
        "skills": [],
    }
