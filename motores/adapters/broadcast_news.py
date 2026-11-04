from __future__ import annotations

from pathlib import Path
from typing import Any

from engine_interface import VisualEngine


class BroadcastNewsEngine(VisualEngine):
    """Motor jornalistico explicativo, com fatos consolidados e motion graphics locais."""

    engine_id = "broadcast_news"
    supports_independent_deliverables = True

    def validate_job(self, job: dict[str, Any]) -> None:
        canal = str(job.get("canal", "")).strip()
        tema = str(job.get("tema", "")).strip()
        formatos = [x.strip() for x in str(job.get("formatos") or "").split(",") if x.strip()]
        if not canal or not tema:
            raise ValueError("Canal e tema sao obrigatorios.")
        if not formatos or any(x not in ("16x9", "9x16") for x in formatos):
            raise ValueError("Broadcast News aceita apenas 16x9 e 9x16.")

    def build_command(self, job: dict[str, Any], root: Path, python_executable: str) -> list[str]:
        self.validate_job(job)
        command = [
            python_executable, "-u", str(root / "motores" / "broadcast_news.py"),
            job["canal"], job["tema"],
            "--categoria", str(job.get("categoria") or "noticias"),
            "--formatos", str(job.get("formatos") or "16x9"),
        ]
        if int(job.get("duracao") or 0):
            command += ["--duracao", str(int(job["duracao"]))]
        if job.get("entrega_format"):
            command += ["--entrega-format", str(job["entrega_format"])]
        if job.get("simular"):
            command.append("--simular")
        if job.get("revisar"):
            command.append("--revisar")
        relative_project = str(job.get("pasta") or "").strip()
        if relative_project:
            project_dir = (root / "projetos" / relative_project).resolve()
            projects_root = (root / "projetos").resolve()
            if projects_root not in project_dir.parents or not project_dir.is_dir():
                raise ValueError("A pasta salva para retomada nao existe ou esta fora de projetos/.")
            command += ["--projeto", str(project_dir)]
        return command

    def capabilities(self) -> dict[str, Any]:
        return {
            **super().capabilities(),
            "local_rendering": True,
            "requires_research_grounding": False,
            "uses_google_search": False,
            "factual_mode": "conhecimento consolidado do Gemini; nao declarar atualidade sem fonte fornecida",
            "visual_components": ["headlines", "data_cards", "timelines", "flows", "comparisons", "charts", "source_strips"],
        }
