"""Contrato minimo para adaptadores de motores visuais.

Um motor so deve ser marcado como ativo depois de implementar e testar este
contrato. Os metodos sao intencionalmente pequenos para facilitar plugins.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class VisualEngine(ABC):
    engine_id = "base"
    supports_independent_deliverables = False

    @abstractmethod
    def validate_job(self, job: dict[str, Any]) -> None:
        """Valida as opcoes antes de iniciar qualquer processo."""

    @abstractmethod
    def build_command(self, job: dict[str, Any], root: Path, python_executable: str) -> list[str]:
        """Retorna o comando local que executa o job."""

    def capabilities(self) -> dict[str, Any]:
        return {
            "engine_id": self.engine_id,
            "independent_deliverables": self.supports_independent_deliverables,
        }
