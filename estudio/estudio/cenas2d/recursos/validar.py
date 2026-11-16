"""
validar.py - valida e normaliza um RECURSO visual (personagem, objeto ou cenario) recebido como JSON.

Nada e executado: so se verifica estrutura, tipos, intervalos e limites de tamanho. Qualquer problema levanta
RecursoInvalido com a lista de mensagens (o motor entao usa um substituto e segue renderizando).
Formato (resumo):  veja o apendice do RELATORIO_M1_GENERICO.md  /  exemplos em exemplos/recursos_poc/.
"""
import math
import re

from . import svgpath

FORMATO = "m1-recurso/1"
TIPOS = ("personagem", "objeto", "cenario")
FORMAS = ("path", "poly", "rect", "ellipse", "line", "glow")
PROPS = ("rot", "tx", "ty", "sx", "sy", "op", "var")
LIM = dict(partes=160, formas=3000, anims=48, keys=600, dur=120.0, coord=1e5, caminho=400000, id=64)
ID_RE = re.compile(r"^[a-zA-Z0-9_\-\.]{1,64}$")
NOMES_COR = {"white": (255, 255, 255), "black": (0, 0, 0), "red": (255, 0, 0), "transparent": None, "none": None}


class RecursoInvalido(ValueError):
    def __init__(self, erros):
        self.erros = erros if isinstance(erros, list) else [erros]
        super().__init__("; ".join(self.erros[:6]) + (" ..." if len(self.erros) > 6 else ""))


def cor(v, paleta=None, erros=None, ctx=""):
    """'#rgb' '#rrggbb' '#rrggbbaa' '$nome' [r,g,b(,a)] 'none' -> (r,g,b,a) ou None"""
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip().lower()
        if s.startswith("$"):
            if paleta and s[1:] in paleta:
                return cor(paleta[s[1:]], None, erros, ctx)
            (erros if erros is not None else []).append(f"{ctx}: cor '{v}' nao esta na paleta")
            return (255, 0, 255, 255)
        if s in NOMES_COR:
            c = NOMES_COR[s]
            return None if c is None else c + (255,)
        m = re.fullmatch(r"#([0-9a-f]{3,8})", s)
        if m and len(m.group(1)) in (3, 4, 6, 8):
            h = m.group(1)
            if len(h) in (3, 4):
                h = "".join(ch * 2 for ch in h)
            vals = [int(h[i:i + 2], 16) for i in range(0, len(h), 2)]
            return tuple(vals + [255] * (4 - len(vals)))
    elif isinstance(v, (list, tuple)) and 3 <= len(v) <= 4 and all(isinstance(x, (int, float)) for x in v):
        vals = [int(max(0, min(255, x))) for x in v]
        return tuple(vals + [255] * (4 - len(vals)))
    (erros if erros is not None else []).append(f"{ctx}: cor invalida {str(v)[:30]}")
    return (255, 0, 255, 255)


def _num(v, ctx, erros, lo=-LIM["coord"], hi=LIM["coord"]):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < lo or v > hi:
        erros.append(f"{ctx}: numero invalido ({str(v)[:20]})")
        return 0.0
    return float(v)


def _par(v, ctx, erros):
    if not isinstance(v, (list, tuple)) or len(v) != 2:
        erros.append(f"{ctx}: esperado [x, y]")
        return (0.0, 0.0)
    return (_num(v[0], ctx, erros), _num(v[1], ctx, erros))


def _preenchimento(f, paleta, erros, ctx):
    if isinstance(f, dict):
        stops = f.get("g")
        if not isinstance(stops, list) or len(stops) < 2 or len(stops) > 8:
            erros.append(f"{ctx}: gradiente precisa de 2..8 paradas em 'g'")
            return None
        ps = []
        for s in stops:
            if not isinstance(s, (list, tuple)) or len(s) != 2:
                erros.append(f"{ctx}: parada de gradiente invalida")
                return None
            ps.append((_num(s[0], ctx, erros, 0.0, 1.0), cor(s[1], paleta, erros, ctx)))
        dr = f.get("dir", "v")
        if dr not in ("v", "h"):
            erros.append(f"{ctx}: dir deve ser 'v' ou 'h'")
            dr = "v"
        return {"g": sorted(ps, key=lambda p: p[0]), "dir": dr}
    return cor(f, paleta, erros, ctx)


