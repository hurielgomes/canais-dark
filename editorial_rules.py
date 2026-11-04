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


def ensure_closing_question(script: dict, category_id: str | None, topic: str = "", tone: str = "") -> dict:
    """Garante CTA contextual e preserva a pergunta especifica escrita pela IA."""
    scenes = script.get("cenas") if isinstance(script, dict) else None
    if not isinstance(scenes, list) or not scenes:
        return script
    last = scenes[-1]
    if not isinstance(last, dict):
        return script
    narration = str(last.get("narracao") or "").strip()
    tail = narration[-420:].lower()
    invite_markers = ("coment", "conta aqui", "conta nos", "conta aí", "deixe sua", "deixa sua", "escreva nos", "sua opinião", "sua escolha", "qual outro", "o que faria", "e você")
    has_question = "?" in tail
    has_invite = any(marker in tail for marker in invite_markers)
    if not (has_question and has_invite):
        question = closing_question(category_id, topic, tone)
        if question.lower() not in narration.lower():
            separator = " " if narration.endswith((".", "!", "?")) else ". "
            narration = (narration + separator + question).strip()
            last["narracao"] = narration
            tail = narration[-420:].lower()

    # Guarda a pergunta que o roteiro já escreveu quando ela vem acompanhada
    # de convite para comentar. Isso mantém a CTA específica ao tema.
    questions = re.findall(r"[^.!?]*\?", narration)
    if questions and has_invite:
        chosen = questions[-1].strip()
        chosen = re.sub(r"^[-—\s]+", "", chosen)
        script["pergunta_final"] = chosen or closing_question(category_id, topic, tone)
    else:
        script["pergunta_final"] = closing_question(category_id, topic, tone)
    return script

