from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


def _camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.title() for part in tail)


def _default_scopes() -> list[Literal["rooms", "messages", "tasks"]]:
    return ["rooms", "messages", "tasks"]


class DiscoveryModel(BaseModel):
    model_config = ConfigDict(alias_generator=lambda value: _camel(value), populate_by_name=True)


class GlobalSearchRequest(DiscoveryModel):
    query: str = Field(min_length=2, max_length=200)
    scopes: list[Literal["rooms", "messages", "tasks"]] = Field(
        default_factory=_default_scopes, max_length=3
    )
    limit: int = Field(default=20, ge=1, le=50)


class GlobalSearchResponse(DiscoveryModel):
    groups: list[dict[str, Any]]
    shortcuts: list[dict[str, str]]
    removed_count: int = 0


class NotificationListResponse(DiscoveryModel):
    items: list[dict[str, Any]]
    unread_count: int
    next_cursor: str | None = None
