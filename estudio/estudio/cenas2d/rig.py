"""
rig.py - interpreta um RECURSO validado (personagem/objeto/cenario) e o desenha/animar. SEM codigo por objeto:
tudo vem dos dados (partes, pivos, formas, animacoes).

Modelo
------
* PARTES em hierarquia (pai -> filho). Cada parte tem pivo (no espaco do recurso), z, formas e variantes.
* POSE = {parte: {rot, tx, ty, sx, sy, op, var}}. Vem de ANIMACOES (faixas de keyframes) com mistura entre clipes.
* Matriz da parte  =  matriz_do_pai . T(pivo+t) . R(rot) . S(sx,sy) . T(-pivo)   (espaco do recurso).
* Desenho vetorial com Pillow (supersampling): poligonos, tracos, gradientes, recorte pelo corpo ("clip":"base"),
  brilhos. Cada frame redesenha so a caixa ocupada pelo recurso.
"""
import math
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter

from ..comum.tween import EASES, clamp
from . import pintura as pt
from .recursos import svgpath
from .recursos.svgpath import IDENT, mmul, mpt, rotacao_graus, translacao

PADRAO = {"rot": 0.0, "tx": 0.0, "ty": 0.0, "sx": 1.0, "sy": 1.0, "op": 1.0}
ALIAS_GLOBAL = {"andar": "caminhar", "correr": "caminhar", "idle": "parado", "parar": "parado", "em_pe": "parado",
                "sentar": "sentado", "ligado": "ligada", "desligado": "desligada", "walk": "caminhar", "stand": "levantar"}


# =============================================================================== geometria das formas
def _rrect_pts(x, y, w, h, r):
    r = max(0.0, min(r, abs(w) / 2, abs(h) / 2))
    if r < 0.5:
        return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    pts = []
    for cx, cy, a0 in ((x + w - r, y + r, -90), (x + w - r, y + h - r, 0), (x + r, y + h - r, 90), (x + r, y + r, 180)):
        for k in range(0, 7):
            a = math.radians(a0 + 90 * k / 6)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def _ellipse_pts(cx, cy, rx, ry):
    n = max(24, min(96, int(max(rx, ry) / 2.5) + 20))
    return [(cx + rx * math.cos(2 * math.pi * k / n), cy + ry * math.sin(2 * math.pi * k / n)) for k in range(n)]


def compilar_forma(f):
    """forma validada -> dict com 'subs' (polilinhas no espaco do recurso)"""
    m = tuple(f.get("m", IDENT))
    t = f["t"]
    o = {k: v for k, v in f.items() if k not in ("d", "pts", "x", "y", "w", "h", "r", "cx", "cy", "rx", "ry", "m")}
    if t == "glow":
        cx, cy = mpt(m, f["cx"], f["cy"])
        o.update(cx=cx, cy=cy, rx=f["rx"], ry=f["ry"], r=f["r"], subs=[])
        return o
    if t == "path":
        subs = svgpath.parse(f["d"], m)
    elif t in ("poly", "line"):
        subs = [([mpt(m, x, y) for x, y in f["pts"]], bool(f.get("fechado", t == "poly")))]
    elif t == "rect":
        subs = [([mpt(m, x, y) for x, y in _rrect_pts(f["x"], f["y"], f["w"], f["h"], f.get("r", 0))], True)]
    else:   # ellipse
        subs = [([mpt(m, x, y) for x, y in _ellipse_pts(f["cx"], f["cy"], f["rx"], f["ry"])], True)]
    o["subs"] = subs
    return o


# =============================================================================== animacao
def _ease_fn(nome):
    return EASES.get(nome or "", None)


def _catmull(p0, p1, p2, p3, u):
    return 0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u + (-p0 + 3 * p1 - 3 * p2 + p3) * u ** 3)


