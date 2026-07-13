from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

import pytest
from bighead_worker.privacy import PrivacyRequest, process_privacy_requests


@dataclass
class Store:
    requests: list[PrivacyRequest]
    should_fail: bool = False
    completed: list[tuple[UUID, dict[str, Any]]] = field(default_factory=list)
    failed: list[UUID] = field(default_factory=list)

    async def claim(self, worker: str, limit: int, lease_seconds: int) -> list[PrivacyRequest]:
        return self.requests[:limit]

    async def process(self, request: PrivacyRequest, worker: str) -> dict[str, Any]:
        if self.should_fail:
            raise RuntimeError("provider unavailable")
        return {"exportPath": f"privacy/{request.id}.json"}

    async def complete(self, request_id: UUID, worker: str, evidence: dict[str, Any]) -> bool:
        self.completed.append((request_id, evidence))
        return True

    async def fail(self, request_id: UUID, worker: str, error: str, max_attempts: int) -> bool:
        self.failed.append(request_id)
        return True


def request() -> PrivacyRequest:
    return PrivacyRequest(uuid4(), uuid4(), uuid4(), "export", 1)


@pytest.mark.asyncio
async def test_privacy_export_completes_with_evidence() -> None:
    item = request()
    store = Store([item])
    assert await process_privacy_requests(store, worker="privacy-a") == (1, 0)
    assert store.completed[0][0] == item.id
    assert store.failed == []


@pytest.mark.asyncio
async def test_privacy_failure_returns_to_database_retry_lifecycle() -> None:
    item = request()
    store = Store([item], should_fail=True)
    assert await process_privacy_requests(store, worker="privacy-a") == (0, 1)
    assert store.failed == [item.id]
