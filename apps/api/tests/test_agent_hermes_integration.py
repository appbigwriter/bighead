# ruff: noqa: ASYNC230, ASYNC240
import os
import shutil
import tempfile
from uuid import UUID, uuid4

import pytest
from bighead_api.governance.models import AgentCreateRequest, AgentPatchRequest
from bighead_api.governance.service import PostgresGovernanceRepository
from bighead_api.identity.repository import Database
from fastapi import HTTPException

ATLAS_OWNER_ID = UUID("10000000-0000-0000-0000-000000000001")
ATLAS_ORGANIZATION_ID = UUID("20000000-0000-0000-0000-000000000001")


@pytest.fixture
def temp_profiles_dir():
    dir_path = tempfile.mkdtemp()
    yield dir_path
    shutil.rmtree(dir_path)


@pytest.mark.skipif(
    "SUPABASE_INTEGRATION_DATABASE_URL" not in os.environ,
    reason="Requires real Supabase URL",
)
@pytest.mark.asyncio
async def test_agent_creation_syncs_hermes_profile_and_rollback_on_failure(
    temp_profiles_dir,
) -> None:
    database = Database(os.environ["SUPABASE_INTEGRATION_DATABASE_URL"])
    repo = PostgresGovernanceRepository(
        database, "integration-pepper", hermes_profiles_dir=temp_profiles_dir
    )

    slug = f"agent-hermes-{uuid4()}"
    agent_id = None

    # 1. Caso Feliz: Criação com sucesso e gravação do profile YAML
    try:
        created = await repo.create_agent(
            ATLAS_OWNER_ID,
            ATLAS_ORGANIZATION_ID,
            AgentCreateRequest(name="Hermes SDR", slug=slug, prompt="Prompt do Hermes"),
        )
        agent_id = created["agent"]["id"]
        assert created["versions"][0]["version"] == 1

        # Verifica se o arquivo profile foi criado no filesystem
        yaml_path = os.path.join(temp_profiles_dir, f"{agent_id}.yaml")
        assert os.path.exists(yaml_path)

        with open(yaml_path, encoding="utf-8") as f:
            content = f.read()
        assert f"agent_id: {agent_id}" in content
        assert "name: Hermes SDR" in content
        assert "model: hermes" in content
        assert "enabled: false" in content  # Sem model_id, o agente inicia desabilitado

    finally:
        if agent_id:
            pool = await database.pool()
            await pool.execute("delete from public.agents where id=$1", agent_id)

    # 2. Caso de Falha: Se a gravação no filesystem falhar, deve fazer rollback no banco
    invalid_repo = PostgresGovernanceRepository(
        database, "integration-pepper", hermes_profiles_dir="/invalid/directory/path/non/existent"
    )

    slug_fail = f"agent-fail-{uuid4()}"
    with pytest.raises(HTTPException) as exc_info:
        await invalid_repo.create_agent(
            ATLAS_OWNER_ID,
            ATLAS_ORGANIZATION_ID,
            AgentCreateRequest(name="Hermes Fail", slug=slug_fail, prompt="Prompt fail"),
        )
    assert exc_info.value.status_code == 500
    assert "Hermes profile synchronization failed" in exc_info.value.detail

    # Verifica que o agente não foi cadastrado no banco devido ao rollback da transação
    pool = await database.pool()
    agent_exists = await pool.fetchval(
        "select exists(select 1 from public.agents where slug=$1 and organization_id=$2)",
        slug_fail,
        ATLAS_ORGANIZATION_ID,
    )
    assert agent_exists is False

    await database.close()


@pytest.mark.skipif(
    "SUPABASE_INTEGRATION_DATABASE_URL" not in os.environ,
    reason="Requires real Supabase URL",
)
@pytest.mark.asyncio
async def test_agent_edit_and_delete_schedules_hermes_updates(temp_profiles_dir) -> None:
    database = Database(os.environ["SUPABASE_INTEGRATION_DATABASE_URL"])
    repo = PostgresGovernanceRepository(
        database, "integration-pepper", hermes_profiles_dir=temp_profiles_dir
    )

    slug = f"agent-edit-{uuid4()}"
    agent_id = None

    try:
        # Cria agente inicial
        created = await repo.create_agent(
            ATLAS_OWNER_ID,
            ATLAS_ORGANIZATION_ID,
            AgentCreateRequest(name="Hermes Edit", slug=slug, prompt="Prompt original"),
        )
        agent_id = created["agent"]["id"]
        yaml_path = os.path.join(temp_profiles_dir, f"{agent_id}.yaml")
        assert os.path.exists(yaml_path)

        # Edita o agente gerando nova versão
        updated = await repo.patch_agent(
            ATLAS_OWNER_ID,
            ATLAS_ORGANIZATION_ID,
            agent_id,
            AgentPatchRequest(prompt="Prompt atualizado", expected_version=1),
        )
        assert updated["versions"][0]["version"] == 2

        # Verifica se o arquivo profile foi atualizado no filesystem
        with open(yaml_path, encoding="utf-8") as f:
            content = f.read()
        assert "system_prompt: |\n  Prompt atualizado" in content
        assert "version: 2" in content

        # Remove o agente (delete_agent marca is_enabled=false no banco)
        await repo.delete_agent(ATLAS_OWNER_ID, ATLAS_ORGANIZATION_ID, agent_id, 2)

        # Conforme a issue de aceite: desativar ao remover. O profile YAML deve ser removido
        assert not os.path.exists(yaml_path)

    finally:
        if agent_id:
            pool = await database.pool()
            await pool.execute("delete from public.agents where id=$1", agent_id)

    await database.close()
