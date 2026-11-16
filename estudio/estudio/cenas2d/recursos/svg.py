"""
svg.py - converte um arquivo SVG em um RECURSO (dict) do M1.

* Cada <g id="..."> filho direto da raiz (ou com data-parte="1") vira uma PARTE (articulavel por JSON de apoio).
  Formas soltas na raiz vao para a parte "base".
* Suporta: path, rect, circle, ellipse, line, polyline, polygon, transform, fill/stroke/opacity (atributo ou style),
  linearGradient (conversao para gradiente vertical/horizontal), viewBox.
* Seguranca: rejeita DOCTYPE/ENTITY (ataques de expansao), <script>, <foreignObject>, <image>, <use> externo e
  referencias a arquivos; limita tamanho e numero de nos. Nada e executado.
* Um JSON "sidecar" opcional completa o que o SVG nao tem (hierarquia, pivos, animacoes, ancoras, slots).
"""
import re
import xml.etree.ElementTree as ET

from . import svgpath
from .validar import RecursoInvalido

MAX_BYTES = 2_000_000
MAX_NOS = 6000
PROIBIDOS = ("script", "foreignobject", "image", "iframe", "audio", "video", "animate", "set", "animatetransform")


def _tag(el):
    t = el.tag
    return t.split("}", 1)[1].lower() if isinstance(t, str) and "}" in t else str(t).lower()


def _estilo(el):
    d = {}
    for k in ("fill", "stroke", "stroke-width", "opacity", "fill-opacity", "stroke-opacity", "stroke-linecap"):
        if el.get(k) is not None:
            d[k] = el.get(k)
    st = el.get("style")
    if st:
        for item in st.split(";"):
            if ":" in item:
                k, v = item.split(":", 1)
                d[k.strip().lower()] = v.strip()
    return d


def _f(v, padrao=0.0):
    if v is None:
        return padrao
    m = re.match(r"\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)", str(v))
    return float(m.group(1)) if m else padrao


def _gradientes(raiz):
    out = {}
    for el in raiz.iter():
        if _tag(el) == "lineargradient" and el.get("id"):
            out[el.get("id")] = el
    res = {}

    def resolve(gid, prof=0):
        el = out.get(gid)
        if el is None or prof > 4:
            return None
        stops = [s for s in el if _tag(s) == "stop"]
        if not stops:
            href = (el.get("{http://www.w3.org/1999/xlink}href") or el.get("href") or "")
            if href.startswith("#"):
                return resolve(href[1:], prof + 1)
            return None
        ps = []
        for s in stops:
            e = s.get("offset", "0")
            off = _f(e) / 100.0 if str(e).strip().endswith("%") else _f(e)
            st = _estilo(s)
            c = s.get("stop-color") or st.get("stop-color") or "#000"
            ps.append([max(0.0, min(1.0, off)), c])
        x1, y1, x2, y2 = (_f(el.get(k), dv) for k, dv in (("x1", 0), ("y1", 0), ("x2", 1), ("y2", 0)))
        dr = "h" if abs(x2 - x1) >= abs(y2 - y1) else "v"
        rev = (x2 < x1) if dr == "h" else (y2 < y1)
        if rev:
            ps = [[1 - p[0], p[1]] for p in reversed(ps)]
        return {"g": ps, "dir": dr}

    for gid in out:
        g = resolve(gid)
        if g:
            res[gid] = g
    return res


def _resolve_cor(v, grads, padrao):
    if v is None:
        return padrao
    v = v.strip()
    if v.lower() == "none":
        return None
    m = re.fullmatch(r"url\(#([^)]+)\)", v)
    if m:
        return grads.get(m.group(1), "#808080")
    if v.lower() == "currentcolor":
        return "#000000"
    mm = re.fullmatch(r"rgb\((\d+),\s*(\d+),\s*(\d+)\)", v.lower())
    if mm:
        return [int(mm.group(i)) for i in (1, 2, 3)]
    return v


