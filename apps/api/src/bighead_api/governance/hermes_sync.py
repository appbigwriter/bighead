import logging
import os
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


def dict_to_yaml(data: dict[str, Any]) -> str:
    lines = []
    for k, v in data.items():
        if isinstance(v, list):
            lines.append(f"{k}:")
            for item in v:
                lines.append(f"  - {item}")
        elif isinstance(v, dict):
            lines.append(f"{k}:")
            for sub_k, sub_v in v.items():
                lines.append(f"  {sub_k}: {sub_v}")
        elif v is None:
            lines.append(f"{k}: null")
        elif isinstance(v, bool):
            lines.append(f"{k}: {str(v).lower()}")
        elif isinstance(v, (int, float)):
            lines.append(f"{k}: {v}")
        elif isinstance(v, UUID):
            lines.append(f"{k}: {str(v)}")
        else:
            val_str = str(v)
            if "\n" in val_str:
                lines.append(f"{k}: |")
                for line in val_str.splitlines():
                    lines.append(f"  {line}")
            else:
                lines.append(f"{k}: {val_str}")
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
        file_path = os.path.join(self.profiles_dir, f"{agent_id}.yaml")

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(yaml_content)
            logger.info(
                "Sincronização de profile concluída com sucesso",
                extra={"file_path": file_path, "agent_id": agent_id},
            )
        except Exception as exc:
            raise HermesProfileSyncError(f"Failed to write profile file: {exc}") from exc

        return file_path

    def disable_agent(self, agent_id: UUID) -> None:
        """Marca o profile do agente como desabilitado ou o remove do Hermes."""
        if not self.profiles_dir:
            raise HermesProfileSyncError("HERMES_PROFILES_DIR is not configured")

        file_path = os.path.join(self.profiles_dir, f"{agent_id}.yaml")
        if os.path.exists(file_path):
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
