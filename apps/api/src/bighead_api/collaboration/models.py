from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import Field

from bighead_api.identity.models import ApiModel


class TaskStatus(StrEnum):
    NEW = "new"
    TRIAGED = "triaged"
    IN_PROGRESS = "in_progress"
    WAITING_TOOL = "waiting_tool"
    WAITING_HUMAN = "waiting_human"
    READY_FOR_REVIEW = "ready_for_review"
    APPROVED = "approved"
    DONE = "done"
    FAILED = "failed"
    CANCELED = "canceled"


class Room(ApiModel):
    id: UUID
    name: str
    description: str | None = None
    is_private: bool
    created_at: datetime


class RoomListResponse(ApiModel):
    rooms: list[Room]
    counters: dict[str, int]
    next_cursor: str | None = None


class RoomCreateRequest(ApiModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    is_private: bool = False


class Message(ApiModel):
    id: UUID
    room_id: UUID
    parent_message_id: UUID | None = None
    author_user_id: UUID | None = None
    body: str
    metadata: dict[str, Any]
    edited_at: datetime | None = None
    deleted_at: datetime | None = None
    created_at: datetime


class MessageListResponse(ApiModel):
    messages: list[Message]
    next_cursor: str | None = None
    room_context: Room


class MessageCreateRequest(ApiModel):
    body: str = Field(min_length=1, max_length=100_000)
    parent_message_id: UUID | None = None
    client_id: str | None = Field(default=None, max_length=120)


class Task(ApiModel):
    id: UUID
    room_id: UUID | None = None
    source_message_id: UUID | None = None
    title: str
    objective: str
    status: TaskStatus
    priority: int
    risk_level: str
    requester_id: UUID | None = None
    assignee_id: UUID | None = None
    workflow_version_id: UUID | None = None
    due_at: datetime | None = None
    sla_at: datetime | None = None
    version: int
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class TaskListResponse(ApiModel):
    items: list[Task]
    saved_views: list[dict[str, Any]] = Field(default_factory=list)
    next_cursor: str | None = None


class TaskCreateRequest(ApiModel):
    goal: str = Field(min_length=1, max_length=10_000)
    title: str | None = Field(default=None, max_length=240)
    risk: str = "low"
    workflow_id: UUID | None = None
    assignee_id: UUID | None = None
    room_id: UUID | None = None
    source_message_id: UUID | None = None
    sla_at: datetime | None = None
    dependencies: list[UUID] = Field(default_factory=list, max_length=100)


class TaskCreateResponse(ApiModel):
    task: Task
    route_preview: dict[str, Any]
    created_artifacts: list[dict[str, Any]] = Field(default_factory=list)
    replayed: bool = False


class TaskTransitionRequest(ApiModel):
    target_state: TaskStatus
    reason: str | None = Field(default=None, max_length=4000)
    expected_version: int = Field(ge=1)


class TimelineItem(ApiModel):
    from_status: TaskStatus
    to_status: TaskStatus
    reason: str | None = None


class TaskTransitionResponse(ApiModel):
    task: Task
    timeline_item: TimelineItem
    allowed_transitions: list[TaskStatus]


class CalendarDay(ApiModel):
    date: str
    tasks: list[Task]


class TaskCalendarResponse(ApiModel):
    days: list[CalendarDay]
    overdue_count: int
    risk_count: int
