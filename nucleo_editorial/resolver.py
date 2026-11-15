"""Resolucao de perfil narrativo por canal, categoria e tema."""
import json
import unicodedata
import re
from functools import lru_cache
from pathlib import Path


_ARQ = Path(__file__).with_name("perfis_narrativos.json")


class PerfilInvalido(ValueError):
    pass


@lru_cache(maxsize=1)
def _dados():
    with open(_ARQ, encoding="utf-8") as f:
        return json.load(f)


def _norm(txt):
    txt = unicodedata.normalize("NFKD", str(txt or "").lower())
    return "".join(c for c in txt if not unicodedata.combining(c))


def listar_perfis():
    return {pid: {"id": pid, **p} for pid, p in _dados()["perfis"].items()}


def obter_perfil(perfil_id):
    p = _dados()["perfis"].get(perfil_id)
    if p is None:
        raise PerfilInvalido(f"perfil desconhecido: {perfil_id}")
    return {"id": perfil_id, **p}


def mapa_categoria(categoria):
    cats = _dados()["categorias"]
    return cats.get(categoria or "", cats["_padrao"])


def _config(canal):
    cfg = (canal or {}).get("nucleo_editorial") or {}
    return cfg if isinstance(cfg, dict) else {}


def canal_usa_nucleo(canal):
    return bool(_config(canal).get("ativo"))


def _permitido(pid, cfg):
    if pid in (cfg.get("perfis_bloqueados") or []):
        return False
    permitidos = cfg.get("perfis_permitidos") or []
    return not permitidos or pid in permitidos


def _tem_sinal(sinal, tema_n):
    return re.search(r"\b" + re.escape(_norm(sinal)) + r"\b", tema_n) is not None


def recomendar_perfis(canal, categoria, tema, limite=3):
    """Lista ordenada de {perfil, pontos, motivos} respeitando o canal.

    Sinal explícito no tema pesa mais que o padrão da categoria.
    Desempate: mais sinais no tema > padrão da categoria > ordem do JSON.
    """
    cfg = _config(canal)
    mapa = mapa_categoria(categoria)
    tema_n = _norm(tema)
    resultado = []
    for ordem, pid in enumerate(_dados()["perfis"]):
        if not _permitido(pid, cfg):
            continue
        p, motivos = 0, []
        eh_padrao = pid == mapa["padrao"]
        if eh_padrao:
            p += 2; motivos.append(f"padrão da categoria '{categoria}'")
        elif pid in mapa["compativeis"]:
            p += 1; motivos.append(f"compatível com a categoria '{categoria}'")
        hits = [s for s in _dados()["sinais_tema"].get(pid, []) if _tem_sinal(s, tema_n)]
        if hits:
            p += 3 * len(hits); motivos.append("sinais no tema: " + ", ".join(hits))
        if p:
            resultado.append((p, len(hits), eh_padrao, -ordem, pid, motivos))
    resultado.sort(reverse=True)
    return [{"perfil": pid, "pontos": p, "motivos": m}
            for p, _, _, _, pid, m in resultado[:limite]]


def resolver_perfil(canal, categoria, tema, perfil_manual=None):
    """Retorna {perfil, origem, justificativa, modo}.

    Ordem: manual do job > perfil_padrao do canal > recomendacao > padrao da categoria.
    Bloqueios/permitidos do canal sempre vencem.
    """
    if perfil_manual:
        obter_perfil(perfil_manual)  # valida id
    if not canal_usa_nucleo(canal):
        return {"perfil": None, "origem": "legado", "modo": "legado",
                "justificativa": "canal sem nucleo_editorial.ativo; comportamento antigo mantido"}

    cfg = _config(canal)
    avisos = []
    for origem, pid in (("manual", perfil_manual), ("canal", cfg.get("perfil_padrao"))):
        if not pid:
            continue
        obter_perfil(pid)
        if _permitido(pid, cfg):
            just = f"perfil '{pid}' definido por {origem}"
            return {"perfil": pid, "origem": origem, "modo": "nucleo",
                    "justificativa": "; ".join(avisos + [just])}
        avisos.append(f"perfil '{pid}' ({origem}) não permitido pelo canal")

    recs = recomendar_perfis(canal, categoria, tema, limite=1)
    if recs:
        r = recs[0]
        return {"perfil": r["perfil"], "origem": "recomendacao", "modo": "nucleo",
                "justificativa": "; ".join(avisos + r["motivos"])}

    padrao = mapa_categoria(categoria)["padrao"]
    return {"perfil": padrao, "origem": "categoria", "modo": "nucleo",
            "justificativa": "; ".join(avisos + ["nenhum perfil permitido pontuou; usado padrão da categoria"])}
