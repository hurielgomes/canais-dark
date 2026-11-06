"""Adapters dos estilos animados (criar_animado.py): whiteboard e telejornal animado."""
from pathlib import Path

from engine_interface import VisualEngine


class _AnimadoBase(VisualEngine):
    ESTILO = ""
    FORMATOS = ("16x9", "9x16")

    def validate_job(self, job):
        erros = []
        if not str(job.get("canal") or "").strip():
            erros.append("canal nao informado")
        if not str(job.get("tema") or "").strip():
            erros.append("tema nao informado")
        fmt = self._formato(job)
        if fmt not in self.FORMATOS:
            erros.append(f"formato invalido: {fmt}")
        return erros

    @staticmethod
    def _formato(job):
        return job.get("entrega_format") or (str(job.get("formatos") or "16x9").split(",")[0].strip())

    def build_command(self, job, root, python_executable):
        root = Path(root)
        cmd = [python_executable, "-u", str(root / "criar_animado.py"),
               job["canal"], job["tema"],
               "--estilo", self.ESTILO,
               "--categoria", job.get("categoria") or "curiosidades",
               "--formatos", self._formato(job)]
        if job.get("duracao"):
            cmd += ["--duracao", str(int(job["duracao"]))]
        if job.get("revisar"):
            cmd.append("--revisar")
        if job.get("simular"):
            cmd.append("--simular")
        return cmd

    def capabilities(self):
        return {"formats": list(self.FORMATOS), "supports_independent_deliverables": True,
                "estilo": self.ESTILO}


class WhiteboardEngine(_AnimadoBase):
    ESTILO = "whiteboard"


class TelejornalAnimadoEngine(_AnimadoBase):
    ESTILO = "telejornal"
