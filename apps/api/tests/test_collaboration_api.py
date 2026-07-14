from datetime import UTC, date, datetime
from uuid import UUID

from bighead_api.artifacts.models import ArtifactDownloadResponse
from bighead_api.artifacts.routes import artifact_service
from bighead_api.collaboration.models import (
    FailureGroup,
    Message,
    MessageCreateRequest,
    MessagePatchRequest,
    Room,
    RoomCreateRequest,
    RoomDetailResponse,
    RoomFile,
    RoomMember,
    RoomPatchRequest,
    Run,
    Task,
    TaskAssigneePatchRequest,
    TaskCreateRequest,
    TaskDependenciesPatchRequest,
    TaskRiskLevel,
    TaskSlaStatus,
    TaskStatus,
    TaskTransitionRequest,
    TimelineItem,
)
from bighead_api.collaboration.routes import repository, router
from bighead_api.identity.dependencies import TenantContext, tenant_context
from bighead_api.identity.models import AuthUser, MemberRole, Membership
from fastapi import FastAPI
from fastapi.testclient import TestClient

USER_ID = UUID("10000000-0000-0000-0000-000000000001")
ORG_ID = UUID("20000000-0000-0000-0000-000000000001")
ROOM_ID = UUID("30000000-0000-0000-0000-000000000001")
TASK_ID = UUID("40000000-0000-0000-0000-000000000001")
NOW = datetime.now(UTC)


def room() -> Room:
    return Room(id=ROOM_ID, name="Ops", is_private=False, created_at=NOW)


def task(*, status: TaskStatus = TaskStatus.NEW, version: int = 1) -> Task:
    return Task(
        id=TASK_ID,
        title="Ship",
        objective="Ship safely",
        status=status,
        priority=3,
        risk_level="low",
        requester_id=USER_ID,
        version=version,
        metadata={},
        created_at=NOW,
        updated_at=NOW,
    )


