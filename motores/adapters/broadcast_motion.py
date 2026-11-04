from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from .broadcast_news import BroadcastNewsEngine
except ImportError:
    from motores.adapters.broadcast_news import BroadcastNewsEngine


class BroadcastMotionEngine(BroadcastNewsEngine):
    """Broadcast News com icones, diagramas e graficos animados sobre imagens."""

    engine_id = "broadcast_motion"

    def build_command(self, job: dict[str, Any], root: Path, python_executable: str) -> list[str]:
        command = super().build_command(job, root, python_executable)
        command[2] = str(root / "motores" / "broadcast_motion.py")
        return command

    def capabilities(self) -> dict[str, Any]:
        caps = super().capabilities()
        caps["visual_components"] = caps.get("visual_components", []) + [
            "animated_icons", "animated_diagrams", "counters", "bar_line_donut_charts", "media_backgrounds"]
        return caps
