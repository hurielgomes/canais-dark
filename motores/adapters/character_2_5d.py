from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from engine_interface import VisualEngine


DIRETORES_VALIDOS = {"myhub", "gemini", "local", "auto"}


def _diretor_configurado(root: Path) -> str:
    """le o provedor salvo pela interface (config.json -> m1_diretor_padrao) no momento de iniciar o job"""
    caminho = Path(root) / "config.json"
    try:
        valor = str(json.loads(caminho.read_text(encoding="utf-8-sig")).get("m1_diretor_padrao") or "auto").strip().lower()
    except (OSError, ValueError):
        return "auto"
    return valor if valor in DIRETORES_VALIDOS else "auto"


class Character25DEngine(VisualEngine):
    """Motor M1 (Cenas 2D em Camadas): personagens, objetos e cenarios da biblioteca montados por JSON."""
    engine_id = "character_2_5d"
    supports_independent_deliverables = True

    def validate_job(self, job: dict[str, Any]) -> None:
        canal = str(job.get("canal", ""))
        tema = str(job.get("tema", "")).strip()
        formatos = [x.strip() for x in str(job.get("formatos") or "").split(",") if x.strip()]
        if not canal or not tema:
            raise ValueError("Canal e tema sao obrigatorios.")
        if not formatos or any(x not in ("16x9", "9x16") for x in formatos):
            raise ValueError("O motor Personagem 2.5D (M1) aceita apenas os formatos 16x9 e 9x16.")

    def build_command(self, job: dict[str, Any], root: Path, python_executable: str) -> list[str]:
        self.validate_job(job)
        command = [python_executable, "-u", str(root / "criar_cenas2d.py"),
                   job["canal"], job["tema"], "--formatos", job["formatos"],
                   "--categoria", str(job.get("categoria") or "curiosidades")]
        if int(job.get("duracao") or 0):
            command += ["--duracao", str(int(job["duracao"]))]
        if job.get("entrega_format"):
            command += ["--entrega-format", str(job["entrega_format"])]
        if job.get("perfil"):
            command += ["--perfil", str(job["perfil"])]
        diretor = str(job.get("diretor") or _diretor_configurado(root)).strip().lower()
        if diretor not in DIRETORES_VALIDOS:
            raise ValueError(f"Diretor M1 invalido: {diretor}. Opcoes: {', '.join(sorted(DIRETORES_VALIDOS))}.")
        command += ["--diretor", diretor]
        if job.get("revisar"):
            command.append("--revisar")
        if job.get("simular"):
            command.append("--simular")
        relative_project = str(job.get("pasta") or "").strip()
        if relative_project:
            project_dir = (root / "projetos" / relative_project).resolve()
            projects_root = (root / "projetos").resolve()
            if projects_root not in project_dir.parents or not project_dir.is_dir():
                raise ValueError("A pasta salva para retomada nao existe ou esta fora de projetos/.")
            command += ["--projeto", str(project_dir)]
        return command