def _forma(f, paleta, erros, ctx):
    if not isinstance(f, dict) or f.get("t") not in FORMAS:
        erros.append(f"{ctx}: forma invalida (t deve ser um de {FORMAS})")
        return None
    t = f["t"]
    o = {"t": t}
    if t == "path":
        d = f.get("d")
        if not isinstance(d, str) or not d.strip() or len(d) > LIM["caminho"]:
            erros.append(f"{ctx}: path sem 'd' valido")
            return None
        try:
            svgpath.parse(d)                      # valida a sintaxe agora (falha cedo)
        except svgpath.CaminhoInvalido as e:
            erros.append(f"{ctx}: {e}")
            return None
        o["d"] = d
    elif t in ("poly", "line"):
        pts = f.get("pts")
        if not isinstance(pts, list) or not (2 <= len(pts) <= 5000):
            erros.append(f"{ctx}: pts precisa de 2..5000 pontos")
            return None
        o["pts"] = [_par(p, ctx, erros) for p in pts]
        o["fechado"] = bool(f.get("fechado", t == "poly"))
    elif t == "rect":
        for k in ("x", "y", "w", "h"):
            o[k] = _num(f.get(k, 0), f"{ctx}.{k}", erros)
        o["r"] = _num(f.get("r", 0), f"{ctx}.r", erros, 0, LIM["coord"])
    elif t == "ellipse":
        o["cx"], o["cy"] = _num(f.get("cx", 0), ctx, erros), _num(f.get("cy", 0), ctx, erros)
        rx = f.get("rx", f.get("r", 0))
        o["rx"], o["ry"] = _num(rx, ctx, erros, 0), _num(f.get("ry", rx), ctx, erros, 0)
    elif t == "glow":
        o["cx"], o["cy"] = _num(f.get("cx", 0), ctx, erros), _num(f.get("cy", 0), ctx, erros)
        o["r"] = _num(f.get("r", 50), ctx, erros, 0.5)
        o["rx"] = _num(f.get("rx", o["r"]), ctx, erros, 0.5)
        o["ry"] = _num(f.get("ry", o["r"]), ctx, erros, 0.5)
        o["cor"] = cor(f.get("cor", "#ffffff"), paleta, erros, ctx) or (255, 255, 255, 255)
        o["a"] = _num(f.get("a", 1.0), ctx, erros, 0, 1)
        o["exp"] = _num(f.get("exp", 2.0), ctx, erros, 0.3, 8)
    if t != "glow":
        o["fill"] = _preenchimento(f.get("fill"), paleta, erros, ctx + ".fill") if "fill" in f else None
        o["stroke"] = cor(f.get("stroke"), paleta, erros, ctx + ".stroke")
        o["sw"] = _num(f.get("sw", 0 if o["stroke"] is None else 2), ctx + ".sw", erros, 0, 500)
        o["cap"] = bool(f.get("cap", True))
    o["op"] = _num(f.get("op", 1.0), ctx + ".op", erros, 0, 1)
    if f.get("clip") not in (None, "base"):
        erros.append(f"{ctx}: clip so aceita 'base'")
    o["clip"] = f.get("clip")
    if "m" in f:
        m = f["m"]
        if not isinstance(m, (list, tuple)) or len(m) != 6:
            erros.append(f"{ctx}: m deve ter 6 numeros")
        else:
            o["m"] = tuple(_num(x, ctx + ".m", erros) for x in m)
    return o


def _formas(lst, paleta, erros, ctx, cont):
    if not isinstance(lst, list):
        erros.append(f"{ctx}: 'formas' deve ser lista")
        return []
    out = []
    for i, f in enumerate(lst):
        cont[0] += 1
        if cont[0] > LIM["formas"]:
            erros.append("formas demais no recurso")
            break
        n = _forma(f, paleta, erros, f"{ctx}[{i}]")
        if n:
            out.append(n)
    return out


def _faixas(an, partes_ids, erros, ctx):
    fx = {}
    if not isinstance(an.get("faixas"), dict):
        erros.append(f"{ctx}: 'faixas' obrigatorio (dict)")
        return fx
    for pid, props in an["faixas"].items():
        if pid not in partes_ids:
            erros.append(f"{ctx}: faixa para parte inexistente '{pid}'")
            continue
        if not isinstance(props, dict):
            erros.append(f"{ctx}.{pid}: propriedades devem ser dict")
            continue
        fx[pid] = {}
        for pr, keys in props.items():
            if pr not in PROPS:
                erros.append(f"{ctx}.{pid}: propriedade '{pr}' desconhecida (use {PROPS})")
                continue
            if not isinstance(keys, list) or not (1 <= len(keys) <= LIM["keys"]):
                erros.append(f"{ctx}.{pid}.{pr}: 1..{LIM['keys']} keyframes")
                continue
            ks = []
            for k in keys:
                if not isinstance(k, (list, tuple)) or len(k) < 2:
                    erros.append(f"{ctx}.{pid}.{pr}: keyframe deve ser [t, valor, ease?]")
                    continue
                t = _num(k[0], ctx, erros, 0, LIM["dur"])
                if pr == "var":
                    v = str(k[1])[:40]
                else:
                    v = _num(k[1], ctx, erros)
                ks.append((t, v, str(k[2]) if len(k) > 2 and k[2] is not None else None))
            fx[pid][pr] = sorted(ks, key=lambda x: x[0])
    return fx


