from __future__ import annotations
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def get_category(category_id: str | None) -> dict:
    try:
        data = json.loads((ROOT / "motores" / "categorias.json").read_text(encoding="utf-8"))
        return next((c for c in data.get("categories", []) if c.get("id") == (category_id or "curiosidades")), {})
    except (OSError, json.JSONDecodeError):
        return {}

def closing_question(category_id: str | None, topic: str = "", tone: str = "") -> str:
    category = get_category(category_id)
    profile = category.get("editorial_profile", {})
    tone_text = (tone or "").lower()
    if category_id == "what_if":
        return "E você, o que faria se isso acontecesse com você? Conta sua escolha nos comentários."
    if category_id == "humor" or any(x in tone_text for x in ("humor", "engraçado", "descontra", "leve e divertido")):
        return "E você, faria diferente ou também ia acabar nessa confusão? Conta aí nos comentários."
    if category_id in ("noticias", "politica_institucional"):
        return "Qual ponto desse assunto você considera mais importante? Comente sua opinião, com respeito, aqui embaixo."
    return str(profile.get("closing_question") or "Qual parte desse assunto mais chamou sua atenção? Conta nos comentários.")

import re
import unicodedata


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9 ]", "", s).strip()


def _dedupe_questions(narration: str) -> str:
    """Remove perguntas repetidas, mantendo a primeira ocorrência."""
    parts = re.findall(r"[^.!?]*[.!?]+|[^.!?]+$", narration)
    seen, out = set(), []
    for p in parts:
        key = _norm(p)
        if p.strip().endswith("?") and key in seen:
            continue
        if p.strip().endswith("?"):
            seen.add(key)
        out.append(p)
    return re.sub(r"\s+", " ", "".join(out)).strip()


INVITE_MARKERS = (
    "coment", "conta aqui", "conta nos", "conta ai", "deixe sua", "deixa sua",
    "escreva nos", "sua opiniao", "sua escolha", "qual outro", "o que faria", "e voce",
)


_CTAS_GENERICOS = (
    "já conhecia",
    "o que mais te surpreendeu",
    "conta nos comentários",
    "conta aqui nos comentários",
)


def _remove_ctas_genericos(texto: str) -> str:
    """Remove frases de CTA genérico, mantendo o restante da narração."""
    marcadores = [_norm(m) for m in _CTAS_GENERICOS]
    partes = re.findall(r"[^.!?]+[.!?]*", texto)
    mantidas = [p.strip() for p in partes if not any(m in _norm(p) for m in marcadores)]
    return " ".join(mantidas).strip()


def ensure_closing_question(script: dict, category_id: str | None, topic: str = "", tone: str = "") -> dict:
    """Preserva a pergunta escrita pela IA; só usa o fallback da categoria se não houver nenhuma."""
    scenes = script.get("cenas") if isinstance(script, dict) else None
    if not isinstance(scenes, list) or not scenes:
        return script
    last = scenes[-1]
    if not isinstance(last, dict):
        return script

    narration = _dedupe_questions(str(last.get("narracao") or "").strip())
    narration = _remove_ctas_genericos(narration) or narration

    questions = re.findall(r"[^.!?]*\?", narration)
    if not questions:
        question = closing_question(category_id, topic, tone)
        sep = " " if narration.endswith((".", "!", "?")) else ". "
        narration = (narration + sep + question).strip()
        questions = [question]

    last["narracao"] = narration
    chosen = re.sub(r"^[-—\s]+", "", questions[-1].strip())
    script["pergunta_final"] = chosen or closing_question(category_id, topic, tone)
    return script


def closing_instruction(category_id: str | None) -> str:
    profile = get_category(category_id).get("editorial_profile", {})
    return profile.get("closing_instruction") or INSTRUCAO_FECHAMENTO_PADRAO
