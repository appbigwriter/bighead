from types import TracebackType
from typing import Any
from uuid import UUID

import pytest
from bighead_api.identity.repository import Database


class FakeTransaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None


class FakeConnection:
    def __init__(self) -> None:
        self.executions: list[tuple[str, tuple[Any, ...]]] = []

    def transaction(self) -> FakeTransaction:
        return FakeTransaction()

    async def execute(self, query: str, *args: Any) -> str:
        self.executions.append((query, args))
        return "OK"


class FakeAcquire:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    async def __aenter__(self) -> FakeConnection:
        return self.connection

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None


class FakePool:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    def acquire(self) -> FakeAcquire:
        return FakeAcquire(self.connection)

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_authenticated_transaction_sets_role_user_and_tenant_claims() -> None:
    user_id = UUID("10000000-0000-0000-0000-000000000001")
    organization_id = UUID("20000000-0000-0000-0000-000000000001")
    connection = FakeConnection()
    database = Database("unused")
    database._pool = FakePool(connection)  # type: ignore[assignment]

    async with database.authenticated(user_id, organization_id) as yielded:
        assert yielded is connection

    assert connection.executions == [
        ("set local role authenticated", ()),
        ("select set_config('request.jwt.claim.sub', $1, true)", (str(user_id),)),
        (
            "select set_config('request.jwt.claim.organization_id', $1, true)",
            (str(organization_id),),
        ),
    ]


@pytest.mark.asyncio
async def test_privileged_operations_use_the_separate_service_pool() -> None:
    tenant_connection = FakeConnection()
    service_connection = FakeConnection()
    database = Database("tenant-role", "service-role")
    database._pool = FakePool(tenant_connection)  # type: ignore[assignment]
    database._service_pool = FakePool(service_connection)  # type: ignore[assignment]

    async with database.privileged() as yielded:
        assert yielded is service_connection

    assert tenant_connection.executions == []
