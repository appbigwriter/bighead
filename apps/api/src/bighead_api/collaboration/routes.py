from collections import defaultdict
from datetime import UTC, date, datetime
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status

from bighead_api.collaboration.models import (
    CalendarDay, Message, MessageCreateRequest, MessageListResponse, Room, RoomCreateRequest,
    RoomListResponse, TaskCalendarResponse, TaskCreateRequest, TaskCreateResponse,
    TaskListResponse, TaskStatus, TaskTransitionRequest, TaskTransitionResponse,
)
from bighead_api.collaboration.service import ALLOWED, CollaborationRepository
from bighead_api.identity.dependencies import TenantContext, tenant_context

router = APIRouter(prefix="/v1", tags=["collaboration"])


def repository(request: Request) -> CollaborationRepository:
    return cast(CollaborationRepository, request.app.state.collaboration_repository)


@router.get("/rooms", response_model=RoomListResponse)
async def rooms(context: Annotated[TenantContext, Depends(tenant_context)], repo: Annotated[CollaborationRepository, Depends(repository)],
                visibility: str | None = None, cursor: str | None = None, limit: int = Query(50, ge=1, le=100)) -> RoomListResponse:
    items, next_cursor, counters = await repo.list_rooms(_user(context), context.organization_id, visibility, cursor, limit)
    return RoomListResponse(rooms=items, counters=counters, next_cursor=next_cursor)


@router.post("/rooms", response_model=Room, status_code=status.HTTP_201_CREATED)
async def create_room(payload: RoomCreateRequest, context: Annotated[TenantContext, Depends(tenant_context)],
                      repo: Annotated[CollaborationRepository, Depends(repository)]) -> Room:
    return await repo.create_room(_user(context), context.organization_id, payload)


@router.get("/rooms/{room_id}/messages", response_model=MessageListResponse)
async def messages(room_id: UUID, context: Annotated[TenantContext, Depends(tenant_context)], repo: Annotated[CollaborationRepository, Depends(repository)],
                   cursor: str | None = None, limit: int = Query(50, ge=1, le=100)) -> MessageListResponse:
    room, items, next_cursor = await repo.list_messages(_user(context), context.organization_id, room_id, cursor, limit)
    return MessageListResponse(messages=items, next_cursor=next_cursor, room_context=room)


@router.post("/rooms/{room_id}/messages", response_model=Message, status_code=status.HTTP_201_CREATED)
async def create_message(room_id: UUID, payload: MessageCreateRequest, context: Annotated[TenantContext, Depends(tenant_context)],
                         repo: Annotated[CollaborationRepository, Depends(repository)]) -> Message:
    return await repo.create_message(_user(context), context.organization_id, room_id, payload)


@router.get("/tasks/calendar", response_model=TaskCalendarResponse, tags=["tasks"])
async def calendar(context: Annotated[TenantContext, Depends(tenant_context)], repo: Annotated[CollaborationRepository, Depends(repository)],
                   start: date = Query(alias="from"), end: date = Query(alias="to"), owner_ids: list[UUID] = Query(default=[], alias="ownerIds")) -> TaskCalendarResponse:
    if end < start or (end - start).days > 366:
        raise HTTPException(status_code=422, detail="Invalid calendar range")
    items = await repo.calendar(_user(context), context.organization_id, start, end, owner_ids)
    grouped: dict[str, list] = defaultdict(list)
    now = datetime.now(UTC)
    for item in items:
        instant = item.due_at or item.sla_at
        if instant:
            grouped[instant.date().isoformat()].append(item)
    return TaskCalendarResponse(days=[CalendarDay(date=key, tasks=value) for key, value in sorted(grouped.items())],
        overdue_count=sum(1 for item in items if (item.due_at or item.sla_at) and cast(datetime, item.due_at or item.sla_at) < now and item.status not in {TaskStatus.DONE, TaskStatus.CANCELED}),
        risk_count=sum(1 for item in items if item.risk_level in {"high", "critical"}))


@router.get("/tasks", response_model=TaskListResponse, tags=["tasks"])
async def tasks(context: Annotated[TenantContext, Depends(tenant_context)], repo: Annotated[CollaborationRepository, Depends(repository)],
                task_status: TaskStatus | None = Query(default=None, alias="status"), cursor: str | None = None,
                limit: int = Query(50, ge=1, le=100)) -> TaskListResponse:
    items, next_cursor = await repo.list_tasks(_user(context), context.organization_id, task_status, cursor, limit)
    return TaskListResponse(items=items, next_cursor=next_cursor)


@router.post("/tasks", response_model=TaskCreateResponse, status_code=status.HTTP_201_CREATED, tags=["tasks"])
async def create_task(payload: TaskCreateRequest, context: Annotated[TenantContext, Depends(tenant_context)], repo: Annotated[CollaborationRepository, Depends(repository)],
                      idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None) -> TaskCreateResponse:
    if not idempotency_key or len(idempotency_key) > 200:
        raise HTTPException(status_code=400, detail="Idempotency-Key header required")
    task, replayed = await repo.create_task(_user(context), context.organization_id, payload, idempotency_key)
    return TaskCreateResponse(task=task, route_preview={"workflowId": str(payload.workflow_id) if payload.workflow_id else None, "risk": payload.risk}, replayed=replayed)


@router.post("/tasks/{task_id}/transition", response_model=TaskTransitionResponse, tags=["tasks"])
async def transition(task_id: UUID, payload: TaskTransitionRequest, context: Annotated[TenantContext, Depends(tenant_context)],
                     repo: Annotated[CollaborationRepository, Depends(repository)]) -> TaskTransitionResponse:
    task, timeline = await repo.transition_task(_user(context), context.organization_id, task_id, payload)
    return TaskTransitionResponse(task=task, timeline_item=timeline, allowed_transitions=ALLOWED.get(task.status, []))


def _user(context: TenantContext) -> UUID:
    if context.user.id is None:
        raise HTTPException(status_code=401, detail="Authenticated user required")
    return context.user.id
