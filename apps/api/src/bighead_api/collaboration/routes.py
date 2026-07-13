from collections import defaultdict
from datetime import UTC, date, datetime
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, Request, status

from bighead_api.artifacts.routes import artifact_service
from bighead_api.artifacts.service import ArtifactService
from bighead_api.collaboration.models import (
    CalendarDay,
    FailureGroupResponse,
    Message,
    MessageCreateRequest,
    MessageListResponse,
    Room,
    RoomCreateRequest,
    RoomDetailResponse,
    RoomFileListResponse,
    RoomListResponse,
    RoomPatchRequest,
    RunListResponse,
    RunRetryResponse,
    Task,
    TaskCalendarResponse,
    TaskCreateRequest,
    TaskCreateResponse,
    TaskListResponse,
    TaskStatus,
    TaskTransitionRequest,
    TaskTransitionResponse,
)
from bighead_api.collaboration.service import ALLOWED, CollaborationRepository
from bighead_api.identity.dependencies import TenantContext, tenant_context
from bighead_api.identity.models import MemberRole

router = APIRouter(prefix="/v1", tags=["collaboration"])


def repository(request: Request) -> CollaborationRepository:
    return cast(CollaborationRepository, request.app.state.collaboration_repository)


@router.get("/rooms", response_model=RoomListResponse)
async def rooms(
    context: Annotated[TenantContext, Depends(tenant_context)],
    repo: Annotated[CollaborationRepository, Depends(repository)],
    visibility: str | None = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> RoomListResponse:
    items, next_cursor, counters = await repo.list_rooms(
        _user(context), context.organization_id, visibility, cursor, limit
    )
    return RoomListResponse(rooms=items, counters=counters, next_cursor=next_cursor)


@router.post("/rooms", response_model=Room, status_code=status.HTTP_201_CREATED)
async def create_room(
    payload: RoomCreateRequest,
    context: Annotated[TenantContext, Depends(tenant_context)],
    repo: Annotated[CollaborationRepository, Depends(repository)],
) -> Room:
    return await repo.create_room(_user(context), context.organization_id, payload)


@router.patch("/rooms/{roomId}", response_model=RoomDetailResponse)
async def patch_room(
    room_id: Annotated[UUID, Path(alias="roomId")],
    payload: RoomPatchRequest,
    context: Annotated[TenantContext, Depends(tenant_context)],
    repo: Annotated[CollaborationRepository, Depends(repository)],
) -> RoomDetailResponse:
    return await repo.patch_room(_user(context), context.organization_id, room_id, payload)


@router.get("/rooms/{roomId}/messages", response_model=MessageListResponse)
async def messages(
    room_id: Annotated[UUID, Path(alias="roomId")],
    context: Annotated[TenantContext, Depends(tenant_context)],
    repo: Annotated[CollaborationRepository, Depends(repository)],
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> MessageListResponse:
    room, items, next_cursor = await repo.list_messages(
        _user(context), context.organization_id, room_id, cursor, limit
    )
    return MessageListResponse(messages=items, next_cursor=next_cursor, room_context=room)


@router.post(
    "/rooms/{roomId}/messages", response_model=Message, status_code=status.HTTP_201_CREATED
)
async def create_message(
    room_id: Annotated[UUID, Path(alias="roomId")],
    payload: MessageCreateRequest,
    context: Annotated[TenantContext, Depends(tenant_context)],
    repo: Annotated[CollaborationRepository, Depends(repository)],
) -> Message:
    return await repo.create_message(_user(context), context.organization_id, room_id, payload)


@router.get("/rooms/{roomId}/files", response_model=RoomFileListResponse)
async def room_files(
    room_id: Annotated[UUID, Path(alias="roomId")],
    context: Annotated[TenantContext, Depends(tenant_context)],
    repo: Annotated[CollaborationRepository, Depends(repository)],
    artifacts: Annotated[ArtifactService, Depends(artifact_service)],
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> RoomFileListResponse:
    items, next_cursor = await repo.list_room_files(
        _user(context), context.organization_id, room_id, cursor, limit
    )
    preview = None
    clean = next((item for item in items if item.quarantine_status == "clean"), None)
    if clean:
        preview = await artifacts.download(context.organization_id, clean.id)
    return RoomFileListResponse(files=items, signed_preview=preview, next_cursor=next_cursor)


@router.get("/tasks/calendar", response_model=TaskCalendarResponse, tags=["tasks"])
async def calendar(
    context: Annotated[TenantContext, Depends(tenant_context)],
    repo: Annotated[CollaborationRepository, Depends(repository)],
    start: Annotated[date, Query(alias="from")],
    end: Annotated[date, Query(alias="to")],
    owner_ids: Annotated[list[UUID] | None, Query(alias="ownerIds")] = None,
) -> TaskCalendarResponse:
    if end < start or (end - start).days > 366:
        raise HTTPException(status_code=422, detail="Invalid calendar range")
    items = await repo.calendar(
        _user(context), context.organization_id, start, end, owner_ids or []
    )
    grouped: dict[str, list[Task]] = defaultdict(list)
    now = datetime.now(UTC)
    for item in items:
        instant = item.due_at or item.sla_at
        if instant:
            grouped[instant.date().isoformat()].append(item)
    return TaskCalendarResponse(
        days=[CalendarDay(date=key, tasks=value) for key, value in sorted(grouped.items())],
        overdue_count=sum(
            1
            for item in items
            if (item.due_at or item.sla_at)
            and cast(datetime, item.due_at or item.sla_at) < now
            and item.status not in {TaskStatus.DONE, TaskStatus.CANCELED}
        ),
        risk_count=sum(1 for item in items if item.risk_level in {"high", "critical"}),
    )


@router.get("/tasks", response_model=TaskListResponse, tags=["tasks"])
async def tasks(
    context: Annotated[TenantContext, Depends(tenant_context)],
    repo: Annotated[CollaborationRepository, Depends(repository)],
    task_status: Annotated[TaskStatus | None, Query(alias="status")] = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> TaskListResponse:
    items, next_cursor = await repo.list_tasks(
        _user(context), context.organization_id, task_status, cursor, limit
    )
    return TaskListResponse(items=items, next_cursor=next_cursor)


@router.post(
    "/tasks", response_model=TaskCreateResponse, status_code=status.HTTP_201_CREATED, tags=["tasks"]
)
async def create_task(
    payload: TaskCreateRequest,
    context: Annotated[TenantContext, Depends(tenant_context)],
    repo: Annotated[CollaborationRepository, Depends(repository)],
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=1, max_length=200, pattern=r".*\S.*")
    ],
) -> TaskCreateResponse:
    task, replayed = await repo.create_task(
        _user(context), context.organization_id, payload, idempotency_key
    )
    return TaskCreateResponse(
        task=task,
        route_preview={
            "workflowId": str(payload.workflow_id) if payload.workflow_id else None,
            "risk": payload.risk,
        },
        replayed=replayed,
    )


@router.post("/tasks/{taskId}/transition", response_model=TaskTransitionResponse, tags=["tasks"])
async def transition(
    task_id: Annotated[UUID, Path(alias="taskId")],
    payload: TaskTransitionRequest,
    context: Annotated[TenantContext, Depends(tenant_context)],
    repo: Annotated[CollaborationRepository, Depends(repository)],
) -> TaskTransitionResponse:
    task, timeline = await repo.transition_task(
        _user(context), context.organization_id, task_id, payload
    )
    return TaskTransitionResponse(
        task=task, timeline_item=timeline, allowed_transitions=ALLOWED.get(task.status, [])
    )


@router.get("/runs", response_model=RunListResponse, tags=["runs"])
async def runs(
    context: Annotated[TenantContext, Depends(tenant_context)],
    repo: Annotated[CollaborationRepository, Depends(repository)],
    task_id: Annotated[UUID | None, Query(alias="taskId")] = None,
    run_status: Annotated[str | None, Query(alias="status")] = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> RunListResponse:
    items, next_cursor = await repo.list_runs(
        _user(context), context.organization_id, task_id, run_status, cursor, limit
    )
    return RunListResponse(
        runs=items,
        heartbeats=[
            {
                "runId": str(item.id),
                "status": "lease_expired"
                if item.locked_until and item.locked_until < datetime.now(UTC)
                else item.status,
                "heartbeatAt": item.heartbeat_at.isoformat() if item.heartbeat_at else None,
            }
            for item in items
        ],
        next_cursor=next_cursor,
    )


@router.post("/runs/{runId}/retry", response_model=RunRetryResponse, tags=["runs"])
async def retry_run(
    run_id: Annotated[UUID, Path(alias="runId")],
    context: Annotated[TenantContext, Depends(tenant_context)],
    repo: Annotated[CollaborationRepository, Depends(repository)],
) -> RunRetryResponse:
    retried = await repo.retry_run(_user(context), context.organization_id, run_id)
    return RunRetryResponse(run=retried, previous_run_id=run_id)


@router.get("/failures", response_model=FailureGroupResponse, tags=["runs"])
async def failures(
    context: Annotated[TenantContext, Depends(tenant_context)],
    repo: Annotated[CollaborationRepository, Depends(repository)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> FailureGroupResponse:
    if context.membership.role not in {
        MemberRole.OWNER,
        MemberRole.ADMIN,
        MemberRole.MANAGER,
    }:
        raise HTTPException(status_code=403, detail="Manager role required")
    groups = await repo.failures(_user(context), context.organization_id, limit)
    return FailureGroupResponse(
        groups=groups,
        impact_summary={
            "failures": sum(group.count for group in groups),
            "affectedTasks": sum(group.affected_tasks for group in groups),
        },
    )


def _user(context: TenantContext) -> UUID:
    if context.user.id is None:
        raise HTTPException(status_code=401, detail="Authenticated user required")
    return context.user.id