def _forma_de(el, m, est, grads):
    t = _tag(el)
    fill = _resolve_cor(est.get("fill"), grads, "#000000")
    stroke = _resolve_cor(est.get("stroke"), grads, None)
    op = _f(est.get("opacity"), 1.0)
    fo = _f(est.get("fill-opacity"), 1.0)
    so = _f(est.get("stroke-opacity"), 1.0)
    sw = _f(est.get("stroke-width"), 1.0) if stroke else 0.0
    base = {"fill": fill, "stroke": stroke, "sw": sw, "op": max(0.0, min(1.0, op * (fo if fill else so)))}
    if m != svgpath.IDENT:
        base["m"] = list(m)
    if t == "path" and el.get("d"):
        return dict(base, t="path", d=el.get("d"))
    if t == "rect":
        return dict(base, t="rect", x=_f(el.get("x")), y=_f(el.get("y")), w=_f(el.get("width")), h=_f(el.get("height")), r=_f(el.get("rx"), _f(el.get("ry")))
                    )
    if t == "circle":
        return dict(base, t="ellipse", cx=_f(el.get("cx")), cy=_f(el.get("cy")), rx=_f(el.get("r")), ry=_f(el.get("r")))
    if t == "ellipse":
        return dict(base, t="ellipse", cx=_f(el.get("cx")), cy=_f(el.get("cy")), rx=_f(el.get("rx")), ry=_f(el.get("ry")))
    if t == "line":
        return dict(base, t="line", pts=[[_f(el.get("x1")), _f(el.get("y1"))], [_f(el.get("x2")), _f(el.get("y2"))]], fill=None)
    if t in ("polyline", "polygon"):
        nums = [float(x) for x in re.findall(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", el.get("points", ""))]
        pts = [[nums[i], nums[i + 1]] for i in range(0, len(nums) - 1, 2)]
        if len(pts) >= 2:
            return dict(base, t="poly" if t == "polygon" else "line", pts=pts, fechado=(t == "polygon"))
    return None


def _bbox(formas):
    xs, ys = [], []
    for f in formas:
        try:
            if f["t"] == "path":
                for pts, _ in svgpath.parse(f["d"], tuple(f.get("m", svgpath.IDENT))):
                    xs += [p[0] for p in pts]; ys += [p[1] for p in pts]
            elif f["t"] in ("poly", "line"):
                m = tuple(f.get("m", svgpath.IDENT))
                for p in f["pts"]:
                    q = svgpath.mpt(m, p[0], p[1]); xs.append(q[0]); ys.append(q[1])
            elif f["t"] == "rect":
                xs += [f["x"], f["x"] + f["w"]]; ys += [f["y"], f["y"] + f["h"]]
            elif f["t"] == "ellipse":
                xs += [f["cx"] - f["rx"], f["cx"] + f["rx"]]; ys += [f["cy"] - f["ry"], f["cy"] + f["ry"]]
        except svgpath.CaminhoInvalido:
            pass
    return (min(xs), min(ys), max(xs), max(ys)) if xs else (0, 0, 1, 1)


def importar_svg(texto, rid, tipo="objeto", sidecar=None):
    """texto: conteudo do SVG (str ou bytes). Retorna dict de recurso (ainda nao validado) + lista de avisos."""
    avisos = []
    if isinstance(texto, bytes):
        if len(texto) > MAX_BYTES:
            raise RecursoInvalido("SVG grande demais")
        texto = texto.decode("utf-8", "replace")
    if len(texto) > MAX_BYTES:
        raise RecursoInvalido("SVG grande demais")
    low = texto.lower()
    if "<!doctype" in low or "<!entity" in low:
        raise RecursoInvalido("SVG com DOCTYPE/ENTITY e rejeitado (seguranca)")
    try:
        raiz = ET.fromstring(texto)
    except ET.ParseError as e:
        raise RecursoInvalido(f"SVG mal formado: {e}")
    nos = 0
    for el in raiz.iter():
        nos += 1
        if nos > MAX_NOS:
            raise RecursoInvalido("SVG com nos demais")
        tg = _tag(el)
        if tg in PROIBIDOS:
            raise RecursoInvalido(f"elemento <{tg}> nao e permitido")
        for k, v in el.attrib.items():
            if k.lower().endswith("href") and not str(v).startswith("#"):
                raise RecursoInvalido("referencias externas (href) nao sao permitidas")
            if k.lower().startswith("on"):
                raise RecursoInvalido("atributos de evento nao sao permitidos")
        if tg in ("style", "use", "text", "mask", "clippath", "filter", "pattern", "symbol"):
            avisos.append(f"<{tg}> nao suportado (ignorado)")
    grads = _gradientes(raiz)
    vb = raiz.get("viewBox")
    if vb:
        v = [float(x) for x in re.split(r"[\s,]+", vb.strip())]
        caixa = [v[0], v[1], v[0] + v[2], v[1] + v[3]]
    else:
        caixa = [0, 0, _f(raiz.get("width"), 100), _f(raiz.get("height"), 100)]
    partes, soltas = [], []

    def coleta(el, m, est, destino, nivel_parte):
        tg = _tag(el)
        if tg in ("defs", "lineargradient", "radialgradient", "title", "desc", "metadata", "style"):
            return
        m2 = svgpath.mmul(m, svgpath.parse_transform(el.get("transform")))
        e2 = dict(est)
        e2.update(_estilo(el))
        if tg == "g":
            for ch in el:
                coleta(ch, m2, e2, destino, nivel_parte)
            return
        f = _forma_de(el, m2, e2, grads)
        if f:
            destino.append(f)

    for ch in raiz:
        tg = _tag(ch)
        if tg in ("defs", "lineargradient", "radialgradient", "title", "desc", "metadata", "style"):
            continue
        if tg == "g" and ch.get("id"):
            fs = []
            m0 = svgpath.parse_transform(ch.get("transform"))
            est0 = _estilo(ch)
            for sub in ch:
                coleta(sub, m0, est0, fs, 1)
            if fs:
                x0, y0, x1, y1 = _bbox(fs)
                partes.append({"id": ch.get("id"), "pivo": [(x0 + x1) / 2, (y0 + y1) / 2], "z": len(partes), "formas": fs})
        else:
            coleta(ch, svgpath.IDENT, {}, soltas, 0)
    if soltas:
        x0, y0, x1, y1 = _bbox(soltas)
        partes.insert(0, {"id": "base", "pivo": [(x0 + x1) / 2, (y0 + y1) / 2], "z": -1, "formas": soltas})
        for i, p in enumerate(partes):
            p["z"] = i
    rec = {"formato": "m1-recurso/1", "id": rid, "tipo": tipo, "caixa": caixa, "partes": partes}
    # ---- sidecar: complementa (hierarquia, pivos, animacoes...)
    if sidecar:
        sc = dict(sidecar)
        ov = sc.pop("partes", {}) or {}
        if isinstance(ov, list):
            ov = {p.get("id"): p for p in ov if isinstance(p, dict)}
        ids = {p["id"] for p in partes}
        for pid, o in ov.items():
            if pid not in ids:
                avisos.append(f"sidecar: parte '{pid}' nao existe no SVG")
                continue
            for p in partes:
                if p["id"] == pid:
                    p.update({k: v for k, v in o.items() if k != "id"})
        for pn in sc.pop("partes_novas", []) or []:
            if isinstance(pn, dict):
                partes.append(pn)
        rec.update({k: v for k, v in sc.items() if k not in ("formato", "partes")})
        rec["id"] = rid
    return rec, avisos
