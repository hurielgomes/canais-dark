"""
cena_generica.py - modelo "generica": monta uma cena inteira a partir de JSON, SEM codigo por objeto.

    {"modelo": "generica", "duracao": 7.0,
     "cenario":  {"ref": "savana", "enq": {"9x16": {"esc": 1.5, "foco": [1700, 675]}, "16x9": {...}}, "ambiente": {"cor": "#2a1030", "forca": 0.2}},
     "elementos": [ {"id": "tigre", "ref": "tigre", "altura": {"9x16": 0.22, "16x9": 0.5}, "pos": {"9x16": [0.4, 0.8], "16x9": [0.3, 0.84]},
                     "mover": [{"t": 0, "para": [...]}, {"t": 6, "para": [...]}],
                     "linha_do_tempo": [{"t": 0, "anim": "parado"}, {"t": 0.6, "anim": "caminhar", "sincronizar": true}]} ],
     "camera": {"seguir": {"elemento": "tigre", "fator": 0.95}, "zoom": [{"t": 0, "v": 1.0}, {"t": 6, "v": 1.05}]},
     "luzes": [...], "hud": {...}, "legenda": [...], "destaques": [...]}

Um recurso pode vir de:  "ref" (biblioteca) | "def" (JSON inline) | "arquivo" (.json/.svg).  Recurso invalido => substituto + aviso
(o video segue sendo renderizado). Animacao inexistente => alias/fallback + aviso (usa so o que o recurso tem).
"""
import math
import sys

from PIL import Image, ImageFilter

from ..comum import hud
from ..comum.tween import EASES, clamp, lerp, tw
from .camadas import Mundo, Sprite
from .cenas import CenaBase
from .pintura import Lona
from .recursos.biblioteca import Biblioteca
from .recursos.svgpath import mpt
from .recursos.validar import RecursoInvalido, validar_recurso
from .rig import Rig, camadas_cenario

SUBSTITUTO = {"formato": "m1-recurso/1", "id": "_substituto", "tipo": "objeto", "nome": "recurso ausente", "caixa": [0, 0, 200, 260], "base": [100, 260],
              "partes": [{"id": "caixa", "pivo": [100, 130], "formas": [
                  {"t": "rect", "x": 10, "y": 10, "w": 180, "h": 240, "r": 16, "fill": "#ffffff", "op": 0.10, "stroke": "#ff5a5a", "sw": 6},
                  {"t": "line", "pts": [[30, 30], [170, 230]], "stroke": "#ff5a5a", "sw": 6}, {"t": "line", "pts": [[170, 30], [30, 230]], "stroke": "#ff5a5a", "sw": 6}]}]}


def _ease(nome):
    return EASES.get(nome or "in_out", EASES["in_out"])


class Elemento:
    pass


