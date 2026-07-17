import json
import logging
import os
import re
import tempfile
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


def dict_to_yaml(data: dict[str, Any]) -> str:
    lines: list[str] = []
    for k, v in data.items():
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", k):
            raise HermesProfileSyncError(f"Invalid profile field name: {k}")
        normalized = str(v) if isinstance(v, UUID) else v
        lines.append(f"{k}: {json.dumps(normalized, ensure_ascii=False)}")
    return "\n".join(lines) + "\n"


class HermesProfileSyncError(Exception):
    """Exceção para erros de sincronização de profile com o Hermes."""

    pass


class HermesProfileSync:
    def __init__(self, profiles_dir: str):
        self.profiles_dir = profiles_dir

    def sync_agent(self, agent_data: dict[str, Any]) -> str:
        """Gera e escreve o profile do agente para o filesystem do Hermes.

        Retorna o caminho do arquivo gerado.
        """
        if not self.profiles_dir:
            raise HermesProfileSyncError("HERMES_PROFILES_DIR is not configured")

        agent_id = agent_data.get("agent_id")
        if not agent_id:
            raise HermesProfileSyncError("Missing agent_id in sync data")

        # Garante a existência do diretório
        try:
            os.makedirs(self.profiles_dir, exist_ok=True)
        except Exception as exc:
            raise HermesProfileSyncError(f"Failed to create profiles directory: {exc}") from exc

        # Campos obrigatórios exigidos no perfil do Hermes
        required_fields = [
            "agent_id",
            "organization_id",
            "agent_version_id",
            "name",
            "model",
            "system_prompt",
            "skills",
            "workspace",
            "risk_level",
            "enabled",
            "version",
        ]
        for field in required_fields:
            if field not in agent_data:
                raise HermesProfileSyncError(
                    f"Missing required field '{field}' for profile generation"
                )

        yaml_content = dict_to_yaml(agent_data)
        version_id = agent_data["agent_version_id"]
        file_path = os.path.join(self.profiles_dir, f"{version_id}.yaml")

        temp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.profiles_dir,
                prefix=f".{agent_id}.",
                suffix=".tmp",
                delete=False,
            ) as f:
                temp_path = f.name
                f.write(yaml_content)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, file_path)
            logger.info(
                "Sincronização de profile concluída com sucesso",
                extra={"file_path": file_path, "agent_id": agent_id},
            )
        except Exception as exc:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
            raise HermesProfileSyncError(f"Failed to write profile file: {exc}") from exc

        return file_path

    def disable_agent(self, agent_id: UUID, version_ids: list[UUID] | None = None) -> None:
        """Marca o profile do agente como desabilitado ou o remove do Hermes."""
        if not self.profiles_dir:
            raise HermesProfileSyncError("HERMES_PROFILES_DIR is not configured")

        paths = [
            os.path.join(self.profiles_dir, f"{version_id}.yaml")
            for version_id in version_ids or []
        ]
        paths.append(os.path.join(self.profiles_dir, f"{agent_id}.yaml"))
        for file_path in paths:
            if not os.path.exists(file_path):
                continue
            try:
                # Conforme especificação: desativar ao remover
                # Podemos tanto apagar o arquivo quanto alterar enabled para false.
                # Para ser limpo e desativar com segurança, removemos o arquivo
                # de forma a impedir que o gateway execute runs com esse perfil.
                os.remove(file_path)
                logger.info(
                    "Profile do agente desativado/removido",
                    extra={"file_path": file_path, "agent_id": str(agent_id)},
                )
            except Exception as exc:
                raise HermesProfileSyncError(f"Failed to remove profile file: {exc}") from exc
