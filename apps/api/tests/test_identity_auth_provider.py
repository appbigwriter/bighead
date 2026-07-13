from uuid import UUID

import httpx
import pytest
import respx
from bighead_api.identity.auth import SupabaseAuthProvider


@pytest.mark.asyncio
@respx.mock
async def test_verify_reuses_and_closes_the_auth_connection_pool() -> None:
    route = respx.get("http://supabase.test/auth/v1/user").mock(
        return_value=httpx.Response(
            200,
            json={"id": "d1000000-0000-0000-0000-000000000001", "email": "owner@example.com"},
        )
    )
    provider = SupabaseAuthProvider("http://supabase.test", "publishable", "secret")

    first = await provider.verify("header.payload.signature")
    client = provider._verification_client
    second = await provider.verify("header.payload.signature")

    assert first.id == second.id == UUID("d1000000-0000-0000-0000-000000000001")
    assert provider._verification_client is client
    assert route.call_count == 2

    await provider.close()
    assert provider._verification_client is None
