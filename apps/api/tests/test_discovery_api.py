from uuid import UUID

from bighead_api.discovery.models import GlobalSearchRequest
from bighead_api.discovery.routes import repository, router
from bighead_api.identity.dependencies import TenantContext, tenant_context
from bighead_api.identity.models import AuthUser, MemberRole, Membership
from fastapi import FastAPI
from fastapi.testclient import TestClient

USER_ID = UUID("10000000-0000-0000-0000-000000000001")
ORG_ID = UUID("20000000-0000-0000-0000-000000000001")


class FakeDiscoveryRepository:
    async def search(
        self, user_id: UUID, organization_id: UUID, payload: GlobalSearchRequest
    ) -> dict[str, object]:
        assert (user_id, organization_id) == (USER_ID, ORG_ID)
        return {
            "groups": [{"scope": "tasks", "items": [{"title": payload.query}]}],
            "shortcuts": [],
            "removed_count": 0,
        }

    async def notifications(
        self,
        user_id: UUID,
        organization_id: UUID,
        *,
        unread_only: bool,
        limit: int,
    ) -> dict[str, object]:
        assert unread_only is True and limit == 10
        return {"items": [{"title": "Review"}], "unread_count": 1, "next_cursor": None}


def make_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)

    async def context() -> TenantContext:
        return TenantContext(
            user=AuthUser(id=USER_ID, email="member@example.com"),
            token="valid",
            membership=Membership(
                id="membership",
                organization_id=ORG_ID,
                user_id=USER_ID,
                role=MemberRole.MEMBER,
                status="active",
            ),
        )

    app.dependency_overrides[tenant_context] = context
    app.dependency_overrides[repository] = FakeDiscoveryRepository
    return TestClient(app)


def test_t07_global_search_is_tenant_scoped_and_no_store() -> None:
    response = make_client().post(
        "/v1/search/global", json={"query": "launch", "scopes": ["tasks"], "limit": 10}
    )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["groups"][0]["items"][0]["title"] == "launch"


def test_t08_notifications_respects_unread_filter() -> None:
    response = make_client().get("/v1/notifications?filter=unread&limit=10")
    assert response.status_code == 200
    assert response.json() == {
        "items": [{"title": "Review"}],
        "unreadCount": 1,
        "nextCursor": None,
    }


def test_global_search_rejects_unbounded_or_unknown_scopes() -> None:
    response = make_client().post(
        "/v1/search/global", json={"query": "x", "scopes": ["secrets"], "limit": 1000}
    )
    assert response.status_code == 422
