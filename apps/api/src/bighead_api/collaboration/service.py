import base64
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Protocol, cast
from uuid import UUID, uuid4

import asyncpg
from fastapi import HTTPException

from bighead_api.collaboration.models import (
    Message,
    MessageCreateRequest,
    Room,
    RoomCreateRequest,
    Task,
    TaskCreateRequest,
    TaskStatus,
    TaskTransitionRequest,
    TimelineItem,
)
from bighead_api.identity.repository import Database


class CollaborationRepository(Protocol):
    async def list_rooms(self, user_id: UUID, organization_id: UUID, visibility: str | None,
                         cursor: str | None, limit: int) -> tuple[list[Room], str | None, dict[str, int]]: ...
    async def create_room(self, user_id: UUID, organization_id: UUID,
                          payload: RoomCreateRequest) -> Room: ...
    async def list_messages(self, user_id: UUID, organization_id: UUID, room_id: UUID,
                            cursor: str | None, limit: int) -> tuple[Room, list[Message], str | None]: ...
    async def create_message(self, user_id: UUID, organization_id: UUID, room_id: UUID,
                             payload: MessageCreateRequest) -> Message: ...
    async def list_tasks(self, user_id: UUID, organization_id: UUID, status: TaskStatus | None,
                         cursor: str | None, limit: int) -> tuple[list[Task], str | None]: ...
    async def create_task(self, user_id: UUID, organization_id: UUID, payload: TaskCreateRequest,
                          idempotency_key: str) -> tuple[Task, bool]: ...
    async def transition_task(self, user_id: UUID, organization_id: UUID, task_id: UUID,
                              payload: TaskTransitionRequest) -> tuple[Task, TimelineItem]: ...
    async def calendar(self, user_id: UUID, organization_id: UUID, start: date, end: date,
                       owner_ids: list[UUID]) -> list[Task]: ...


def _cursor(row: Mapping[str, Any]) -> str:
    value = json.dumps([row["created_at"].isoformat(), str(row["id"])]).encode()
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _decode_cursor(value: str | None) -> tuple[datetime, UUID] | None:
    if not value:
        return None
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        created, identifier = json.loads(raw)
        return datetime.fromisoformat(created), UUID(identifier)
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail="Invalid cursor") from exc


def _row(model: type[Room] | type[Message] | type[Task], row: Mapping[str, Any]) -> Any:
    return model.model_validate(dict(row))


