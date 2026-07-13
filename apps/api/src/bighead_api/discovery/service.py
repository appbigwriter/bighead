from dataclasses import dataclass
from typing import Any
from uuid import UUID

from bighead_api.discovery.models import GlobalSearchRequest
from bighead_api.identity.repository import Database


@dataclass
class DiscoveryRepository:
    database: Database

    async def search(
        self, user_id: UUID, organization_id: UUID, payload: GlobalSearchRequest
    ) -> dict[str, Any]:
        pattern = f"%{_escape_like(payload.query)}%"
        groups: list[dict[str, Any]] = []
        per_scope = max(1, payload.limit // max(1, len(payload.scopes)))
        async with self.database.authenticated(user_id, organization_id) as conn:
            if "rooms" in payload.scopes:
                rows = await conn.fetch(
                    """select id,name as title,description,created_at from public.rooms
                        where organization_id=$1 and (name ilike $2 escape '\\'
                           or coalesce(description,'') ilike $2 escape '\\')
                        order by created_at desc limit $3""",
                    organization_id,
                    pattern,
                    per_scope,
                )
                groups.append({"scope": "rooms", "items": [dict(row) for row in rows]})
            if "messages" in payload.scopes:
                rows = await conn.fetch(
                    """select id,room_id,body as title,created_at from public.messages
                        where organization_id=$1 and body ilike $2 escape '\\'
                        order by created_at desc limit $3""",
                    organization_id,
                    pattern,
                    per_scope,
                )
                groups.append({"scope": "messages", "items": [dict(row) for row in rows]})
            if "tasks" in payload.scopes:
                rows = await conn.fetch(
                    """select id,title,objective as description,status,created_at from public.tasks
                        where organization_id=$1 and (title ilike $2 escape '\\'
                           or objective ilike $2 escape '\\')
                        order by created_at desc limit $3""",
                    organization_id,
                    pattern,
                    per_scope,
                )
                groups.append({"scope": "tasks", "items": [dict(row) for row in rows]})
        return {
            "groups": groups,
            "shortcuts": [{"label": "Criar tarefa", "path": "/operacao/tarefas"}],
            "removed_count": 0,
        }

    async def notifications(
        self,
        user_id: UUID,
        organization_id: UUID,
        *,
        unread_only: bool,
        limit: int,
    ) -> dict[str, Any]:
        async with self.database.authenticated(user_id, organization_id) as conn:
            rows = await conn.fetch(
                """select id,kind,title,body,resource_type,resource_id,read_at,created_at
                     from public.notifications where organization_id=$1 and user_id=$2
                       and (not $3::boolean or read_at is null)
                     order by created_at desc,id desc limit $4""",
                organization_id,
                user_id,
                unread_only,
                limit + 1,
            )
            unread_count = await conn.fetchval(
                """select count(*) from public.notifications
                    where organization_id=$1 and user_id=$2 and read_at is null""",
                organization_id,
                user_id,
            )
        has_more = len(rows) > limit
        selected = rows[:limit]
        return {
            "items": [dict(row) for row in selected],
            "unread_count": int(unread_count),
            "next_cursor": str(selected[-1]["id"]) if has_more and selected else None,
        }


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
