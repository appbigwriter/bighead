# ruff: noqa: E501
import base64
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Protocol, cast
from uuid import UUID, uuid4

import asyncpg
from fastapi import HTTPException
from pydantic import BaseModel

from bighead_api.collaboration.models import (
    FailureGroup,
    Message,
    MessageCreateRequest,
    Room,
    RoomCreateRequest,
    RoomDetailResponse,
    RoomFile,
    RoomMember,
    RoomPatchRequest,
    Run,
    Task,
    TaskCreateRequest,
    TaskStatus,
    TaskTransitionRequest,
    TimelineItem,
)
from bighead_api.identity.repository import Database


class CollaborationRepository(Protocol):
    async def list_rooms(
        self,
        user_id: UUID,
        organization_id: UUID,
        visibility: str | None,
        cursor: str | None,
        limit: int,
    ) -> tuple[list[Room], str | None, dict[str, int]]: ...
    async def create_room(
        self, user_id: UUID, organization_id: UUID, payload: RoomCreateRequest
    ) -> Room: ...
    async def patch_room(
        self, user_id: UUID, organization_id: UUID, room_id: UUID, payload: RoomPatchRequest
    ) -> RoomDetailResponse: ...
    async def list_room_files(
        self, user_id: UUID, organization_id: UUID, room_id: UUID, cursor: str | None, limit: int
    ) -> tuple[list[RoomFile], str | None]: ...
    async def list_messages(
        self, user_id: UUID, organization_id: UUID, room_id: UUID, cursor: str | None, limit: int
    ) -> tuple[Room, list[Message], str | None]: ...
    async def create_message(
        self, user_id: UUID, organization_id: UUID, room_id: UUID, payload: MessageCreateRequest
    ) -> Message: ...
    async def list_tasks(
        self,
        user_id: UUID,
        organization_id: UUID,
        status: TaskStatus | None,
        cursor: str | None,
        limit: int,
    ) -> tuple[list[Task], str | None]: ...
    async def create_task(
        self, user_id: UUID, organization_id: UUID, payload: TaskCreateRequest, idempotency_key: str
    ) -> tuple[Task, bool]: ...
    async def transition_task(
        self, user_id: UUID, organization_id: UUID, task_id: UUID, payload: TaskTransitionRequest
    ) -> tuple[Task, TimelineItem]: ...
    async def calendar(
        self, user_id: UUID, organization_id: UUID, start: date, end: date, owner_ids: list[UUID]
    ) -> list[Task]: ...
    async def list_runs(
        self,
        user_id: UUID,
        organization_id: UUID,
        task_id: UUID | None,
        status: str | None,
        cursor: str | None,
        limit: int,
    ) -> tuple[list[Run], str | None]: ...
    async def retry_run(self, user_id: UUID, organization_id: UUID, run_id: UUID) -> Run: ...
    async def failures(
        self, user_id: UUID, organization_id: UUID, limit: int
    ) -> list[FailureGroup]: ...


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


def _row[ModelT: BaseModel](model: type[ModelT], row: Mapping[str, Any]) -> ModelT:
    values = dict(row)
    for key, value in values.items():
        if isinstance(value, str) and value[:1] in {"{", "["}:
            try:
                values[key] = json.loads(value)
            except json.JSONDecodeError:
                pass
    return model.model_validate(values)