@dataclass
class PostgresCollaborationRepository:
    database: Database

    async def list_rooms(self, user_id: UUID, organization_id: UUID, visibility: str | None,
                         cursor: str | None, limit: int) -> tuple[list[Room], str | None, dict[str, int]]:
        after = _decode_cursor(cursor)
        async with self.database.authenticated(user_id, organization_id) as conn:
            rows = await conn.fetch(
                """select id, name, description, is_private, created_at from public.rooms
                   where organization_id=$1 and ($2::text is null or
                     ($2='private' and is_private) or ($2='public' and not is_private))
                     and ($3::timestamptz is null or (created_at,id) < ($3,$4))
                   order by created_at desc,id desc limit $5""",
                organization_id, visibility, after[0] if after else None,
                after[1] if after else None, limit + 1,
            )
            counts = await conn.fetchrow(
                """select count(*)::int total,
                          count(*) filter(where is_private)::int private
                     from public.rooms where organization_id=$1""", organization_id,
            )
        next_cursor = _cursor(rows[limit - 1]) if len(rows) > limit else None
        return [_row(Room, row) for row in rows[:limit]], next_cursor, dict(counts or {})

    async def create_room(self, user_id: UUID, organization_id: UUID,
                          payload: RoomCreateRequest) -> Room:
        async with self.database.privileged() as conn:
            row = await conn.fetchrow(
                """insert into public.rooms(organization_id,name,description,is_private,created_by)
                   select $1,$2,$3,$4,$5 where exists(select 1 from public.organization_members
                     where organization_id=$1 and user_id=$5 and status='active')
                   returning id,name,description,is_private,created_at""",
                organization_id, payload.name, payload.description, payload.is_private, user_id,
            )
            if not row:
                raise HTTPException(status_code=403, detail="Active tenant membership required")
            await self._emit(conn, organization_id, "rooms.updated", "room", row["id"], dict(row))
        return _row(Room, cast(Mapping[str, Any], row))

    async def list_messages(self, user_id: UUID, organization_id: UUID, room_id: UUID,
                            cursor: str | None, limit: int) -> tuple[Room, list[Message], str | None]:
        after = _decode_cursor(cursor)
        async with self.database.authenticated(user_id, organization_id) as conn:
            room = await conn.fetchrow("select id,name,description,is_private,created_at from public.rooms where id=$1 and organization_id=$2", room_id, organization_id)
            if not room:
                raise HTTPException(status_code=404, detail="Room not found")
            rows = await conn.fetch(
                """select id,room_id,parent_message_id,author_user_id,body,metadata,edited_at,deleted_at,created_at
                     from public.messages where room_id=$1 and organization_id=$2
                       and ($3::timestamptz is null or (created_at,id)<($3,$4))
                     order by created_at desc,id desc limit $5""",
                room_id, organization_id, after[0] if after else None,
                after[1] if after else None, limit + 1,
            )
        next_cursor = _cursor(rows[limit - 1]) if len(rows) > limit else None
        return _row(Room, room), [_row(Message, row) for row in rows[:limit]], next_cursor

    async def create_message(self, user_id: UUID, organization_id: UUID, room_id: UUID,
                             payload: MessageCreateRequest) -> Message:
        metadata = {"client_id": payload.client_id} if payload.client_id else {}
        async with self.database.privileged() as conn:
            if payload.client_id:
                existing = await conn.fetchrow(
                    """select id,room_id,parent_message_id,author_user_id,body,metadata,edited_at,deleted_at,created_at
                         from public.messages where organization_id=$1 and room_id=$2
                           and author_user_id=$3 and metadata->>'client_id'=$4""",
                    organization_id, room_id, user_id, payload.client_id,
                )
                if existing:
                    return _row(Message, existing)
            row = await conn.fetchrow(
                """insert into public.messages(organization_id,room_id,parent_message_id,author_user_id,body,metadata)
                   select $1,$2,$3,$4,$5,$6::jsonb where exists(
                     select 1 from public.rooms r join public.organization_members m on m.organization_id=r.organization_id
                      where r.id=$2 and r.organization_id=$1 and m.user_id=$4 and m.status='active'
                        and (not r.is_private or exists(select 1 from public.room_members rm where rm.room_id=r.id and rm.user_id=$4)))
                   returning id,room_id,parent_message_id,author_user_id,body,metadata,edited_at,deleted_at,created_at""",
                organization_id, room_id, payload.parent_message_id, user_id, payload.body, json.dumps(metadata),
            )
            if not row:
                raise HTTPException(status_code=403, detail="Room access required")
            await self._emit(conn, organization_id, "room.message.created", "message", row["id"], dict(row))
        return _row(Message, cast(Mapping[str, Any], row))

    async def list_tasks(self, user_id: UUID, organization_id: UUID, status: TaskStatus | None,
                         cursor: str | None, limit: int) -> tuple[list[Task], str | None]:
        after = _decode_cursor(cursor)
        async with self.database.authenticated(user_id, organization_id) as conn:
            rows = await conn.fetch(
                """select id,room_id,source_message_id,title,objective,status::text,priority,risk_level::text,
                          requester_id,assignee_id,workflow_version_id,due_at,sla_at,version,metadata,created_at,updated_at
                     from public.tasks where organization_id=$1 and ($2::text is null or status::text=$2)
                       and ($3::timestamptz is null or (created_at,id)<($3,$4))
                     order by created_at desc,id desc limit $5""",
                organization_id, status.value if status else None, after[0] if after else None,
                after[1] if after else None, limit + 1,
            )
        next_cursor = _cursor(rows[limit - 1]) if len(rows) > limit else None
        return [_row(Task, row) for row in rows[:limit]], next_cursor

    async def create_task(self, user_id: UUID, organization_id: UUID, payload: TaskCreateRequest,
                          idempotency_key: str) -> tuple[Task, bool]:
        async with self.database.privileged() as conn:
            existing = await self._task_for_key(conn, organization_id, idempotency_key)
            if existing:
                return _row(Task, existing), True
            task_id = uuid4()
            title = payload.title or payload.goal[:240]
            metadata = {"idempotency_key": idempotency_key}
            try:
                row = await conn.fetchrow(
                    """insert into public.tasks(id,organization_id,room_id,source_message_id,title,objective,
                               risk_level,requester_id,assignee_id,workflow_version_id,sla_at,metadata)
                       select $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12::jsonb where exists(
                         select 1 from public.organization_members where organization_id=$2 and user_id=$8 and status='active')
                       returning id,room_id,source_message_id,title,objective,status::text,priority,risk_level::text,
                         requester_id,assignee_id,workflow_version_id,due_at,sla_at,version,metadata,created_at,updated_at""",
                    task_id, organization_id, payload.room_id, payload.source_message_id, title,
                    payload.goal, payload.risk, user_id, payload.assignee_id, payload.workflow_id,
                    payload.sla_at, json.dumps(metadata),
                )
                if not row:
                    raise HTTPException(status_code=403, detail="Active tenant membership required")
                for dependency in dict.fromkeys(payload.dependencies):
                    result = await conn.execute(
                        """insert into public.task_dependencies(organization_id,task_id,depends_on_task_id)
                           select $1,$2,$3 where exists(select 1 from public.tasks where id=$3 and organization_id=$1)""",
                        organization_id, task_id, dependency,
                    )
                    if result == "INSERT 0 0":
                        raise HTTPException(status_code=422, detail=f"Dependency {dependency} not found")
                await self._emit(conn, organization_id, "tasks.created", "task", task_id, dict(row))
            except asyncpg.UniqueViolationError:
                row = await self._task_for_key(conn, organization_id, idempotency_key)
                if not row:
                    raise
                return _row(Task, row), True
            except asyncpg.CheckViolationError as exc:
                raise HTTPException(status_code=409, detail="Task dependency cycle") from exc
        return _row(Task, cast(Mapping[str, Any], row)), False

    async def transition_task(self, user_id: UUID, organization_id: UUID, task_id: UUID,
                              payload: TaskTransitionRequest) -> tuple[Task, TimelineItem]:
        async with self.database.authenticated(user_id, organization_id) as conn:
            before = await conn.fetchrow("select status::text from public.tasks where id=$1 and organization_id=$2", task_id, organization_id)
            if not before:
                raise HTTPException(status_code=404, detail="Task not found")
            try:
                row = await conn.fetchrow(
                    """select id,room_id,source_message_id,title,objective,status::text,priority,risk_level::text,
                         requester_id,assignee_id,workflow_version_id,due_at,sla_at,version,metadata,created_at,updated_at
                       from public.transition_task($1,$2,$3,$4)""",
                    task_id, payload.target_state.value, payload.reason, payload.expected_version,
                )
            except asyncpg.SerializationError as exc:
                raise HTTPException(status_code=409, detail="Task version conflict") from exc
            except asyncpg.RaiseError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
        return _row(Task, cast(Mapping[str, Any], row)), TimelineItem(
            from_status=before["status"], to_status=payload.target_state, reason=payload.reason)

    async def calendar(self, user_id: UUID, organization_id: UUID, start: date, end: date,
                       owner_ids: list[UUID]) -> list[Task]:
        async with self.database.authenticated(user_id, organization_id) as conn:
            rows = await conn.fetch(
                """select id,room_id,source_message_id,title,objective,status::text,priority,risk_level::text,
                         requester_id,assignee_id,workflow_version_id,due_at,sla_at,version,metadata,created_at,updated_at
                     from public.tasks where organization_id=$1 and coalesce(due_at,sla_at)::date between $2 and $3
                       and (cardinality($4::uuid[])=0 or assignee_id=any($4)) order by coalesce(due_at,sla_at),id""",
                organization_id, start, end, owner_ids,
            )
        return [_row(Task, row) for row in rows]

    async def _task_for_key(self, conn: asyncpg.Connection[Any], organization_id: UUID,
                            key: str) -> Mapping[str, Any] | None:
        return await conn.fetchrow(
            """select id,room_id,source_message_id,title,objective,status::text,priority,risk_level::text,
                     requester_id,assignee_id,workflow_version_id,due_at,sla_at,version,metadata,created_at,updated_at
                 from public.tasks where organization_id=$1 and metadata->>'idempotency_key'=$2""",
            organization_id, key,
        )

    async def _emit(self, conn: asyncpg.Connection[Any], organization_id: UUID, event_type: str,
                    aggregate_type: str, aggregate_id: UUID, payload: dict[str, Any]) -> None:
        await conn.execute(
            """insert into public.event_outbox(organization_id,event_type,aggregate_type,aggregate_id,payload)
               values($1,$2,$3,$4,$5::jsonb)""",
            organization_id, event_type, aggregate_type, aggregate_id,
            json.dumps(payload, default=str),
        )


ALLOWED: dict[TaskStatus, list[TaskStatus]] = {
    TaskStatus.NEW: [TaskStatus.TRIAGED, TaskStatus.CANCELED],
    TaskStatus.TRIAGED: [TaskStatus.IN_PROGRESS, TaskStatus.CANCELED],
    TaskStatus.IN_PROGRESS: [TaskStatus.WAITING_TOOL, TaskStatus.WAITING_HUMAN, TaskStatus.READY_FOR_REVIEW, TaskStatus.FAILED, TaskStatus.CANCELED],
    TaskStatus.WAITING_TOOL: [TaskStatus.IN_PROGRESS, TaskStatus.FAILED, TaskStatus.CANCELED],
    TaskStatus.WAITING_HUMAN: [TaskStatus.IN_PROGRESS, TaskStatus.READY_FOR_REVIEW, TaskStatus.CANCELED],
    TaskStatus.READY_FOR_REVIEW: [TaskStatus.APPROVED, TaskStatus.IN_PROGRESS, TaskStatus.CANCELED],
    TaskStatus.APPROVED: [TaskStatus.DONE, TaskStatus.IN_PROGRESS],
    TaskStatus.FAILED: [TaskStatus.IN_PROGRESS, TaskStatus.CANCELED],
}
