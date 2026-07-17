# ruff: noqa: ASYNC230, ASYNC240
import os
import shutil
import tempfile
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from bighead_api.governance.routes import repository, router
from bighead_api.governance.service import PostgresGovernanceRepository
from bighead_api.identity.dependencies import TenantContext, tenant_context
from bighead_api.identity.models import AuthUser, MemberRole, Membership
from bighead_api.identity.repository import Database
from fastapi import FastAPI
from fastapi.testclient import TestClient

USER_ID = UUID("10000000-0000-0000-0000-000000000001")
ORG_ID = UUID("20000000-0000-0000-0000-000000000001")
AGENT_ID = UUID("50000000-0000-0000-0000-000000000001")
VERSION_ID = UUID("60000000-0000-0000-0000-000000000001")


class AsyncContextManagerMock:
    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.fixture
def temp_profiles_dir():
    dir_path = tempfile.mkdtemp()
    yield dir_path
    shutil.rmtree(dir_path)


def make_smoke_client(repo) -> TestClient:
    app = FastAPI()
    app.include_router(router)

    async def context() -> TenantContext:
        return TenantContext(
            user=AuthUser(id=USER_ID, email="admin@example.com"),
            token="token",
            membership=Membership(
                id="member",
                organization_id=ORG_ID,
                user_id=USER_ID,
                role=MemberRole.ADMIN,
                status="active",
            ),
        )

    app.dependency_overrides[tenant_context] = context
    app.dependency_overrides[repository] = lambda: repo
    return TestClient(app)