class FakeRepository:
    def __init__(self) -> None:
        self.keys: set[str] = set()
        self.task_filters: dict[str, object] = {}

    async def list_rooms(
        self,
        user_id: UUID,
        organization_id: UUID,
        visibility: str | None,
        cursor: str | None,
        limit: int,
    ):  # type: ignore[no-untyped-def]
        return [room()], None, {"total": 1, "private": 0}

    async def create_room(
        self, user_id: UUID, organization_id: UUID, payload: RoomCreateRequest
    ) -> Room:
        return room().model_copy(update={"name": payload.name})

    async def patch_room(
        self,
        user_id: UUID,
        organization_id: UUID,
        room_id: UUID,
        payload: RoomPatchRequest,
    ) -> RoomDetailResponse:
        return RoomDetailResponse(
            room=room().model_copy(update={"name": payload.title or "Ops"}),
            members=[RoomMember(user_id=USER_ID, is_moderator=True)],
        )

    async def list_room_members(
        self, user_id: UUID, organization_id: UUID, room_id: UUID
    ):  # type: ignore[no-untyped-def]
        return room(), [RoomMember(user_id=USER_ID, is_moderator=True)]

    async def list_room_files(
        self,
        user_id: UUID,
        organization_id: UUID,
        room_id: UUID,
        cursor: str | None,
        limit: int,
    ):  # type: ignore[no-untyped-def]
        return [
            RoomFile(
                id=UUID("60000000-0000-0000-0000-000000000001"),
                name="report.pdf",
                kind="document",
                mime_type="application/pdf",
                size_bytes=42,
                quarantine_status="clean",
                created_at=NOW,
            )
        ], None

    async def list_messages(
        self, user_id: UUID, organization_id: UUID, room_id: UUID, cursor: str | None, limit: int
    ):  # type: ignore[no-untyped-def]
        item = Message(
            id=UUID("50000000-0000-0000-0000-000000000001"),
            room_id=ROOM_ID,
            author_user_id=USER_ID,
            body="hello",
            metadata={},
            created_at=NOW,
        )
        return room(), [item], None

    async def create_message(
        self, user_id: UUID, organization_id: UUID, room_id: UUID, payload: MessageCreateRequest
    ) -> Message:
        return Message(
            id=UUID("50000000-0000-0000-0000-000000000001"),
            room_id=room_id,
            author_user_id=user_id,
            body=payload.body,
            metadata={"client_id": payload.client_id},
            created_at=NOW,
        )

    async def patch_message(
        self,
        user_id: UUID,
        organization_id: UUID,
        room_id: UUID,
        message_id: UUID,
        payload: MessagePatchRequest,
    ) -> Message:
        return (await self.list_messages(user_id, organization_id, room_id, None, 1))[1][
            0
        ].model_copy(update={"body": payload.body, "edited_at": NOW})

    async def delete_message(
        self, user_id: UUID, organization_id: UUID, room_id: UUID, message_id: UUID
    ) -> Message:
        return (await self.list_messages(user_id, organization_id, room_id, None, 1))[1][
            0
        ].model_copy(update={"body": "[deleted]", "deleted_at": NOW})

    async def list_tasks(
        self,
        user_id: UUID,
        organization_id: UUID,
        status: TaskStatus | None,
        assignee_id: UUID | None,
        risk: TaskRiskLevel | None,
        sla_status: TaskSlaStatus | None,
        room_id: UUID | None,
        cursor: str | None,
        limit: int,
    ):  # type: ignore[no-untyped-def]
        self.task_filters = {
            "status": status,
            "assignee_id": assignee_id,
            "risk": risk,
            "sla_status": sla_status,
            "room_id": room_id,
        }
        return [
            task(status=status or TaskStatus.NEW).model_copy(
                update={
                    "assignee_id": assignee_id,
                    "risk_level": risk.value if risk else "low",
                    "room_id": room_id,
                }
            )
        ], None

    async def get_task(
        self, user_id: UUID, organization_id: UUID, task_id: UUID
    ) -> Task:
        return task()

    async def create_task(
        self, user_id: UUID, organization_id: UUID, payload: TaskCreateRequest, idempotency_key: str
    ):  # type: ignore[no-untyped-def]
        replayed = idempotency_key in self.keys
        self.keys.add(idempotency_key)
        return task(), replayed

    async def replace_task_dependencies(
        self,
        user_id: UUID,
        organization_id: UUID,
        task_id: UUID,
        payload: TaskDependenciesPatchRequest,
    ) -> Task:
        return task(version=payload.expected_version + 1)

    async def reassign_task(
        self, user_id: UUID, organization_id: UUID, task_id: UUID, payload: TaskAssigneePatchRequest
    ) -> Task:
        return task(version=payload.expected_version + 1).model_copy(
            update={"assignee_id": payload.assignee_id}
        )

    async def transition_task(
        self, user_id: UUID, organization_id: UUID, task_id: UUID, payload: TaskTransitionRequest
    ):  # type: ignore[no-untyped-def]
        return task(status=payload.target_state, version=2), TimelineItem(
            from_status=TaskStatus.NEW, to_status=payload.target_state, reason=payload.reason
        )

    async def calendar(
        self, user_id: UUID, organization_id: UUID, start: date, end: date, owner_ids: list[UUID]
    ) -> list[Task]:
        return [task().model_copy(update={"due_at": NOW})]

    async def list_runs(
        self,
        user_id: UUID,
        organization_id: UUID,
        task_id: UUID | None,
        status: str | None,
        cursor: str | None,
        limit: int,
    ):  # type: ignore[no-untyped-def]
        item = Run(
            id=UUID("70000000-0000-0000-0000-000000000001"),
            task_id=TASK_ID,
            status=status or "failed",
            attempt=1,
            heartbeat_at=NOW,
            error_code="provider_timeout",
            created_at=NOW,
        )
        return [item], None

    async def retry_run(self, user_id: UUID, organization_id: UUID, run_id: UUID) -> Run:
        return Run(
            id=UUID("70000000-0000-0000-0000-000000000002"),
            task_id=TASK_ID,
            status="queued",
            attempt=2,
            created_at=NOW,
        )

    async def failures(
        self, user_id: UUID, organization_id: UUID, limit: int
    ) -> list[FailureGroup]:
        return [FailureGroup(code="provider_timeout", count=2, affected_tasks=1, latest_at=NOW)]


