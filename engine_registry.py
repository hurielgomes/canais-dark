"""Catalogo de motores visuais e capacidades da Fabrica de Videos."""
from __future__ import annotations

import json
import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CATALOG_FILE = ROOT / "motores" / "catalogo.json"
CATEGORIES_FILE = ROOT / "motores" / "categorias.json"
THUMBNAILS_FILE = ROOT / "motores" / "thumbnail_templates.json"


def _read(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def list_engines():
    data = _read(CATALOG_FILE, {"engines": []})
    return data.get("engines", [])


def get_engine(engine_id: str):
    return next((e for e in list_engines() if e.get("id") == engine_id), None)


def get_adapter(engine_id: str):
    engine = get_engine(engine_id)
    if not engine or engine.get("status") != "active":
        return None
    adapter_path = engine.get("adapter")
    if not adapter_path or ":" not in adapter_path:
        return None
    module_name, class_name = adapter_path.split(":", 1)
    try:
        module = importlib.import_module(module_name)
        adapter_class = getattr(module, class_name)
        return adapter_class()
    except (ImportError, AttributeError, TypeError):
        return None


def is_engine_executable(engine_id: str) -> bool:
    return get_adapter(engine_id) is not None


def list_categories():
    data = _read(CATEGORIES_FILE, {"categories": []})
    return data.get("categories", [])


def list_thumbnail_templates():
    data = _read(THUMBNAILS_FILE, {"templates": []})
    return data.get("templates", [])


def get_health():
    engines = list_engines()
    return {
        "total": len(engines),
        "active": sum(1 for x in engines if x.get("status") == "active"),
        "planned": sum(1 for x in engines if x.get("status") == "planned"),
    }