def amostrar_faixa(keys, t, ciclico=False, dur=1.0, discreto=False):
    """valor da faixa de keyframes no tempo t. Catmull-Rom (suave) por padrao; 'ease' do key sobrescreve."""
    n = len(keys)
    if n == 1:
        return keys[0][1]
    if t <= keys[0][0] and not ciclico:
        return keys[0][1]
    if t >= keys[-1][0] and not ciclico:
        return keys[-1][1]
    i = 0
    while i < n - 2 and t >= keys[i + 1][0]:
        i += 1
    k0, k1 = keys[i], keys[i + 1]
    if discreto:
        return k0[1] if t < k1[0] else k1[1]
    seg = max(1e-6, k1[0] - k0[0])
    u = clamp((t - k0[0]) / seg)
    ez = _ease_fn(k0[2])
    if ez is not None:
        return k0[1] + (k1[1] - k0[1]) * ez(u)
    if k0[2] == "linear" or n < 3:
        return k0[1] + (k1[1] - k0[1]) * u
    # catmull-rom com vizinhos (ciclico: usa o outro lado do ciclo)
    def val(j):
        if 0 <= j < n:
            return keys[j][1]
        if ciclico:
            return keys[j % (n - 1)][1] if n > 1 else keys[0][1]
        return keys[0][1] if j < 0 else keys[-1][1]
    return _catmull(val(i - 1), k0[1], k1[1], val(i + 2), u)


class Rig:
    def __init__(self, rec):
        self.rec = rec
        self.id = rec["id"]
        self.partes = {p["id"]: p for p in rec["partes"]}
        self.pai = {p["id"]: p["pai"] for p in rec["partes"]}
        # ordem topologica (pais antes dos filhos)
        self.topo, vis = [], set()

        def visita(pid):
            if pid in vis:
                return
            if self.pai.get(pid):
                visita(self.pai[pid])
            vis.add(pid)
            self.topo.append(pid)
        for p in rec["partes"]:
            visita(p["id"])
        self.ordem_z = [p["id"] for p in sorted(rec["partes"], key=lambda p: p["z"])]
        self.comp = {}
        self.comp_var = {}
        for p in rec["partes"]:
            self.comp[p["id"]] = [compilar_forma(f) for f in p["formas"]]
            self.comp_var[p["id"]] = {vn: [compilar_forma(f) for f in fs] for vn, fs in p["variantes"].items()}
        self.camadas = [{"k": c["k"], "desfoque": c["desfoque"], "formas": [compilar_forma(f) for f in c["formas"]]} for c in rec["camadas"]]
        self.animacoes = rec["animacoes"]

    # ----------------------------------------------------------------- capacidades
    def capacidades(self):
        return sorted(self.animacoes)

    def resolver(self, nome):
        """nome de animacao pedido -> nome disponivel (aliases do recurso e globais) ou None"""
        if nome in self.animacoes:
            return nome
        al = self.rec.get("aliases", {})
        for cand in (al.get(nome), ALIAS_GLOBAL.get(nome)):
            if cand and cand in self.animacoes:
                return cand
        return None

    def duracao(self, nome):
        return self.animacoes[nome]["dur"]

    # ----------------------------------------------------------------- pose
    def pose_de(self, nome, t, vel=1.0):
        """pose (parcial) de uma animacao no tempo t (s) ja com loop/espera no fim"""
        if nome is None or nome not in self.animacoes:
            return {}
        a = self.animacoes[nome]
        tt = t * vel
        if a["loop"]:
            tt = tt % a["dur"]
        else:
            tt = min(max(tt, 0.0), a["dur"])
        out = {}
        for pid, props in a["faixas"].items():
            d = {}
            for pr, keys in props.items():
                d[pr] = amostrar_faixa(keys, tt, a["loop"], a["dur"], discreto=(pr == "var"))
            out[pid] = d
        return out

    def misturar(self, A, B, w):
        """interpola duas poses completas (transicao suave entre animacoes)"""
        out = {}
        for pid, a in A.items():
            b = B[pid]
            d = {k: a[k] + (b[k] - a[k]) * w for k in PADRAO}
            v = b.get("var") if w >= 0.5 else a.get("var")
            if v:
                d["var"] = v
            out[pid] = d
        return out

    def pose_final(self, camadas):
        """camadas = [(pose_parcial, peso)] misturadas sobre pose_base; devolve pose completa {parte:{...}}"""
        base = self.rec["pose_base"]
        res = {}
        for pid in self.partes:
            d = dict(PADRAO)
            d.update({k: v for k, v in base.get(pid, {}).items() if k != "var"})
            if "var" in base.get(pid, {}):
                d["var"] = base[pid]["var"]
            res[pid] = d
        for pose, w in camadas:
            if w <= 0 or not pose:
                continue
            for pid, props in pose.items():
                if pid not in res:
                    continue
                for k, v in props.items():
                    if k == "var":
                        if w >= 0.5:
                            res[pid]["var"] = v
                    else:
                        res[pid][k] = res[pid][k] + (v - res[pid][k]) * w
        return res

    # ----------------------------------------------------------------- matrizes
    def matrizes(self, pose):
        W, op = {}, {}
        for pid in self.topo:
            p = self.partes[pid]
            ps = pose.get(pid, PADRAO)
            px, py = p["pivo"]
            m = mmul(translacao(px + ps["tx"], py + ps["ty"]),
                     mmul(rotacao_graus(ps["rot"]), mmul((ps["sx"], 0.0, 0.0, ps["sy"], 0.0, 0.0), translacao(-px, -py))))
            par = self.pai.get(pid)
            W[pid] = mmul(W[par], m) if par else m
            op[pid] = ps["op"] * (op[par] if par else 1.0)
        return W, op

    def posicionar(self, pose, s, flip, pos_tela):
        """mapeia o espaco do recurso para a tela: base -> pos_tela, escala s, espelho"""
        bx, by = self.rec["base"]
        fx = -1.0 if flip else 1.0
        A = mmul(translacao(pos_tela[0], pos_tela[1]), mmul((fx * s, 0.0, 0.0, s, 0.0, 0.0), translacao(-bx, -by)))
        W, op = self.matrizes(pose)
        return Posicionado(self, pose, A, W, op, s)