class FakeArtifactService:
    async def download(self, organization_id: UUID, artifact_id: UUID) -> ArtifactDownloadResponse:
        return ArtifactDownloadResponse(
            artifact_id=artifact_id,
            download_url="https://storage.example.test/signed-preview",
            expires_at=NOW,
        )


def make_client(
    repo: FakeRepository | None = None, role: MemberRole = MemberRole.MEMBER
) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    selected = repo or FakeRepository()

    async def context() -> TenantContext:
        return TenantContext(
            user=AuthUser(id=USER_ID, email="member@example.com"),
            token="token",
            membership=Membership(
                id="membership",
                organization_id=ORG_ID,
                user_id=USER_ID,
                role=role,
                status="active",
            ),
        )

    app.dependency_overrides[tenant_context] = context
    app.dependency_overrides[repository] = lambda: selected
    app.dependency_overrides[artifact_service] = lambda: FakeArtifactService()
    return TestClient(app)


def test_t10_rooms_and_t11_message_timeline_contracts() -> None:
    client = make_client()
    rooms = client.get("/v1/rooms").json()
    messages = client.get(f"/v1/rooms/{ROOM_ID}/messages").json()
    assert rooms["counters"] == {"total": 1, "private": 0}
    assert messages["roomContext"]["id"] == str(ROOM_ID)
    assert messages["messages"][0]["body"] == "hello"


def test_room_members_read_contract() -> None:
    response = make_client().get(f"/v1/rooms/{ROOM_ID}/members")
    assert response.status_code == 200
    assert response.json() == {
        "room": {
            "id": str(ROOM_ID),
            "name": "Ops",
            "description": None,
            "isPrivate": False,
            "createdAt": NOW.isoformat().replace("+00:00", "Z"),
        },
        "members": [{"userId": str(USER_ID), "isModerator": True}],
    }


def test_task_detail_and_supported_list_filters() -> None:
    repo = FakeRepository()
    client = make_client(repo)
    detail = client.get(f"/v1/tasks/{TASK_ID}")
    listed = client.get(
        f"/v1/tasks?status=triaged&ownerId={USER_ID}&risk=critical"
        f"&slaStatus=overdue&roomId={ROOM_ID}"
    )
    assert detail.status_code == 200 and detail.json()["id"] == str(TASK_ID)
    assert listed.status_code == 200
    assert repo.task_filters == {
        "status": TaskStatus.TRIAGED,
        "assignee_id": USER_ID,
        "risk": TaskRiskLevel.CRITICAL,
        "sla_status": TaskSlaStatus.OVERDUE,
        "room_id": ROOM_ID,
    }
    assert listed.json()["items"][0]["assigneeId"] == str(USER_ID)
    assert listed.json()["items"][0]["roomId"] == str(ROOM_ID)


def test_task_filters_validate_alias_conflicts_and_enums() -> None:
    other_user = UUID("10000000-0000-0000-0000-000000000002")
    client = make_client()
    assert (
        client.get(f"/v1/tasks?ownerId={USER_ID}&assigneeId={other_user}").status_code
        == 422
    )
    assert client.get("/v1/tasks?risk=severe").status_code == 422
    assert client.get("/v1/tasks?slaStatus=breached").status_code == 422


def test_message_client_id_is_forwarded_for_deduplication() -> None:
    response = make_client().post(
        f"/v1/rooms/{ROOM_ID}/messages", json={"body": "hello", "clientId": "offline-1"}
    )
    assert response.status_code == 201
    assert response.json()["metadata"]["client_id"] == "offline-1"


