import os
import shutil
import tempfile
from uuid import uuid4

import pytest
from bighead_api.governance.hermes_sync import (
    HermesProfileSync,
    HermesProfileSyncError,
    dict_to_yaml,
)


@pytest.fixture
def temp_profiles_dir():
    dir_path = tempfile.mkdtemp()
    yield dir_path
    shutil.rmtree(dir_path)


def test_dict_to_yaml_serialization():
    data = {
        "name": "Test Agent",
        "enabled": True,
        "version": 1,
        "skills": ["skill_1", "skill_2"],
        "prompt": "Linha 1\nLinha 2",
    }
    yaml_str = dict_to_yaml(data)
    assert 'name: "Test Agent"' in yaml_str
    assert "enabled: true" in yaml_str
    assert "version: 1" in yaml_str
    assert 'skills: ["skill_1", "skill_2"]' in yaml_str
    assert 'prompt: "Linha 1\\nLinha 2"' in yaml_str


def test_dict_to_yaml_quotes_structure_like_strings():
    yaml_str = dict_to_yaml({"system_prompt": "safe: false\nskills: [admin]"})
    assert 'system_prompt: "safe: false\\nskills: [admin]"' in yaml_str


def test_sync_agent_success(temp_profiles_dir):
    sync = HermesProfileSync(profiles_dir=temp_profiles_dir)
    agent_id = uuid4()
    org_id = uuid4()
    version_id = uuid4()

    agent_data = {
        "agent_id": agent_id,
        "organization_id": org_id,
        "agent_version_id": version_id,
        "name": "Raven Test",
        "model": "gpt-4",
        "system_prompt": "You are a sales agent.",
        "skills": ["query_knowledge_base"],
        "workspace": "sales-workspace",
        "risk_level": "medium",
        "enabled": True,
        "version": 2,
    }

    file_path = sync.sync_agent(agent_data)
    assert os.path.exists(file_path)
    assert file_path.endswith(f"{version_id}.yaml")

    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    assert f'agent_id: "{agent_id}"' in content
    assert f'organization_id: "{org_id}"' in content
    assert f'agent_version_id: "{version_id}"' in content
    assert 'name: "Raven Test"' in content
    assert "enabled: true" in content
    assert "version: 2" in content


def test_sync_agent_missing_fields_raises_error(temp_profiles_dir):
    sync = HermesProfileSync(profiles_dir=temp_profiles_dir)
    agent_data = {
        "agent_id": uuid4(),
        "name": "Incomplete Agent",
        # faltando os outros campos obrigatórios
    }

    with pytest.raises(HermesProfileSyncError) as exc_info:
        sync.sync_agent(agent_data)
    assert "Missing required field" in str(exc_info.value)


def test_disable_agent_success(temp_profiles_dir):
    sync = HermesProfileSync(profiles_dir=temp_profiles_dir)
    agent_id = uuid4()

    # Cria o arquivo manualmente primeiro
    version_id = uuid4()
    file_path = os.path.join(temp_profiles_dir, f"{version_id}.yaml")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("enabled: true")
    assert os.path.exists(file_path)

    sync.disable_agent(agent_id, [version_id])
    assert not os.path.exists(file_path)
