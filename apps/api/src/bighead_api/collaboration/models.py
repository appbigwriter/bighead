from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import Field, field_validator

from bighead_api.artifacts.models import ArtifactDownloadResponse
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


class RoomMemberDelta(ApiModel):
    user_id: UUID
    action: str
    is_moderator: bool = False

    @field_validator("action")
    @classmethod
    def valid_action(cls, value: str) -> str:
        if value not in {"add", "update", "remove"}:
            raise ValueError("invalid member action")
        return value


class RoomPatchRequest(ApiModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    visibility: str | None = None
    members_delta: list[RoomMemberDelta] = Field(default_factory=list, max_length=100)

    @field_validator("visibility")
    @classmethod
    def valid_visibility(cls, value: str | None) -> str | None:
        if value is not None and value not in {"public", "private"}:
            raise ValueError("invalid visibility")
        return value


class RoomMember(ApiModel):
    user_id: UUID
    is_moderator: bool


class RoomDetailResponse(ApiModel):
    room: Room
    members: list[RoomMember]
    audit_trail: list[dict[str, Any]] = Field(default_factory=list)


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


class RoomFile(ApiModel):
    id: UUID
    name: str
    kind: str
    mime_type: str | None = None
    size_bytes: int | None = None
    quarantine_status: str
    created_at: datetime


class RoomFileListResponse(ApiModel):
    files: list[RoomFile]
    signed_preview: ArtifactDownloadResponse | None = None
    next_cursor: str | None = None


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

    @field_validator("risk")
    @classmethod
    def valid_risk(cls, value: str) -> str:
        if value not in {"low", "medium", "high", "critical"}:
            raise ValueError("invalid risk")
        return value


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


class Run(ApiModel):
    id: UUID
    task_id: UUID
    status: str
    attempt: int
    locked_by: str | None = None
    locked_until: datetime | None = None
    heartbeat_at: datetime | None = None
    error_code: str | None = None
    error_detail: dict[str, Any] | None = None
    created_at: datetime


class RunListResponse(ApiModel):
    runs: list[Run]
    heartbeats: list[dict[str, Any]]
    next_cursor: str | None = None


class RunRetryResponse(ApiModel):
    run: Run
    previous_run_id: UUID


class FailureGroup(ApiModel):
    code: str
    count: int
    affected_tasks: int
    latest_at: datetime


class FailureGroupResponse(ApiModel):
    groups: list[FailureGroup]
    impact_summary: dict[str, int]
    next_cursor: str | None = None