def validar_recurso(d):
    """-> (recurso_normalizado, avisos). Levanta RecursoInvalido se houver erros."""
    erros, avisos = [], []
    if not isinstance(d, dict):
        raise RecursoInvalido("o recurso precisa ser um objeto JSON")
    rid = d.get("id")
    if not isinstance(rid, str) or not ID_RE.match(rid):
        erros.append("'id' obrigatorio (letras, numeros, _ - .; ate 64)")
    tipo = d.get("tipo", "objeto")
    if tipo not in TIPOS:
        erros.append(f"'tipo' deve ser um de {TIPOS}")
    conhecidas = {"formato", "id", "tipo", "nome", "tags", "caixa", "base", "frente", "passo", "sombra", "ancoras",
                  "paleta", "partes", "pose_base", "animacoes", "luzes_por_parte", "slots", "camadas", "aliases",
                  "descricao", "autor", "versao"}
    for k in d:
        if k not in conhecidas:
            avisos.append(f"campo desconhecido ignorado: '{k}'")
    paleta = d.get("paleta") or {}
    if not isinstance(paleta, dict):
        erros.append("'paleta' deve ser dict")
        paleta = {}
    r = {"formato": FORMATO, "id": rid, "tipo": tipo, "nome": str(d.get("nome", rid))[:120],
         "tags": [str(t)[:30] for t in (d.get("tags") or [])][:20], "versao": int(d.get("versao", 1) or 1),
         "frente": d.get("frente", "direita"), "paleta": paleta}
    if r["frente"] not in ("direita", "esquerda"):
        erros.append("'frente' deve ser 'direita' ou 'esquerda'")
    cx = d.get("caixa")
    if not (isinstance(cx, (list, tuple)) and len(cx) == 4):
        erros.append("'caixa' obrigatoria: [x0, y0, x1, y1]")
        cx = [0, 0, 1, 1]
    r["caixa"] = tuple(_num(v, "caixa", erros) for v in cx)
    if r["caixa"][2] <= r["caixa"][0] or r["caixa"][3] <= r["caixa"][1]:
        erros.append("'caixa' invalida (x1>x0 e y1>y0)")
    r["base"] = _par(d.get("base", [(r["caixa"][0] + r["caixa"][2]) / 2, r["caixa"][3]]), "base", erros)
    r["passo"] = _num(d.get("passo", 0), "passo", erros, 0, 1e5)
    sb = d.get("sombra")
    r["sombra"] = None if not sb else {"rx": _num(sb.get("rx", 100), "sombra", erros, 1), "ry": _num(sb.get("ry", 14), "sombra", erros, 1),
                                       "y": _num(sb.get("y", r["base"][1]), "sombra", erros), "x": _num(sb.get("x", r["base"][0]), "sombra", erros),
                                       "a": _num(sb.get("a", 0.5), "sombra", erros, 0, 1)}
    r["ancoras"] = {}
    for k, v in (d.get("ancoras") or {}).items():
        if isinstance(v, (list, tuple)) and len(v) == 3 and isinstance(v[2], str):
            r["ancoras"][str(k)[:40]] = _par(v[:2], f"ancoras.{k}", erros) + (v[2],)       # (x, y, parte)
        else:
            r["ancoras"][str(k)[:40]] = _par(v, f"ancoras.{k}", erros)
    r["aliases"] = {str(k)[:40]: str(v)[:40] for k, v in (d.get("aliases") or {}).items()}
    cont = [0]
    # ---- partes (rig)
    partes, ids = [], set()
    plist = d.get("partes") or []
    if not isinstance(plist, list) or len(plist) > LIM["partes"]:
        erros.append(f"'partes' deve ser lista com ate {LIM['partes']} itens")
        plist = []
    for i, p in enumerate(plist):
        if not isinstance(p, dict) or not isinstance(p.get("id"), str) or not ID_RE.match(p["id"]):
            erros.append(f"partes[{i}]: 'id' invalido")
            continue
        if p["id"] in ids:
            erros.append(f"partes[{i}]: id duplicado '{p['id']}'")
            continue
        ids.add(p["id"])
        ctx = f"partes.{p['id']}"
        var = {}
        for vn, vf in (p.get("variantes") or {}).items():
            var[str(vn)[:40]] = _formas(vf, paleta, erros, f"{ctx}.variantes.{vn}", cont)
        partes.append({"id": p["id"], "pai": p.get("pai"), "pivo": _par(p.get("pivo", [0, 0]), ctx + ".pivo", erros),
                       "z": _num(p.get("z", i), ctx + ".z", erros), "formas": _formas(p.get("formas", []), paleta, erros, ctx, cont),
                       "variantes": var, "var_padrao": p.get("var_padrao"), "oculta": bool(p.get("oculta", False))})
    for p in partes:
        if p["pai"] is not None and p["pai"] not in ids:
            erros.append(f"parte '{p['id']}': pai '{p['pai']}' nao existe")
            p["pai"] = None
    # ciclos
    pai = {p["id"]: p["pai"] for p in partes}
    for pid in pai:
        seen, cur = set(), pid
        while cur is not None:
            if cur in seen:
                erros.append(f"ciclo na hierarquia em '{pid}'")
                pai[pid] = None
                break
            seen.add(cur)
            cur = pai.get(cur)
    r["partes"] = partes
    r["pose_base"] = {}
    for pid, pr in (d.get("pose_base") or {}).items():
        if pid in ids and isinstance(pr, dict):
            r["pose_base"][pid] = {k: (v if k == "var" else _num(v, f"pose_base.{pid}.{k}", erros)) for k, v in pr.items() if k in PROPS}
    # ---- animacoes
    r["animacoes"] = {}
    an = d.get("animacoes") or {}
    if not isinstance(an, dict) or len(an) > LIM["anims"]:
        erros.append(f"'animacoes' deve ser dict com ate {LIM['anims']} itens")
        an = {}
    for nome, a in an.items():
        if not isinstance(a, dict):
            erros.append(f"animacao '{nome}' invalida")
            continue
        dur = _num(a.get("dur", 1.0), f"animacoes.{nome}.dur", erros, 0.05, LIM["dur"])
        r["animacoes"][str(nome)[:40]] = {"dur": dur, "loop": bool(a.get("loop", False)),
                                          "faixas": _faixas(a, ids, erros, f"animacoes.{nome}")}
    r["luzes_por_parte"] = []
    for i, lp in enumerate(d.get("luzes_por_parte") or []):
        if isinstance(lp, dict) and lp.get("parte") in ids:
            r["luzes_por_parte"].append({"parte": lp["parte"], "cor": cor(lp.get("cor", "#ffffff"), paleta, erros, "luzes_por_parte") or (255, 255, 255, 255),
                                         "raio": _num(lp.get("raio", 200), "luzes_por_parte.raio", erros, 1), "int": _num(lp.get("int", 0.6), "luzes_por_parte.int", erros, 0, 3),
                                         "exp": _num(lp.get("exp", 1.8), "luzes_por_parte.exp", erros, 0.3, 8),
                                         "dx": _num(lp.get("dx", 0), "luzes_por_parte.dx", erros), "dy": _num(lp.get("dy", 0), "luzes_por_parte.dy", erros)})
        else:
            avisos.append(f"luzes_por_parte[{i}] ignorada (parte inexistente)")
    r["slots"] = {}
    for nome, sl in (d.get("slots") or {}).items():
        if isinstance(sl, dict) and sl.get("parte") in ids and isinstance(sl.get("caixa"), (list, tuple)) and len(sl["caixa"]) == 4:
            r["slots"][str(nome)[:40]] = {"parte": sl["parte"], "caixa": tuple(_num(v, "slots", erros) for v in sl["caixa"])}
    # ---- camadas (cenarios)
    r["camadas"] = []
    cl = d.get("camadas") or []
    if not isinstance(cl, list) or len(cl) > 40:
        erros.append("'camadas' deve ser lista (ate 40)")
        cl = []
    for i, c in enumerate(cl):
        if isinstance(c, dict):
            r["camadas"].append({"id": str(c.get("id", f"c{i}"))[:40], "k": _num(c.get("k", 0.5), "camadas.k", erros, 0, 3),
                                 "formas": _formas(c.get("formas", []), paleta, erros, f"camadas[{i}]", cont),
                                 "desfoque": _num(c.get("desfoque", 0), "camadas.desfoque", erros, 0, 40)})
    if tipo == "cenario" and not r["camadas"]:
        erros.append("cenario precisa de 'camadas'")
    if tipo != "cenario" and not partes:
        erros.append("personagem/objeto precisa de 'partes'")
    if erros:
        raise RecursoInvalido(erros)
    return r, avisos