@dataclass
class PostgresCollaborationRepository:
    database: Database

    async def list_rooms(
        self,
        user_id: UUID,
        organization_id: UUID,
        visibility: str | None,
        cursor: str | None,
        limit: int,
    ) -> tuple[list[Room], str | None, dict[str, int]]:
        after = _decode_cursor(cursor)
        async with self.database.authenticated(user_id, organization_id) as conn:
            rows = await conn.fetch(
                """select id, name, description, is_private, created_at from public.rooms
                   where organization_id=$1 and ($2::text is null or
                     ($2='private' and is_private) or ($2='public' and not is_private))
                     and ($3::timestamptz is null or (created_at,id) < ($3,$4))
                   order by created_at desc,id desc limit $5""",
                organization_id,
                visibility,
                after[0] if after else None,
                after[1] if after else None,
                limit + 1,
            )
            counts = await conn.fetchrow(
                """select count(*)::int total,
                          count(*) filter(where is_private)::int private
                     from public.rooms where organization_id=$1""",
                organization_id,
            )
        next_cursor = _cursor(rows[limit - 1]) if len(rows) > limit else None
        return [_row(Room, row) for row in rows[:limit]], next_cursor, dict(counts or {})

    async def create_room(
        self, user_id: UUID, organization_id: UUID, payload: RoomCreateRequest
    ) -> Room:
        async with self.database.privileged() as conn:
            row = await conn.fetchrow(
                """insert into public.rooms(organization_id,name,description,is_private,created_by)
                   select $1,$2,$3,$4,$5 where exists(select 1 from public.organization_members
                     where organization_id=$1 and user_id=$5 and status='active')
                   returning id,name,description,is_private,created_at""",
                organization_id,
                payload.name,
                payload.description,
                payload.is_private,
                user_id,
            )
            if not row:
                raise HTTPException(status_code=403, detail="Active tenant membership required")
            if payload.is_private:
                await conn.execute(
                    """insert into public.room_members(
                         organization_id,room_id,user_id,is_moderator
                       ) values($1,$2,$3,true)""",
                    organization_id,
                    row["id"],
                    user_id,
                )
            await self._emit(conn, organization_id, "rooms.updated", "room", row["id"], dict(row))
        return _row(Room, cast(Mapping[str, Any], row))

    async def patch_room(
        self, user_id: UUID, organization_id: UUID, room_id: UUID, payload: RoomPatchRequest
    ) -> RoomDetailResponse:
        async with self.database.privileged() as conn:
            allowed = await conn.fetchval(
                """select exists(select 1 from public.organization_members m
                   where m.organization_id=$1 and m.user_id=$2 and m.status='active'
                     and (m.role in ('owner','admin','manager') or exists(
                       select 1 from public.room_members rm where rm.room_id=$3
                         and rm.user_id=$2 and rm.is_moderator)))""",
                organization_id,
                user_id,
                room_id,
            )
            if not allowed:
                raise HTTPException(status_code=403, detail="Room manager role required")
            current_room = await conn.fetchrow(
                """select id,is_private from public.rooms
                    where id=$1 and organization_id=$2 for update""",
                room_id,
                organization_id,
            )
            if not current_room:
                raise HTTPException(status_code=404, detail="Room not found")
            target_private = (
                current_room["is_private"]
                if payload.visibility is None
                else payload.visibility == "private"
            )
            for delta in payload.members_delta:
                if delta.action == "remove" or (
                    delta.action == "update" and not delta.is_moderator
                ):
                    is_last = await conn.fetchval(
                        """select is_moderator and (select count(*) from public.room_members
                           where room_id=$1 and is_moderator)=1 from public.room_members
                           where room_id=$1 and user_id=$2""",
                        room_id,
                        delta.user_id,
                    )
                    if is_last and target_private:
                        raise HTTPException(
                            status_code=409, detail="Last moderator cannot be removed"
                        )
                if delta.action == "remove":
                    await conn.execute(
                        "delete from public.room_members where room_id=$1 and user_id=$2",
                        room_id,
                        delta.user_id,
                    )
                else:
                    await conn.execute(
                        """insert into public.room_members(organization_id,room_id,user_id,is_moderator)
                           values($1,$2,$3,$4) on conflict(room_id,user_id) do update
                           set is_moderator=excluded.is_moderator""",
                        organization_id,
                        room_id,
                        delta.user_id,
                        delta.is_moderator,
                    )
            if target_private:
                moderator_count = await conn.fetchval(
                    """select count(*) from public.room_members
                        where room_id=$1 and is_moderator""",
                    room_id,
                )
                if moderator_count == 0:
                    await conn.execute(
                        """insert into public.room_members(
                             organization_id,room_id,user_id,is_moderator
                           ) values($1,$2,$3,true)
                           on conflict(room_id,user_id) do update set is_moderator=true""",
                        organization_id,
                        room_id,
                        user_id,
                    )
            row = await conn.fetchrow(
                """update public.rooms set name=coalesce($3,name),
                     description=case when $4::boolean then $5 else description end,
                     is_private=coalesce($6,is_private), updated_at=now()
                   where id=$1 and organization_id=$2
                   returning id,name,description,is_private,created_at""",
                room_id,
                organization_id,
                payload.title,
                "description" in payload.model_fields_set,
                payload.description,
                None if payload.visibility is None else payload.visibility == "private",
            )
            if not row:
                raise HTTPException(status_code=404, detail="Room not found")
            member_rows = await conn.fetch(
                "select user_id,is_moderator from public.room_members where room_id=$1 order by created_at",
                room_id,
            )
            await self._emit(
                conn,
                organization_id,
                "room.member.changed",
                "room",
                room_id,
                {"roomId": str(room_id), "actorUserId": str(user_id)},
            )
            await self._audit(
                conn,
                organization_id,
                user_id,
                "room.updated",
                "room",
                room_id,
                payload.model_dump(mode="json", exclude_unset=True),
            )
        return RoomDetailResponse(
            room=_row(Room, row),
            members=[_row(RoomMember, item) for item in member_rows],
            audit_trail=[{"event": "room.member.changed", "actorUserId": str(user_id)}],
        )

    async def list_room_files(
        self, user_id: UUID, organization_id: UUID, room_id: UUID, cursor: str | None, limit: int
    ) -> tuple[list[RoomFile], str | None]:
        after = _decode_cursor(cursor)
        async with self.database.authenticated(user_id, organization_id) as conn:
            rows = await conn.fetch(
                """select a.id,a.name,a.kind,a.mime_type,a.size_bytes,
                          a.quarantine_status::text,a.created_at
                     from public.artifacts a join public.rooms r on r.id=a.room_id
                    where a.organization_id=$1 and a.room_id=$2
                      and ($3::timestamptz is null or (a.created_at,a.id)<($3,$4))
                    order by a.created_at desc,a.id desc limit $5""",
                organization_id,
                room_id,
                after[0] if after else None,
                after[1] if after else None,
                limit + 1,
            )
        next_cursor = _cursor(rows[limit - 1]) if len(rows) > limit else None
        return [_row(RoomFile, row) for row in rows[:limit]], next_cursor

    async def list_messages(
        self, user_id: UUID, organization_id: UUID, room_id: UUID, cursor: str | None, limit: int
    ) -> tuple[Room, list[Message], str | None]:
        after = _decode_cursor(cursor)
        async with self.database.authenticated(user_id, organization_id) as conn:
            room = await conn.fetchrow(
                "select id,name,description,is_private,created_at from public.rooms where id=$1 and organization_id=$2",
                room_id,
                organization_id,
            )
            if not room:
                raise HTTPException(status_code=404, detail="Room not found")
            rows = await conn.fetch(
                """select id,room_id,parent_message_id,author_user_id,body,metadata,edited_at,deleted_at,created_at
                     from public.messages where room_id=$1 and organization_id=$2
                       and ($3::timestamptz is null or (created_at,id)<($3,$4))
                     order by created_at desc,id desc limit $5""",
                room_id,
                organization_id,
                after[0] if after else None,
                after[1] if after else None,
                limit + 1,
            )
        next_cursor = _cursor(rows[limit - 1]) if len(rows) > limit else None
        return _row(Room, room), [_row(Message, row) for row in rows[:limit]], next_cursor

    async def create_message(
        self, user_id: UUID, organization_id: UUID, room_id: UUID, payload: MessageCreateRequest
    ) -> Message:
        metadata = {"client_id": payload.client_id} if payload.client_id else {}
        async with self.database.privileged() as conn:
            await self._lock_room_access(conn, organization_id, room_id, user_id)
            if payload.client_id:
                existing = await conn.fetchrow(
                    """select id,room_id,parent_message_id,author_user_id,body,metadata,edited_at,deleted_at,created_at
                         from public.messages where organization_id=$1 and room_id=$2
                           and author_user_id=$3 and metadata->>'client_id'=$4""",
                    organization_id,
                    room_id,
                    user_id,
                    payload.client_id,
                )
                if existing:
                    return _row(Message, existing)
            row = await conn.fetchrow(
                """insert into public.messages(organization_id,room_id,parent_message_id,author_user_id,body,metadata)
                   select $1,$2,$3,$4,$5,$6::jsonb where exists(
                     select 1 from public.rooms r join public.organization_members m on m.organization_id=r.organization_id
                      where r.id=$2 and r.organization_id=$1 and m.user_id=$4 and m.status='active'
                        and (not r.is_private or exists(select 1 from public.room_members rm where rm.room_id=r.id and rm.user_id=$4)))
                     and ($3::uuid is null or exists(select 1 from public.messages parent
                       where parent.id=$3 and parent.organization_id=$1 and parent.room_id=$2))
                   on conflict do nothing
                   returning id,room_id,parent_message_id,author_user_id,body,metadata,edited_at,deleted_at,created_at""",
                organization_id,
                room_id,
                payload.parent_message_id,
                user_id,
                payload.body,
                json.dumps(metadata),
            )
            if not row and payload.client_id:
                row = await conn.fetchrow(
                    """select id,room_id,parent_message_id,author_user_id,body,metadata,
                              edited_at,deleted_at,created_at
                         from public.messages where organization_id=$1 and room_id=$2
                           and author_user_id=$3 and metadata->>'client_id'=$4""",
                    organization_id,
                    room_id,
                    user_id,
                    payload.client_id,
                )
            if not row:
                raise HTTPException(status_code=403, detail="Room access required")
            await self._emit(
                conn, organization_id, "room.message.created", "message", row["id"], dict(row)
            )
        return _row(Message, cast(Mapping[str, Any], row))

    async def list_tasks(
        self,
        user_id: UUID,
        organization_id: UUID,
        status: TaskStatus | None,
        cursor: str | None,
        limit: int,
    ) -> tuple[list[Task], str | None]:
        after = _decode_cursor(cursor)
        async with self.database.authenticated(user_id, organization_id) as conn:
            rows = await conn.fetch(
                """select id,room_id,source_message_id,title,objective,status::text,priority,risk_level::text,
                          requester_id,assignee_id,workflow_version_id,due_at,sla_at,version,metadata,created_at,updated_at
                     from public.tasks where organization_id=$1 and ($2::text is null or status::text=$2)
                       and ($3::timestamptz is null or (created_at,id)<($3,$4))
                     order by created_at desc,id desc limit $5""",
                organization_id,
                status.value if status else None,
                after[0] if after else None,
                after[1] if after else None,
                limit + 1,
            )
        next_cursor = _cursor(rows[limit - 1]) if len(rows) > limit else None
        return [_row(Task, row) for row in rows[:limit]], next_cursor

    async def create_task(
        self, user_id: UUID, organization_id: UUID, payload: TaskCreateRequest, idempotency_key: str
    ) -> tuple[Task, bool]:
        fingerprint = hashlib.sha256(
            json.dumps(
                payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest()
        async with self.database.privileged() as conn:
            await self._lock_active_membership(conn, organization_id, user_id)
            existing = await self._task_for_key(conn, organization_id, idempotency_key)
            if existing:
                self._check_fingerprint(existing, fingerprint)
                return _row(Task, existing), True
            task_id = uuid4()
            title = payload.title or payload.goal[:240]
            metadata = {
                "idempotency_key": idempotency_key,
                "idempotency_fingerprint": fingerprint,
            }
            try:
                async with conn.transaction():
                    row = await conn.fetchrow(
                        """insert into public.tasks(id,organization_id,room_id,source_message_id,title,objective,
                               risk_level,requester_id,assignee_id,workflow_version_id,sla_at,metadata)
                       select $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12::jsonb where exists(
                         select 1 from public.organization_members where organization_id=$2 and user_id=$8 and status='active')
                         and ($3::uuid is null or exists(select 1 from public.rooms
                           where id=$3 and organization_id=$2))
                         and ($4::uuid is null or exists(select 1 from public.messages
                           where id=$4 and organization_id=$2 and ($3::uuid is null or room_id=$3)))
                       returning id,room_id,source_message_id,title,objective,status::text,priority,risk_level::text,
                         requester_id,assignee_id,workflow_version_id,due_at,sla_at,version,metadata,created_at,updated_at""",
                        task_id,
                        organization_id,
                        payload.room_id,
                        payload.source_message_id,
                        title,
                        payload.goal,
                        payload.risk,
                        user_id,
                        payload.assignee_id,
                        payload.workflow_id,
                        payload.sla_at,
                        json.dumps(metadata),
                    )
                if not row:
                    raise HTTPException(status_code=403, detail="Active tenant membership required")
                for dependency in dict.fromkeys(payload.dependencies):
                    result = await conn.execute(
                        """insert into public.task_dependencies(organization_id,task_id,depends_on_task_id)
                           select $1,$2,$3 where exists(select 1 from public.tasks where id=$3 and organization_id=$1)""",
                        organization_id,
                        task_id,
                        dependency,
                    )
                    if result == "INSERT 0 0":
                        raise HTTPException(
                            status_code=422, detail=f"Dependency {dependency} not found"
                        )
                await self._emit(conn, organization_id, "tasks.created", "task", task_id, dict(row))
                await self._audit(
                    conn,
                    organization_id,
                    user_id,
                    "task.created",
                    "task",
                    task_id,
                    {"idempotencyKey": idempotency_key},
                )
            except asyncpg.UniqueViolationError:
                row = await self._task_for_key(conn, organization_id, idempotency_key)
                if not row:
                    raise
                self._check_fingerprint(row, fingerprint)
                return _row(Task, row), True
            except asyncpg.CheckViolationError as exc:
                raise HTTPException(status_code=409, detail="Task dependency cycle") from exc
        return _row(Task, cast(Mapping[str, Any], row)), False

    async def transition_task(
        self, user_id: UUID, organization_id: UUID, task_id: UUID, payload: TaskTransitionRequest
    ) -> tuple[Task, TimelineItem]:
        async with self.database.authenticated(user_id, organization_id) as conn:
            before = await conn.fetchrow(
                "select status::text from public.tasks where id=$1 and organization_id=$2",
                task_id,
                organization_id,
            )
            if not before:
                raise HTTPException(status_code=404, detail="Task not found")
            try:
                row = await conn.fetchrow(
                    """select id,room_id,source_message_id,title,objective,status::text,priority,risk_level::text,
                         requester_id,assignee_id,workflow_version_id,due_at,sla_at,version,metadata,created_at,updated_at
                       from public.transition_task($1,$2,$3,$4)""",
                    task_id,
                    payload.target_state.value,
                    payload.reason,
                    payload.expected_version,
                )
            except asyncpg.SerializationError as exc:
                raise HTTPException(status_code=409, detail="Task version conflict") from exc
            except asyncpg.RaiseError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
        return _row(Task, cast(Mapping[str, Any], row)), TimelineItem(
            from_status=before["status"], to_status=payload.target_state, reason=payload.reason
        )

    async def calendar(
        self, user_id: UUID, organization_id: UUID, start: date, end: date, owner_ids: list[UUID]
    ) -> list[Task]:
        async with self.database.authenticated(user_id, organization_id) as conn:
            rows = await conn.fetch(
                """select id,room_id,source_message_id,title,objective,status::text,priority,risk_level::text,
                         requester_id,assignee_id,workflow_version_id,due_at,sla_at,version,metadata,created_at,updated_at
                     from public.tasks where organization_id=$1 and coalesce(due_at,sla_at)::date between $2 and $3
                       and (cardinality($4::uuid[])=0 or assignee_id=any($4)) order by coalesce(due_at,sla_at),id""",
                organization_id,
                start,
                end,
                owner_ids,
            )
        return [_row(Task, row) for row in rows]

    async def list_runs(
        self,
        user_id: UUID,
        organization_id: UUID,
        task_id: UUID | None,
        status: str | None,
        cursor: str | None,
        limit: int,
    ) -> tuple[list[Run], str | None]:
        after = _decode_cursor(cursor)
        async with self.database.authenticated(user_id, organization_id) as conn:
            rows = await conn.fetch(
                """select id,task_id,status::text,attempt,locked_by,locked_until,
                          heartbeat_at,error_code,error_detail,created_at
                     from public.runs where organization_id=$1
                      and ($2::uuid is null or task_id=$2)
                      and ($3::text is null or status::text=$3)
                      and ($4::timestamptz is null or (created_at,id)<($4,$5))
                    order by created_at desc,id desc limit $6""",
                organization_id,
                task_id,
                status,
                after[0] if after else None,
                after[1] if after else None,
                limit + 1,
            )
        next_cursor = _cursor(rows[limit - 1]) if len(rows) > limit else None
        return [_row(Run, row) for row in rows[:limit]], next_cursor

    async def retry_run(self, user_id: UUID, organization_id: UUID, run_id: UUID) -> Run:
        async with self.database.privileged() as conn:
            previous = await conn.fetchrow(
                """select r.* from public.runs r join public.organization_members m
                     on m.organization_id=r.organization_id and m.user_id=$3 and m.status='active'
                    where r.id=$1 and r.organization_id=$2 for update""",
                run_id,
                organization_id,
                user_id,
            )
            if not previous:
                raise HTTPException(status_code=404, detail="Run not found")
            if (
                previous["status"] == "running"
                and previous["locked_until"]
                and previous["locked_until"] > datetime.now(UTC)
            ):
                raise HTTPException(status_code=423, detail="Run has an active lease")
            if previous["attempt"] >= 5:
                raise HTTPException(status_code=429, detail="Retry limit reached")
            retry_key = f"retry:{run_id}:{previous['attempt'] + 1}"
            existing = await conn.fetchrow(
                """select id,task_id,status::text,attempt,locked_by,locked_until,
                          heartbeat_at,error_code,error_detail,created_at
                     from public.runs where organization_id=$1 and idempotency_key=$2""",
                organization_id,
                retry_key,
            )
            if existing:
                return _row(Run, existing)
            new_id = uuid4()
            try:
                async with conn.transaction():
                    row = await conn.fetchrow(
                        """insert into public.runs(id,organization_id,task_id,workflow_version_id,
                             status,idempotency_key,attempt)
                           values($1,$2,$3,$4,'queued',$5,$6)
                           returning id,task_id,status::text,attempt,locked_by,locked_until,
                             heartbeat_at,error_code,error_detail,created_at""",
                        new_id,
                        organization_id,
                        previous["task_id"],
                        previous["workflow_version_id"],
                        retry_key,
                        previous["attempt"] + 1,
                    )
            except asyncpg.UniqueViolationError:
                row = await conn.fetchrow(
                    """select id,task_id,status::text,attempt,locked_by,locked_until,
                              heartbeat_at,error_code,error_detail,created_at
                         from public.runs where organization_id=$1 and idempotency_key=$2""",
                    organization_id,
                    retry_key,
                )
                if not row:
                    raise
                return _row(Run, row)
            await self._emit(
                conn,
                organization_id,
                "runs.retry.requested",
                "run",
                new_id,
                {"runId": str(new_id), "previousRunId": str(run_id)},
            )
            await self._audit(
                conn,
                organization_id,
                user_id,
                "run.retry_requested",
                "run",
                new_id,
                {"previousRunId": str(run_id), "attempt": previous["attempt"] + 1},
            )
        return _row(Run, cast(Mapping[str, Any], row))

    async def failures(
        self, user_id: UUID, organization_id: UUID, limit: int
    ) -> list[FailureGroup]:
        async with self.database.authenticated(user_id, organization_id) as conn:
            rows = await conn.fetch(
                """select coalesce(error_code,'unknown') code,count(*)::int count,
                          count(distinct task_id)::int affected_tasks,max(created_at) latest_at
                     from public.runs where organization_id=$1 and status='failed'
                    group by coalesce(error_code,'unknown') order by max(created_at) desc limit $2""",
                organization_id,
                limit,
            )
        return [_row(FailureGroup, row) for row in rows]

    async def _task_for_key(
        self, conn: asyncpg.Connection[Any], organization_id: UUID, key: str
    ) -> Mapping[str, Any] | None:
        row = await conn.fetchrow(
            """select id,room_id,source_message_id,title,objective,status::text,priority,risk_level::text,
                     requester_id,assignee_id,workflow_version_id,due_at,sla_at,version,metadata,created_at,updated_at
                 from public.tasks where organization_id=$1 and metadata->>'idempotency_key'=$2""",
            organization_id,
            key,
        )
        return cast(Mapping[str, Any] | None, row)

    async def _lock_active_membership(
        self,
        conn: asyncpg.Connection[Any],
        organization_id: UUID,
        user_id: UUID,
    ) -> None:
        membership = await conn.fetchrow(
            """select organization_id from public.organization_members
                where organization_id=$1 and user_id=$2 and status='active'
                for share""",
            organization_id,
            user_id,
        )
        if not membership:
            raise HTTPException(status_code=403, detail="Active tenant membership required")

    async def _lock_room_access(
        self,
        conn: asyncpg.Connection[Any],
        organization_id: UUID,
        room_id: UUID,
        user_id: UUID,
    ) -> None:
        await self._lock_active_membership(conn, organization_id, user_id)
        room = await conn.fetchrow(
            """select id,is_private from public.rooms
                where id=$1 and organization_id=$2 for share""",
            room_id,
            organization_id,
        )
        if not room:
            raise HTTPException(status_code=403, detail="Room access required")
        if room["is_private"]:
            room_member = await conn.fetchrow(
                """select room_id from public.room_members
                    where room_id=$1 and user_id=$2 for share""",
                room_id,
                user_id,
            )
            if not room_member:
                raise HTTPException(status_code=403, detail="Room access required")

    async def _emit(
        self,
        conn: asyncpg.Connection[Any],
        organization_id: UUID,
        event_type: str,
        aggregate_type: str,
        aggregate_id: UUID,
        payload: dict[str, Any],
    ) -> None:
        await conn.execute(
            """insert into public.event_outbox(organization_id,event_type,aggregate_type,aggregate_id,payload)
               values($1,$2,$3,$4,$5::jsonb)""",
            organization_id,
            event_type,
            aggregate_type,
            aggregate_id,
            json.dumps(payload, default=str),
        )

    async def _audit(
        self,
        conn: asyncpg.Connection[Any],
        organization_id: UUID,
        user_id: UUID,
        action: str,
        resource_type: str,
        resource_id: UUID,
        changes: dict[str, Any],
    ) -> None:
        await conn.execute(
            """insert into public.audit_log(
                 organization_id,actor_user_id,actor_type,action,resource_type,
                 resource_id,changes_redacted
               ) values($1,$2,'user',$3,$4,$5,$6::jsonb)""",
            organization_id,
            user_id,
            action,
            resource_type,
            str(resource_id),
            json.dumps(changes, default=str),
        )

    def _check_fingerprint(self, row: Mapping[str, Any], fingerprint: str) -> None:
        metadata = row["metadata"]
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        if metadata.get("idempotency_fingerprint") != fingerprint:
            raise HTTPException(
                status_code=409,
                detail="Idempotency-Key was already used with a different request",
            )


ALLOWED: dict[TaskStatus, list[TaskStatus]] = {
    TaskStatus.NEW: [TaskStatus.TRIAGED, TaskStatus.CANCELED],
    TaskStatus.TRIAGED: [TaskStatus.IN_PROGRESS, TaskStatus.CANCELED],
    TaskStatus.IN_PROGRESS: [
        TaskStatus.WAITING_TOOL,
        TaskStatus.WAITING_HUMAN,
        TaskStatus.READY_FOR_REVIEW,
        TaskStatus.FAILED,
        TaskStatus.CANCELED,
    ],
    TaskStatus.WAITING_TOOL: [TaskStatus.IN_PROGRESS, TaskStatus.FAILED, TaskStatus.CANCELED],
    TaskStatus.WAITING_HUMAN: [
        TaskStatus.IN_PROGRESS,
        TaskStatus.READY_FOR_REVIEW,
        TaskStatus.CANCELED,
    ],
    TaskStatus.READY_FOR_REVIEW: [TaskStatus.APPROVED, TaskStatus.IN_PROGRESS, TaskStatus.CANCELED],
    TaskStatus.APPROVED: [TaskStatus.DONE, TaskStatus.IN_PROGRESS],
    TaskStatus.FAILED: [TaskStatus.IN_PROGRESS, TaskStatus.CANCELED],
}