class Posicionado:
    def __init__(self, rig, pose, A, W, op, s):
        self.rig, self.pose, self.A, self.W, self.op, self.s = rig, pose, A, W, op, s
        self.M = {pid: mmul(A, W[pid]) for pid in W}

    # ---------- pontos de referencia
    def ancora(self, nome):
        a = self.rig.rec["ancoras"].get(nome)
        if a is None:
            return None
        x, y = a[0], a[1]
        parte = a[2] if len(a) > 2 else None
        m = self.M[parte] if parte in self.M else self.A
        return mpt(m, x, y)

    def centro_parte(self, pid):
        p = self.rig.partes[pid]
        xs = ys = n = 0
        for f in self.rig.comp[pid]:
            for pts, _ in f["subs"]:
                for x, y in pts:
                    xs += x; ys += y; n += 1
        if not n:
            return mpt(self.M[pid], *p["pivo"])
        return mpt(self.M[pid], xs / n, ys / n)

    def regiao_slot(self, nome):
        sl = self.rig.rec["slots"].get(nome)
        if not sl:
            return None
        x, y, w, h = sl["caixa"]
        m = self.M[sl["parte"]]
        pts = [mpt(m, *q) for q in ((x, y), (x + w, y), (x + w, y + h), (x, y + h))]
        xs, ys = [q[0] for q in pts], [q[1] for q in pts]
        return (min(xs), min(ys), max(xs), max(ys))

    def luzes(self):
        out = []
        for lp in self.rig.rec["luzes_por_parte"]:
            pid = lp["parte"]
            inten = lp["int"] * self.op.get(pid, 1.0)
            if inten <= 0.01:
                continue
            cx, cy = self.centro_parte(pid)
            cx2, cy2 = mpt(self.A, 0, 0)
            out.append((cx + lp["dx"] * self.s, cy + lp["dy"] * self.s, lp["raio"] * self.s, lp["cor"][:3], inten, lp["exp"]))
        return out

    # ---------- desenho
    def desenhar(self, limite=None, ss=2, slots=None):
        """-> (RGBA, ox, oy) cobrindo so a area ocupada (limitada a `limite`=(x0,y0,x1,y1))"""
        rig = self.rig
        tf = []     # (pid, forma, subs_tela, op)
        xs, ys = [], []
        for pid in rig.ordem_z:
            p = rig.partes[pid]
            if p["oculta"] or self.op[pid] <= 0.004:
                continue
            var = self.pose[pid].get("var") or p["var_padrao"]
            formas = list(rig.comp[pid]) + list(rig.comp_var[pid].get(var, [])) if var else list(rig.comp[pid])
            M = self.M[pid]
            for f in formas:
                if f["t"] == "glow":
                    cx, cy = mpt(M, f["cx"], f["cy"])
                    rx, ry = f["rx"] * self.s, f["ry"] * self.s
                    xs += [cx - rx, cx + rx]; ys += [cy - ry, cy + ry]
                    tf.append((pid, f, [(cx, cy, rx, ry)], self.op[pid]))
                    continue
                subs = [([mpt(M, x, y) for x, y in pts], fe) for pts, fe in f["subs"]]
                for pts, _ in subs:
                    for x, y in pts:
                        xs.append(x); ys.append(y)
                tf.append((pid, f, subs, self.op[pid]))
        reg = {}
        if slots:
            for nome, conteudo in slots.items():
                r = self.regiao_slot(nome)
                if r:
                    reg[self.rig.rec["slots"][nome]["parte"]] = (conteudo, r)
                    xs += [r[0], r[2]]; ys += [r[1], r[3]]
        if not xs:
            return None
        marg = 6 + max((f.get("sw", 0) or 0) for _, f, _, _ in tf) * self.s if tf else 6
        x0, y0, x1, y1 = min(xs) - marg, min(ys) - marg, max(xs) + marg, max(ys) + marg
        if limite:
            x0, y0, x1, y1 = max(x0, limite[0]), max(y0, limite[1]), min(x1, limite[2]), min(y1, limite[3])
        ox, oy = int(math.floor(x0)), int(math.floor(y0))
        W_, H_ = int(math.ceil(x1)) - ox, int(math.ceil(y1)) - oy
        if W_ < 2 or H_ < 2:
            return None
        if W_ * H_ > 6_500_000:
            ss = 1
        if reg:
            return self._com_slots(ox, oy, ss, tf, reg, W_, H_)
        main = Image.new("RGBA", (W_ * ss, H_ * ss), (0, 0, 0, 0))
        base_cache = {}
        for pid, f, subs, op in tf:
            self._desenha_forma(main, ox, oy, ss, pid, f, subs, op, base_cache)
        return (main.reduce(ss) if ss > 1 else main), ox, oy

    def _com_slots(self, ox, oy, ss, tf, reg, W_, H_):
        # respeita o z: partes ate o alvo, depois o conteudo do slot, depois as partes seguintes
        img = Image.new("RGBA", (W_ * ss, H_ * ss), (0, 0, 0, 0))
        base_cache = {}
        feito = set()
        for idx, (pid, f, subs, op) in enumerate(tf):
            self._desenha_forma(img, ox, oy, ss, pid, f, subs, op, base_cache)
            prox = tf[idx + 1][0] if idx + 1 < len(tf) else None
            if pid in reg and prox != pid and pid not in feito:
                feito.add(pid)
                conteudo, (rx0, ry0, rx1, ry1) = reg[pid]
                cw, ch = int((rx1 - rx0) * ss), int((ry1 - ry0) * ss)
                if cw > 2 and ch > 2:
                    c = conteudo.resize((cw, ch), Image.BILINEAR) if conteudo.size != (cw, ch) else conteudo
                    opp = self.op.get(pid, 1.0)
                    if opp < 0.999:
                        c = c.copy()
                        c.putalpha(c.getchannel("A").point(lambda v, k=opp: int(v * k)))
                    img.alpha_composite(c, dest=(int((rx0 - ox) * ss), int((ry0 - oy) * ss)))
        return (img.reduce(ss) if ss > 1 else img), ox, oy

    def _desenha_forma(self, main, ox, oy, ss, pid, f, subs, op, base_cache):
        t = f["t"]
        if t == "glow":
            cx, cy, rx, ry = subs[0]
            a = f["a"] * f["op"] * op
            if a <= 0.004:
                return
            r = int(max(4, rx * ss))
            sp = pt.brilho_sprite(r, f["cor"][:3], a * (f["cor"][3] / 255.0), f["exp"], ry=int(max(4, ry * ss)))
            self._cola(main, sp, int((cx - ox) * ss - sp.width / 2), int((cy - oy) * ss - sp.height / 2))
            return
        fill, stroke = f.get("fill"), f.get("stroke")
        eop = f["op"] * op
        if eop <= 0.004:
            return
        S = [([((x - ox) * ss, (y - oy) * ss) for x, y in pts], fe) for pts, fe in subs]
        solido = isinstance(fill, tuple) and fill[3] == 255 and eop >= 0.999 and f.get("clip") != "base"
        sw = max(0.0, (f.get("sw", 0) or 0) * self.s * ss)
        if solido and (not stroke or stroke[3] == 255):
            d = ImageDraw.Draw(main)
            for pts, fe in S:
                if len(pts) >= 3:
                    d.polygon(pts, fill=fill)
            if stroke and sw > 0:
                self._tracos(d, S, stroke, sw, f)
            return
        # caminho geral: camada temporaria da bbox
        allp = [p for pts, _ in S for p in pts]
        if not allp:
            return
        bx0, by0 = max(0, int(min(p[0] for p in allp) - sw - 2)), max(0, int(min(p[1] for p in allp) - sw - 2))
        bx1, by1 = min(main.width, int(max(p[0] for p in allp) + sw + 3)), min(main.height, int(max(p[1] for p in allp) + sw + 3))
        if bx1 <= bx0 or by1 <= by0:
            return
        bw, bh = bx1 - bx0, by1 - by0
        loc = [([(x - bx0, y - by0) for x, y in pts], fe) for pts, fe in S]
        layer = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        if fill is not None:
            m = Image.new("L", (bw, bh), 0)
            dm = ImageDraw.Draw(m)
            for pts, fe in loc:
                if len(pts) >= 3:
                    dm.polygon(pts, fill=255)
            if isinstance(fill, dict):
                cor = _grad_rgba(bw, bh, fill)
                cor.putalpha(ImageChops_mul(cor.getchannel("A"), m))
                layer.alpha_composite(cor)
            else:
                col = Image.new("RGBA", (bw, bh), fill[:3] + (0,))
                col.putalpha(m.point(lambda v, a=fill[3]: v * a // 255))
                layer.alpha_composite(col)
        if stroke and sw > 0:
            tl = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
            self._tracos(ImageDraw.Draw(tl), loc, stroke, sw, f)
            layer.alpha_composite(tl)
        if f.get("clip") == "base":
            bm = self._mascara_base(pid, ox, oy, ss, bx0, by0, bw, bh)
            if bm is not None:
                layer.putalpha(ImageChops_mul(layer.getchannel("A"), bm))
        if eop < 0.999:
            layer.putalpha(layer.getchannel("A").point(lambda v, k=eop: int(v * k)))
        self._cola(main, layer, bx0, by0)

    def _mascara_base(self, pid, ox, oy, ss, bx0, by0, bw, bh):
        rig = self.rig
        formas = rig.comp[pid]
        if not formas:
            return None
        base = formas[0]
        M = self.M[pid]
        m = Image.new("L", (bw, bh), 0)
        d = ImageDraw.Draw(m)
        for pts, _ in base["subs"]:
            q = [((mpt(M, x, y)[0] - ox) * ss - bx0, (mpt(M, x, y)[1] - oy) * ss - by0) for x, y in pts]
            if len(q) >= 3:
                d.polygon(q, fill=255)
        return m

    @staticmethod
    def _tracos(d, subs, cor, sw, f):
        w = max(1, int(round(sw)))
        for pts, fechado in subs:
            if len(pts) < 2:
                continue
            seq = pts + [pts[0]] if fechado else pts
            d.line(seq, fill=cor, width=w, joint="curve")
            if f.get("cap", True) and not fechado and w > 2:
                r = w / 2.0
                for x, y in (pts[0], pts[-1]):
                    d.ellipse([x - r, y - r, x + r, y + r], fill=cor)

    @staticmethod
    def _cola(dst, src, x, y):
        W, H = dst.size
        ax0, ay0, ax1, ay1 = max(0, x), max(0, y), min(W, x + src.width), min(H, y + src.height)
        if ax1 <= ax0 or ay1 <= ay0:
            return
        dst.alpha_composite(src.crop((ax0 - x, ay0 - y, ax1 - x, ay1 - y)), dest=(ax0, ay0))


def ImageChops_mul(a, b):
    from PIL import ImageChops
    return ImageChops.multiply(a, b)


def _grad_rgba(w, h, g):
    stops = g["g"]
    horiz = g["dir"] == "h"
    rgb = pt.degradado(w, h, [(p, c[:3]) for p, c in stops if c is not None] or [(0, (0, 0, 0)), (1, (0, 0, 0))], horizontal=horiz)
    al = pt.degradado(w, h, [(p, (c[3],) * 3) for p, c in stops if c is not None] or [(0, (255,) * 3), (1, (255,) * 3)], horizontal=horiz).convert("L")
    out = rgb.convert("RGBA")
    out.putalpha(al)
    return out


# =============================================================================== cenarios (camadas com parallax)
def camadas_cenario(rig, w, h, esc, foco, ss=1, limite_px=7000):
    """desenha as camadas de um recurso 'cenario' -> [(k, desfoque, RGBA, x, y)]; esc = px por unidade, foco = ponto do
    cenario que fica no centro do quadro. Cada camada e recortada ao conteudo (economiza memoria)."""
    fx, fy = foco
    A = mmul(translacao(w / 2.0, h / 2.0), mmul((esc, 0.0, 0.0, esc, 0.0, 0.0), translacao(-fx, -fy)))
    out = []
    pos = Posicionado(rig, {}, A, {}, {}, esc)
    for c in rig.camadas:
        xs, ys, tf = [], [], []
        for f in c["formas"]:
            if f["t"] == "glow":
                cx, cy = mpt(A, f["cx"], f["cy"])
                rx, ry = f["rx"] * esc, f["ry"] * esc
                xs += [cx - rx, cx + rx]; ys += [cy - ry, cy + ry]
                tf.append((f, [(cx, cy, rx, ry)]))
                continue
            subs = [([mpt(A, x, y) for x, y in pts], fe) for pts, fe in f["subs"]]
            for pts, _ in subs:
                xs += [p[0] for p in pts]; ys += [p[1] for p in pts]
            tf.append((f, subs))
        if not xs:
            continue
        marg = 8 + c["desfoque"] * 3
        x0, y0 = max(-marg - 400, min(xs) - marg), max(-marg - 400, min(ys) - marg)
        x1, y1 = min(limite_px, max(xs) + marg), min(limite_px, max(ys) + marg)
        ox, oy = int(math.floor(x0)), int(math.floor(y0))
        Wc, Hc = int(math.ceil(x1)) - ox, int(math.ceil(y1)) - oy
        if Wc < 2 or Hc < 2:
            continue
        img = Image.new("RGBA", (Wc * ss, Hc * ss), (0, 0, 0, 0))
        for f, subs in tf:
            pos._desenha_forma(img, ox, oy, ss, "_cen", f, subs, 1.0, {})
        if ss > 1:
            img = img.reduce(ss)
        if c["desfoque"] > 0:
            img = img.filter(ImageFilter.GaussianBlur(c["desfoque"]))
        out.append((c["k"], c["desfoque"], img, ox, oy))
    return out