def test_message_edit_delete_and_task_reassignment_contracts() -> None:
    client = make_client()
    message_id = "50000000-0000-0000-0000-000000000001"
    edited = client.patch(f"/v1/rooms/{ROOM_ID}/messages/{message_id}", json={"body": "edited"})
    deleted = client.delete(f"/v1/rooms/{ROOM_ID}/messages/{message_id}")
    reassigned = client.patch(
        f"/v1/tasks/{TASK_ID}/assignee", json={"assigneeId": str(USER_ID), "expectedVersion": 1}
    )
    assert edited.status_code == 200 and edited.json()["editedAt"]
    assert deleted.status_code == 200 and deleted.json()["deletedAt"]
    assert reassigned.status_code == 200 and reassigned.json()["assigneeId"] == str(USER_ID)


def test_t15_requires_idempotency_key_and_replays_same_task() -> None:
    repo = FakeRepository()
    client = make_client(repo)
    assert client.post("/v1/tasks", json={"goal": "Ship safely"}).status_code == 422
    first = client.post(
        "/v1/tasks", headers={"Idempotency-Key": "task-1"}, json={"goal": "Ship safely"}
    )
    replay = client.post(
        "/v1/tasks", headers={"Idempotency-Key": "task-1"}, json={"goal": "Ship safely"}
    )
    assert first.status_code == 201 and first.json()["replayed"] is False
    assert replay.status_code == 201 and replay.json()["replayed"] is True
    assert replay.json()["task"]["id"] == first.json()["task"]["id"]


def test_t16_transition_returns_timeline_and_next_states() -> None:
    response = make_client().post(
        f"/v1/tasks/{TASK_ID}/transition",
        json={"targetState": "triaged", "reason": "accepted", "expectedVersion": 1},
    )
    assert response.status_code == 200
    assert response.json()["timelineItem"]["fromStatus"] == "new"
    assert "in_progress" in response.json()["allowedTransitions"]
    assert "waiting_human" in response.json()["allowedTransitions"]


def test_t15_dependency_edit_has_a_real_versioned_command() -> None:
    response = make_client().patch(
        f"/v1/tasks/{TASK_ID}/dependencies",
        json={"dependencies": [], "expectedVersion": 1},
    )
    assert response.status_code == 200
    assert response.json()["version"] == 2


def test_t19_calendar_validates_range_and_aggregates() -> None:
    client = make_client()
    assert client.get("/v1/tasks/calendar?from=2026-07-13&to=2026-07-12").status_code == 422
    response = client.get("/v1/tasks/calendar?from=2026-07-01&to=2026-07-31")
    assert response.status_code == 200
    assert response.json()["days"][0]["tasks"][0]["id"] == str(TASK_ID)


def test_t12_patch_room_and_t13_files_contracts() -> None:
    client = make_client()
    detail = client.patch(f"/v1/rooms/{ROOM_ID}", json={"title": "War room"})
    files = client.get(f"/v1/rooms/{ROOM_ID}/files")
    assert detail.status_code == 200
    assert detail.json()["room"]["name"] == "War room"
    assert detail.json()["members"][0]["isModerator"] is True
    assert files.json()["files"][0]["quarantineStatus"] == "clean"
    assert files.json()["signedPreview"]["downloadUrl"].startswith("https://storage.example.test")


def test_t17_runs_retry_and_t18_failure_grouping() -> None:
    client = make_client(role=MemberRole.MANAGER)
    runs = client.get(f"/v1/runs?taskId={TASK_ID}")
    run_id = runs.json()["runs"][0]["id"]
    retry = client.post(f"/v1/runs/{run_id}/retry")
    failures = client.get("/v1/failures")
    assert runs.status_code == 200 and runs.json()["heartbeats"][0]["status"] == "failed"
    assert retry.status_code == 200 and retry.json()["run"]["attempt"] == 2
    assert failures.json()["impactSummary"] == {"failures": 2, "affectedTasks": 1}