@pytest.mark.asyncio
async def test_agent_smoke_lifecycle(temp_profiles_dir) -> None:
    # 1. Configurar Mocks do Banco
    conn = AsyncMock()
    conn.transaction = MagicMock(return_value=AsyncContextManagerMock(None))

    # Variável interna para acompanhar se a edição já foi feita para mudar os mocks
    state = {"edited": False}

    async def mock_fetchrow(query, *args):
        query_lower = query.lower()
        print(f"[FETCHROW] Query: {query} Args: {args}")
        if "insert into public.agents" in query_lower:
            res = {"id": args[0]}
            print(f"[FETCHROW] Retorno: {res}")
            return res
        elif "select * from public.agents where slug=" in query_lower:
            print("[FETCHROW] Retorno: None")
            return None
        elif "select * from public.agents where id=" in query_lower:
            name = "Hermes SDR" if state["edited"] else "Hermes Agent"
            res = {
                "id": args[0],
                "organization_id": ORG_ID,
                "name": name,
                "slug": "hermes-agent",
                "is_enabled": state["edited"],
                "risk_level": "low",
                "trust_score": 0.95,
                "created_at": "2026-07-15T12:00:00Z",
                "updated_at": "2026-07-15T12:00:00Z",
            }
            print(f"[FETCHROW] Retorno: {res}")
            return res
        elif "v.id as agent_version_id" in query_lower or "select a.name" in query_lower:
            res = {
                "name": "Hermes SDR",
                "risk_level": "low",
                "is_enabled": True,
                "agent_version_id": VERSION_ID,
                "version": 2,
                "system_prompt": "Prompt atualizado",
                "model_id": UUID("76000000-0000-0000-0000-000000000001"),
            }
            print(f"[FETCHROW] Retorno: {res}")
            return res
        elif "coalesce(max(v.version)" in query_lower:
            version = 2 if state["edited"] else 1
            res = {
                "id": args[0],
                "organization_id": ORG_ID,
                "name": "Hermes SDR",
                "slug": "hermes-agent",
                "risk_level": "low",
                "is_enabled": True,
                "current_version": version,
            }
            print(f"[FETCHROW] Retorno: {res}")
            return res
        elif "from public.agent_versions" in query_lower and "order by version desc" in query_lower:
            res = {
                "id": VERSION_ID,
                "model_id": None,
                "system_prompt": "Prompt do Hermes",
                "configuration": {},
            }
            print(f"[FETCHROW] Retorno: {res}")
            return res
        elif "select risk_level" in query_lower:
            res = {"risk_level": "low", "current_version": 2}
            print(f"[FETCHROW] Retorno: {res}")
            return res
        print("[FETCHROW] Retorno: None")
        return None

    async def mock_fetchval(query, *args):
        query_lower = query.lower()
        print(f"[FETCHVAL] Query: {query} Args: {args}")
        if "insert into public.agent_versions" in query_lower:
            res = args[0]
            print(f"[FETCHVAL] Retorno: {res}")
            return res
        elif "update public.agents set is_enabled=false" in query_lower:
            res = args[0]
            print(f"[FETCHVAL] Retorno: {res}")
            return res
        elif "select slug from public.organizations" in query_lower:
            print("[FETCHVAL] Retorno: org-slug")
            return "org-slug"
        elif "organization_members" in query_lower:
            print("[FETCHVAL] Retorno: True")
            return True
        print("[FETCHVAL] Retorno: None")
        return None

    async def mock_fetch(query, *args):
        query_lower = query.lower()
        print(f"[FETCH] Query: {query} Args: {args}")
        if "from public.agent_versions" in query_lower:
            prompt = "Prompt atualizado" if state["edited"] else "Prompt do Hermes"
            model_id = UUID("76000000-0000-0000-0000-000000000001") if state["edited"] else None
            res = [
                {
                    "id": VERSION_ID,
                    "version": 2 if state["edited"] else 1,
                    "model_id": model_id,
                    "system_prompt": prompt,
                    "configuration": {},
                    "published_at": None,
                    "created_at": "2026-07-15T12:00:00Z",
                    "skill_ids": [],
                }
            ]
            print(f"[FETCH] Retorno: {res}")
            return res
        elif "from public.skills" in query_lower:
            print("[FETCH] Retorno: []")
            return []
        print("[FETCH] Retorno: []")
        return []

    conn.fetchrow.side_effect = mock_fetchrow
    conn.fetchval.side_effect = mock_fetchval
    conn.fetch.side_effect = mock_fetch

    database = MagicMock(spec=Database)
    database.privileged.side_effect = lambda: AsyncContextManagerMock(conn)
    database.authenticated.side_effect = lambda user_id, org_id: AsyncContextManagerMock(conn)

    repo = PostgresGovernanceRepository(
        database, "test-pepper", hermes_profiles_dir=temp_profiles_dir
    )
    client = make_smoke_client(repo)

    # 2. Executar Criação via POST /v1/agents
    payload = {"name": "Hermes Agent", "slug": "hermes-agent", "prompt": "Prompt do Hermes"}
    response = client.post("/v1/agents", json=payload)
 
    assert response.status_code == 201
    assert response.json()["agent"]["name"] == "Hermes Agent"
    created_id = response.json()["agent"]["id"]
 
    # Validar se o arquivo profile YAML foi gravado
    assert len(os.listdir(temp_profiles_dir)) == 1
 
    # 3. Executar Edição via PATCH /v1/agents/{agentId}
    patch_payload = {
        "name": "Hermes SDR",
        "prompt": "Prompt atualizado",
        "modelId": "76000000-0000-0000-0000-000000000001",
        "expectedVersion": 1,
    }
    patch_response = client.patch(f"/v1/agents/{created_id}", json=patch_payload)
    assert patch_response.status_code == 200
    state["edited"] = True

    # Validar se o profile YAML foi atualizado
    yaml_path = os.path.join(temp_profiles_dir, f"{VERSION_ID}.yaml")
    with open(yaml_path, encoding="utf-8") as f:
        content = f.read()
    assert 'name: "Hermes SDR"' in content
    assert 'system_prompt: "Prompt atualizado"' in content
 
    # 4. Executar Arquivamento/Deleção via DELETE /v1/agents/{agentId}
    delete_response = client.delete(f"/v1/agents/{created_id}?expectedVersion=2")
    assert delete_response.status_code == 204
 
    # Validar se o profile YAML foi desabilitado (removido)
    assert not os.path.exists(yaml_path)