class CenaGenerica(CenaBase):
    USA_BIB = True

    def __init__(self, cena, w, h, formato, bib=None):
        self.bib = bib or Biblioteca("/tmp/_m1_bib_temp")
        self.avisos = {}
        super().__init__(cena, w, h, formato)

    # ------------------------------------------------------------------ utilidades
    def aviso(self, chave, msg):
        if chave not in self.avisos:
            self.avisos[chave] = msg
            self.bib.problemas.append(msg)
            print(f"aviso: {msg}", file=sys.stderr)

    def pf(self, v, padrao=None):
        """valor por formato: {"9x16": a, "16x9": b} ou valor unico"""
        if isinstance(v, dict) and ("9x16" in v or "16x9" in v):
            return v.get(self.formato, v.get("9x16" if self.formato == "16x9" else "16x9", padrao))
        return padrao if v is None else v

    def recurso(self, spec, tipo=None):
        """spec -> Rig. 'ref' | 'def' | 'arquivo'. Nunca levanta: devolve substituto + aviso em caso de falha."""
        try:
            if isinstance(spec, str):
                spec = {"ref": spec}
            if "def" in spec:
                r = self.bib.registrar(spec["def"], tipo=tipo)
                return self.bib.rig(r.id)
            if "arquivo" in spec:
                r = self.bib.registrar(spec["arquivo"], tipo=tipo)
                return self.bib.rig(r.id)
            return self.bib.rig(spec["ref"])
        except (KeyError, RecursoInvalido, ValueError, OSError) as e:
            self.aviso(f"rec:{spec!r}"[:80], f"recurso {spec if isinstance(spec, str) else list(spec.values())[0]!s:.60} indisponivel ({e}); usando substituto")
            rec, _ = validar_recurso(dict(SUBSTITUTO))
            return Rig(rec)

    # ------------------------------------------------------------------ construcao
    def construir(self):
        w, h, u = self.w, self.h, self.u
        c = self.c
        # --- cenario
        self.camadas_cen, self.ambiente = [], None
        self.base_rgb = tuple((c.get("tema") or {}).get("base_rgb", (8, 10, 20)))
        cen = c.get("cenario")
        if cen:
            rig = self.recurso(cen, "cenario")
            if rig.rec["tipo"] == "cenario":
                cx0, cy0, cx1, cy1 = rig.rec["caixa"]
                enq = self.pf(cen.get("enq"), {}) or {}
                esc = enq.get("esc", h / max(1.0, cy1 - cy0))
                foco = enq.get("foco", [(cx0 + cx1) / 2, (cy0 + cy1) / 2])
                for k, desf, img, x, y in camadas_cenario(rig, w, h, esc, foco, ss=1):
                    self.camadas_cen.append((k, 0, Sprite(img, x, y, recortar=True)))
            amb = cen.get("ambiente")
            if amb:
                from .recursos.validar import cor as _cor
                cc = _cor(amb.get("cor", "#000000")) or (0, 0, 0, 255)
                self.ambiente = (cc[:3], float(amb.get("forca", 0.2)))
        # --- elementos
        self.els, self.por_id = [], {}
        dt = 1.0 / 30.0
        for i, spec in enumerate(c.get("elementos", [])):
            el = Elemento()
            el.id = spec.get("id", f"el{i}")
            el.spec = spec
            el.rig = self.recurso(spec, "personagem")
            rec = el.rig.rec
            c0, c1, c2, c3 = rec["caixa"]
            alt = self.pf(spec.get("altura"), 0.3)
            el.s = float(self.pf(spec["escala"])) * u if "escala" in spec else alt * h / max(1.0, (c3 - c1))
            el.k = float(spec.get("k", 1.0))
            el.z = float(spec.get("z", i))
            olhar = self.pf(spec.get("olhar"), rec["frente"])
            el.flip = (olhar != rec["frente"])
            el.sombra = bool(spec.get("sombra", True)) and rec.get("sombra")
            el.ancorar = spec.get("ancorar")
            el.slots = spec.get("slots") or {}
            # posicao (px do mundo) por keyframes
            pos = self.pf(spec.get("pos"), [0.5, 0.8])
            mv = spec.get("mover") or []
            el.keys = []
            for kf in mv:
                pp = self.pf(kf.get("para"), pos)
                el.keys.append((float(kf["t"]), pp[0] * w, pp[1] * h, kf.get("ease", "in_out")))
            if not el.keys:
                el.keys = [(0.0, pos[0] * w, pos[1] * h, "linear")]
            # linha do tempo de animacoes (nomes resolvidos com aliases/fallback)
            tl = []
            for e in sorted(spec.get("linha_do_tempo") or [{"t": 0, "anim": "parado"}], key=lambda e: e["t"]):
                pedido = e.get("anim")
                nome = el.rig.resolver(pedido) if pedido else None
                implicito = not spec.get("linha_do_tempo") and not el.rig.capacidades()      # objeto estatico sem timeline: nada a avisar
                if pedido and nome is None and not implicito:
                    fb = el.rig.resolver("parado")
                    self.aviso(f"anim:{el.id}:{pedido}", f"'{el.id}' nao tem a animacao '{pedido}' (disponiveis: {', '.join(el.rig.capacidades()) or 'nenhuma'}); usando {fb or 'pose base'}")
                    nome = fb
                tl.append({"t": float(e["t"]), "anim": nome, "vel": float(e.get("vel", 1.0)), "mix": float(e.get("mix", 0.25)),
                           "sync": bool(e.get("sincronizar", False)), "olhar": e.get("olhar")})
            el.tl = tl
            # distancia acumulada (sincroniza o ciclo de andar com o deslocamento: sem "patinar")
            n = int(self.dur / dt) + 2
            el.dist = [0.0]
            px, py = self.pos_el(el, 0.0)
            for j in range(1, n):
                qx, qy = self.pos_el(el, j * dt)
                el.dist.append(el.dist[-1] + math.hypot(qx - px, qy - py))
                px, py = qx, qy
            for e in tl:
                e["d0"] = self.dist_el(el, e["t"])
            self.els.append(el)
            self.por_id[el.id] = el
        self.els_ordem = sorted(self.els, key=lambda e: (e.ancorar is not None, e.k, e.z))
        # filhos de slot (recursos dentro de outros recursos)
        for el in self.els:
            for nome, sl in el.slots.items():
                sl["_rig"] = self.recurso(sl, "personagem")

    def pos_el(self, el, t):
        ks = el.keys
        if t <= ks[0][0] or len(ks) == 1:
            return ks[0][1], ks[0][2]
        for i in range(len(ks) - 1):
            if t < ks[i + 1][0]:
                u = _ease(ks[i][3])(clamp((t - ks[i][0]) / max(1e-6, ks[i + 1][0] - ks[i][0])))
                return lerp(ks[i][1], ks[i + 1][1], u), lerp(ks[i][2], ks[i + 1][2], u)
        return ks[-1][1], ks[-1][2]

    def dist_el(self, el, t):
        f = t * 30.0
        i = int(f)
        if i >= len(el.dist) - 1:
            return el.dist[-1]
        return lerp(el.dist[i], el.dist[i + 1], f - i)

    # ------------------------------------------------------------------ animacao
    def pose_el(self, el, t, rig=None, tl=None):
        rig = rig or el.rig
        tl = tl or el.tl
        i = 0
        for j, e in enumerate(tl):
            if e["t"] <= t:
                i = j
        cur = tl[i]

        def local(e):
            if e["anim"] is None:
                return 0.0
            if e["sync"] and rig.rec["passo"] > 0:
                ciclos = (self.dist_el(el, t) - e["d0"]) / (rig.rec["passo"] * el.s)
                return ciclos * rig.duracao(e["anim"])
            return (t - e["t"]) * e["vel"]
        Pc = rig.pose_final([(rig.pose_de(cur["anim"], local(cur)), 1.0)])
        if i > 0 and cur["mix"] > 0:
            wgt = clamp((t - cur["t"]) / cur["mix"])
            if wgt < 1.0:
                prev = tl[i - 1]
                Pp = rig.pose_final([(rig.pose_de(prev["anim"], self._local_prev(el, rig, prev, t)), 1.0)])
                return rig.misturar(Pp, Pc, wgt)
        return Pc

    def _local_prev(self, el, rig, e, t):
        if e["anim"] is None:
            return 0.0
        if e["sync"] and rig.rec["passo"] > 0:
            return (self.dist_el(el, t) - e["d0"]) / (rig.rec["passo"] * el.s) * rig.duracao(e["anim"])
        return (t - e["t"]) * e["vel"]

    def flip_el(self, el, t):
        f = el.flip
        for e in el.tl:
            if e["t"] <= t and e["olhar"]:
                f = (e["olhar"] != el.rig.rec["frente"])
        return f

    # ------------------------------------------------------------------ quadro
    def camera_em(self, t):
        cam = self.c.get("camera") or {}
        u = self.u
        pan = [0.0, 0.0]
        sg = cam.get("seguir")
        if sg and sg.get("elemento") in self.por_id:
            el = self.por_id[sg["elemento"]]
            x, y = self.pos_el(el, t)
            x0, y0 = self.pos_el(el, 0.0)
            f = float(sg.get("fator", 0.9))
            pan = [(x - x0) * f, (y - y0) * float(sg.get("fator_y", 0.0))]
        for kf in self._lista(cam.get("pan")):
            pass
        zoom = 1.0
        zs = self._lista(cam.get("zoom"))
        if zs:
            zoom = self._interp(zs, t, "v")
        pk = self._lista(cam.get("pan"))
        if pk:
            pan[0] += self._interp(pk, t, "x") * u
            pan[1] += self._interp(pk, t, "y") * u
        ent = 0.05 * (1 - tw(t, 0, 0.5, "out_cubic"))
        return pan, zoom + ent

    @staticmethod
    def _lista(v):
        return v if isinstance(v, list) else []

    def _interp(self, ks, t, campo):
        ks = sorted(ks, key=lambda k: k["t"])
        if t <= ks[0]["t"]:
            return ks[0].get(campo, 0.0)
        for i in range(len(ks) - 1):
            if t < ks[i + 1]["t"]:
                u = _ease(ks[i].get("ease"))(clamp((t - ks[i]["t"]) / max(1e-6, ks[i + 1]["t"] - ks[i]["t"])))
                return lerp(ks[i].get(campo, 0.0), ks[i + 1].get(campo, 0.0), u)
        return ks[-1].get(campo, 0.0)

    def sombra_sprite(self, el, pos):
        sb = el.rig.rec["sombra"]
        cx, cy = mpt(pos.A, sb["x"], sb["y"])
        rx, ry = sb["rx"] * el.s, max(4.0, sb["ry"] * el.s)
        W, H = int(rx * 2 + 60), int(ry * 2 + 60)
        L = Lona(W, H, 1)
        L.elipse(W / 2, H / 2, rx, ry, fill=(0, 0, 0, int(255 * sb["a"])))
        img = L.pronto().filter(ImageFilter.GaussianBlur(max(3.0, ry * 0.55)))
        return Sprite(img, int(cx - W / 2), int(cy - H / 2), recortar=False)

    def render_filho(self, el, nome, sl, pos, t):
        reg = pos.regiao_slot(nome)
        if not reg:
            return None
        rw, rh = int(reg[2] - reg[0]), int(reg[3] - reg[1])
        if rw < 4 or rh < 4:
            return None
        rig = sl["_rig"]
        c0, c1, c2, c3 = rig.rec["caixa"]
        s = float(sl.get("altura", 0.7)) * rh / max(1.0, (c3 - c1))
        tl = []
        for e in sorted(sl.get("linha_do_tempo") or [{"t": 0, "anim": "parado"}], key=lambda e: e["t"]):
            nm = rig.resolver(e.get("anim")) or rig.resolver("parado")
            tl.append({"t": float(e["t"]), "anim": nm, "vel": float(e.get("vel", 1.0)), "mix": float(e.get("mix", 0.25)), "sync": bool(e.get("sincronizar", False)), "olhar": e.get("olhar"), "d0": 0.0})
        # deslocamento horizontal do filho dentro da tela (px do slot)
        pose = self._pose_filho(rig, tl, t, s, sl, rw)
        mv = sl.get("mover")
        fx0 = 0.5
        if mv:
            ks = [(float(k["t"]), k["para"][0]) for k in mv]
            fx0 = ks[0][1] if t <= ks[0][0] else ks[-1][1]
            for i in range(len(ks) - 1):
                if ks[i][0] <= t < ks[i + 1][0]:
                    fx0 = lerp(ks[i][1], ks[i + 1][1], clamp((t - ks[i][0]) / (ks[i + 1][0] - ks[i][0])))
        olhar = sl.get("olhar", rig.rec["frente"])
        flip = olhar != rig.rec["frente"]
        sp = rig.posicionar(pose, s, flip, (rw * fx0, rh * float(sl.get("base_y", 0.9))))
        res = sp.desenhar(limite=(0, 0, rw, rh), ss=2)
        out = Image.new("RGBA", (rw, rh), (0, 0, 0, 0))
        if res:
            img, ox, oy = res
            out.alpha_composite(img, dest=(ox, oy)) if ox >= 0 and oy >= 0 else out.paste(img, (ox, oy), img)
        return out

    def _pose_filho(self, rig, tl, t, s, sl, rw):
        mv = sl.get("mover") or []
        def x_em(tt):
            if not mv:
                return 0.5
            ks = [(float(k["t"]), k["para"][0]) for k in mv]
            if tt <= ks[0][0]:
                return ks[0][1]
            for i in range(len(ks) - 1):
                if tt < ks[i + 1][0]:
                    return lerp(ks[i][1], ks[i + 1][1], clamp((tt - ks[i][0]) / (ks[i + 1][0] - ks[i][0])))
            return ks[-1][1]
        def local(e, tt):
            if e["anim"] is None:
                return 0.0
            if e.get("sync") and rig.rec["passo"] > 0:
                return abs(x_em(tt) - x_em(e["t"])) * rw / (rig.rec["passo"] * s) * rig.duracao(e["anim"])
            return (tt - e["t"]) * e["vel"]
        i = 0
        for j, e in enumerate(tl):
            if e["t"] <= t:
                i = j
        e = tl[i]
        Pc = rig.pose_final([(rig.pose_de(e["anim"], local(e, t)), 1.0)])
        if i > 0 and e["mix"] > 0 and (t - e["t"]) < e["mix"]:
            p = tl[i - 1]
            Pp = rig.pose_final([(rig.pose_de(p["anim"], local(p, t)), 1.0)])
            return rig.misturar(Pp, Pc, clamp((t - e["t"]) / e["mix"]))
        return Pc

    def _pose_simples(self, rig, tl, t):
        i = 0
        for j, e in enumerate(tl):
            if e["t"] <= t:
                i = j
        e = tl[i]
        Pc = rig.pose_final([(rig.pose_de(e["anim"], (t - e["t"]) * e["vel"]), 1.0)])
        if i > 0 and e["mix"] > 0 and (t - e["t"]) < e["mix"]:
            p = tl[i - 1]
            Pp = rig.pose_final([(rig.pose_de(p["anim"], (t - p["t"]) * p["vel"]), 1.0)])
            return rig.misturar(Pp, Pc, clamp((t - e["t"]) / e["mix"]))
        return Pc

    def mundo(self, t):
        w, h, u = self.w, self.h, self.u
        m = Mundo(w, h, base_rgb=self.base_rgb)
        pan, zoom = self.camera_em(t)
        m.camera(pan=(pan[0], pan[1]), zoom=zoom)
        itens = []                              # (k, ordem, sprite)
        for k, o, sp in self.camadas_cen:
            itens.append((k, -1000 + o, sp))
        pos_cache, luzes = {}, []
        lim = (-w * 1.2, -h * 0.6, w * 2.2, h * 1.6)
        for el in self.els_ordem:
            x, y = self.pos_el(el, t)
            if el.ancorar:
                alvo = pos_cache.get(el.ancorar.get("em"))
                a = alvo.ancora(el.ancorar.get("ancora", "chao")) if alvo else None
                if a:
                    x, y = a
                    if el.ancorar.get("dx") or el.ancorar.get("dy"):
                        x, y = x + el.ancorar.get("dx", 0) * u, y + el.ancorar.get("dy", 0) * u
            pose = self.pose_el(el, t)
            esc_ent = 1.0
            ent = el.spec.get("entrada")        # {"tipo": "pop|esq|dir|subir", "t": 0.2, "dur": 0.55}: entrada animada do elemento
            if ent:
                t0 = float(ent.get("t", 0.0))
                if t < t0:
                    continue
                pe = tw(t, t0, float(ent.get("dur", 0.55)), "out_back")
                tipo_e = ent.get("tipo", "pop")
                if tipo_e == "pop":
                    esc_ent = 0.5 + 0.5 * pe
                elif tipo_e == "esq":
                    x -= (1 - pe) * 0.45 * w
                elif tipo_e == "dir":
                    x += (1 - pe) * 0.45 * w
                else:
                    y += (1 - pe) * 0.22 * h
            pos = el.rig.posicionar(pose, el.s * esc_ent, self.flip_el(el, t), (x, y))
            halo = (self.c.get("tema") or {}).get("halo", 1.0)      # tema claro reduz/elimina o brilho neon dos objetos
            if halo < 0.999 and isinstance(getattr(pos, "op", None), dict):
                for kk in list(pos.op):
                    if kk in ("brilho", "luz", "glow"):
                        pos.op[kk] = pos.op[kk] * halo
            pos_cache[el.id] = pos
            slots = None
            if el.slots:
                slots = {}
                for nome, sl in el.slots.items():
                    img = self.render_filho(el, nome, sl, pos, t)
                    if img is not None:
                        slots[nome] = img
            res = pos.desenhar(limite=lim, ss=2, slots=slots)
            if el.sombra:
                itens.append((el.k, el.z - 0.5, self.sombra_sprite(el, pos)))
            if res:
                img, ox, oy = res
                itens.append((el.k, el.z, Sprite(img, ox, oy, recortar=False)))
            for lz in pos.luzes():
                luzes.append((el.k,) + lz)
        for k, o, sp in sorted(itens, key=lambda i: (i[0], i[1])):
            m.camada(sp, k)
        if self.ambiente:
            m.cobrir(self.ambiente[0], self.ambiente[1])
        for k, x, y, r, cor, inten, ex in luzes:
            m.luz(k, x, y, r, cor, inten, ex)
        for lz in self.c.get("luzes", []):
            p = self.pf(lz.get("pos"), [0.5, 0.5])
            inten = float(lz.get("int", 0.5))
            if lz.get("piscar"):
                inten *= 0.85 + 0.15 * math.sin(t * 11) * math.sin(t * 7.3)
            from .recursos.validar import cor as _cor
            cc = (_cor(lz.get("cor", "#ffffff")) or (255, 255, 255, 255))[:3]
            m.luz(float(lz.get("k", 1.0)), p[0] * w, p[1] * h, float(self.pf(lz.get("raio"), 0.4)) * h, cc, inten, float(lz.get("exp", 1.8)))
        fade = lambda a, b: clamp((t - a) / 0.2) * clamp((b - t) / 0.2)
        self._t = t
        return m

    # ------------------------------------------------------------------ HUD
    _cache_cont = {}

    def hud(self, f, t):
        w, h, u = self.w, self.h, self.u
        spec = self.c.get("hud") or {}
        ch = spec.get("chip")
        if ch:
            self.chip(f, t, ch.get("hora", ""), ch.get("dia", ""), ini=float(ch.get("t", 0.35)))
        from .recursos.validar import cor as _cor
        for e in spec.get("etiquetas", []):
            ini = float(e.get("t", 0.5))
            fim = float(e.get("fim", self.dur))
            if not (ini <= t < fim):
                continue
            pe = tw(t, ini, 0.55, "out_back")
            cc = (_cor(e.get("cor", "#ff4d4f")) or (255, 77, 79, 255))[:3]
            img = hud.etiqueta(u, e.get("texto", ""), fundo=cc, tam=float(e.get("tam", 46)), subtexto=e.get("sub"))
            p = self.pf(e.get("pos"), [0.5, 0.2])
            meia = img.size[0] / 2 * 1.05 + 0.025 * w          # o selo nunca ultrapassa a borda da tela (rotacao inclusa)
            px = min(max(p[0] * w, meia), w - meia)
            hud.colar(f, img, px, p[1] * h + (1 - pe) * 40 * u, ang=float(e.get("rot", -4)) + (1 - pe) * 8, esc=0.7 + 0.3 * pe,
                      opac=tw(t, ini, 0.2, "out_cubic") * clamp((fim - t) / 0.2))
        for e in spec.get("contadores", []):
            ini = float(e.get("t", 0.6))
            fim = float(e.get("fim", self.dur))
            if not (ini <= t < fim):
                continue
            dur_c = float(e.get("dur", 1.8))
            v = lerp(float(e.get("de", 0)), float(e["ate"]), tw(t, ini + 0.1, dur_c, "out_cubic"))
            dec = int(e.get("decimais", 0))
            num = f"{v:,.{dec}f}".replace(",", "#").replace(".", ",").replace("#", ".")
            texto = f"{e.get('prefixo', '')}{num}{e.get('sufixo', '')}"
            cc = (_cor(e.get("cor", "#ff3e48")) or (255, 62, 72, 255))[:3]
            base = float(self.pf(e.get("tam"), 150))
            tam = min(base, 1.30 * (0.90 * w / u) / max(3.0, len(texto)))
            ck = (texto, round(tam, 1), tuple(cc))
            if ck not in self._cache_cont:
                if len(self._cache_cont) > 60:
                    self._cache_cont.clear()
                self._cache_cont[ck] = hud.numero_grande(u, texto, tam, cc, extrusao=12, brilho=0.6, claro=0.25)
            img = self._cache_cont[ck]
            p = self.pf(e.get("pos"), [0.5, 0.2])
            pe = tw(t, ini, 0.5, "out_back")
            meia = img.size[0] / 2 + 0.03 * w
            cxn = min(max(p[0] * w, meia), w - meia)
            hud.colar(f, img, cxn, p[1] * h, esc=0.75 + 0.25 * pe, opac=tw(t, ini, 0.2, "out_cubic") * clamp((fim - t) / 0.2))
            if e.get("sub"):
                sb = hud.pilula(u, str(e["sub"]), (255, 214, 120), tam=float(e.get("tam_sub", 34)))
                hud.colar(f, sb, cxn, p[1] * h + tam * u * 0.78, esc=0.8 + 0.2 * pe, opac=tw(t, ini + 0.25, 0.25, "out_cubic") * clamp((fim - t) / 0.2))
        for e in spec.get("chamadas", []):
            ini = float(e.get("t", 0.8))
            fim = float(e.get("fim", self.dur))
            if not (ini <= t < fim):
                continue
            cc = (_cor(e.get("cor", "#ff8a80")) or (255, 138, 128, 255))[:3]
            a0, a1 = self.pf(e.get("alvo"), [0.5, 0.5]), self.pf(e.get("para"), [0.7, 0.4])
            hud.chamada(f, (a0[0] * w, a0[1] * h), (a1[0] * w, a1[1] * h), e.get("texto", ""), tw(t, ini, 0.8, "out_cubic") * clamp((fim - t) / 0.2), u,
                        cor=cc, tam=float(e.get("tam", 28)), detalhe=e.get("detalhe"))
        for e in spec.get("pilulas", []):
            ini = float(e.get("t", 0.5))
            fim = float(e.get("fim", self.dur))
            if not (ini <= t < fim):
                continue
            pe = tw(t, ini, 0.5, "out_back")
            cc = (_cor(e.get("cor", "#ffbe5c")) or (255, 190, 92, 255))[:3]
            img = hud.pilula(u, e.get("texto", ""), cc, tam=float(e.get("tam", 30)))
            p = self.pf(e.get("pos"), [0.5, 0.2])
            hud.colar(f, img, p[0] * w, p[1] * h - (1 - pe) * 30 * u, esc=0.8 + 0.2 * pe, opac=tw(t, ini, 0.2, "out_cubic") * clamp((fim - t) / 0.2))
