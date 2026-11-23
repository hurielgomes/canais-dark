"""
cenas.py - as cenas do preset `alerta_noturno`. Cada cena = camadas (fundo -> primeiro plano) + camera + HUD + legenda.
Todas sao funcoes puras de t; os sprites estaticos sao montados uma vez em `construir()`.
Layout: cada cena define posicoes PROPRIAS para vertical (9:16) e horizontal (16:9) - nao e redimensionamento.
"""
import math

from PIL import Image, ImageFilter

from ..comum import hud, legendas
from ..comum.tween import clamp, falha_luz, in_out, lerp, out_back, out_cubic, out_expo, pulso, respirar, tw
from . import cenarios as cn
from . import objetos as ob
from .camadas import Mundo, Sprite, bloom, grade, vinheta
from .cenarios import PAL
from .pintura import Lona, alfa, brilho_sprite, degradado, mix, sombra


class CenaBase:
    def __init__(self, cena, w, h, formato, bib=None):
        self.c, self.w, self.h, self.formato = cena, w, h, formato
        self.vert = h > w
        self.u = min(w, h) / 1080.0
        self.dur = float(cena["duracao"])
        self.pad = int(70 * self.u)
        self.construir()

    # --- a implementar -------------------------------------------------------
    def construir(self):
        pass

    def mundo(self, t):
        raise NotImplementedError

    def hud(self, f, t):
        pass

    # --- pipeline do quadro -----------------------------------------------
    def quadro(self, t):
        th = self.c.get("tema") or {}      # tema visual (temas_m1.py); sem tema = look neon escuro original
        m = self.mundo(t)
        rgb = m.rgb()
        gb = float(th.get("bloom_ganho", self.c.get("bloom_ganho", 1.0)))
        if gb > 0.01:
            rgb = bloom(rgb, limiar=int(th.get("bloom_limiar", self.c.get("bloom_limiar", 175))), ganho=gb)
        if float(th.get("vinheta", 0.60)) > 0.005:
            rgb = vinheta(rgb, float(th.get("vinheta", 0.60)))
        rgb = grade(rgb, float(th.get("contraste", 1.07)), tint=tuple(th.get("tint", (0, 3, 14))))
        f = rgb.convert("RGBA")
        fx = th.get("faixa") or {}
        legendas.faixa_base(f, self.w, self.h, 0.60 if self.vert else 0.74, float(fx.get("forca", 0.58)), tuple(fx.get("cor", (0, 0, 6))))
        self.hud(f, t)
        lg = th.get("legenda") or {}
        kw = {}
        if lg:
            kw = dict(cor_texto=tuple(lg["texto"]), cor_nao_falada=tuple(lg["nao_falada"]), cor_sombra=tuple(lg["sombra"]))
            if lg.get("destaque"):
                from .recursos.validar import cor as _cor
                kw["cor_destaque"] = tuple((_cor(lg["destaque"]) or (255, 92, 92, 255))[:3])
        legendas.desenhar(f, t, self.c.get("legenda", []), self.w, self.h, self.formato, self.c.get("destaques", []), **kw)
        # entrada (da escuridao / do claro) e saida
        a_in = 1 - tw(t, 0.0, 0.30, "linear")
        a_out = tw(t, self.dur - 0.20, 0.20, "in_cubic")
        esc = max(a_in, a_out)
        if esc > 0.004:
            ov = Image.new("RGBA", f.size, tuple(th.get("fade", (3, 5, 12))) + (int(255 * min(1.0, esc)),))
            f.alpha_composite(ov)
        return f.convert("RGB")

    # --- utilidades -----------------------------------------------------------
    def S(self, img, x, y, recortar=False):
        return Sprite(img, x, y, recortar=recortar)

    def chip(self, f, t, hora, dia, ini=0.35, alvo=None):
        p = tw(t, ini, 0.55, "out_back")
        o = tw(t, ini, 0.25, "out_cubic")
        th = self.c.get("tema") or {}
        ac = (th.get("acento") and tuple(int(th["acento"].lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))) or (255, 77, 79)
        img, m = hud.chip_relogio(self.u, hora, dia, t, acento=ac, tema={k: tuple(v) for k, v in (th.get("chip") or {}).items()} or None)
        if self.vert:
            cx, cy = self.w / 2, self.h * 0.098
        else:
            cx, cy = self.w * 0.05 + img.width / 2 - m, self.h * 0.095
        hud.colar(f, img, cx, cy - (1 - p) * 46 * self.u, esc=0.86 + 0.14 * p, opac=o)


# ============================================================================== CENA 1
class CenaObjetoHeroi(CenaBase):
    """Geladeira no escuro: a porta abre, a luz pisca e o apagao chega. Janela com cidade que vai apagando."""

    def construir(self):
        w, h, u, pad = self.w, self.h, self.u, self.pad
        v = self.vert
        self.floor_y = int(h * (0.705 if v else 0.80))
        self.fh = int(h * (0.47 if v else 0.66))
        self.fw = int(self.fh * (0.56 if v else 0.47))
        self.fx = int(w * (0.64 if v else 0.60) - self.fw / 2)
        self.fy = self.floor_y - self.fh
        # parede
        parede = cn.parede(w + 2 * pad, self.floor_y + pad, topo=(24, 31, 66), base=(9, 12, 28))
        self.sp_parede = self.S(parede, -pad, -pad)
        # janela
        ww = int(w * (0.40 if v else 0.21))
        wh = int(ww * (1.12 if v else 1.25))
        wx = int(w * (0.07 if v else 0.15))
        wy = int(h * (0.20 if v else 0.14))
        self.win = (wx, wy, ww, wh)
        ceu = cn.ceu(ww, wh, 70, seed=2)
        sky, self.jan_lst = cn.skyline(ww, int(wh * 0.52), seed=4, cor=(10, 14, 32), altura=(0.3, 0.95),
                                       larg=(34, 70), janela=(6, 8), passo=(15, 20))
        ceu.alpha_composite(sky, dest=(0, wh - sky.height))
        moon = cn.lua(ww * 0.075)
        ceu.alpha_composite(moon, dest=(int(ww * 0.70 - moon.width / 2), int(wh * 0.22 - moon.height / 2)))
        self.ceu_img = ceu
        Lj = Lona(ww + int(60 * u), wh + int(80 * u), 2)
        mj = int(30 * u)
        bw = 16 * u
        Lj.rect(mj - bw, mj - bw, mj + ww + bw, mj + wh + bw, outline=(10, 13, 30, 255), w=bw, r=6 * u)
        Lj.rect(mj - bw, mj - bw, mj + ww + bw, mj + wh + bw, outline=(70, 84, 140, 110), w=2.2 * u, r=6 * u)
        Lj.rect(mj + ww / 2 - 5 * u, mj, mj + ww / 2 + 5 * u, mj + wh, fill=(10, 13, 30, 255))
        Lj.rect(mj, mj + wh * 0.48, mj + ww, mj + wh * 0.48 + 10 * u, fill=(10, 13, 30, 255))
        Lj.rect(mj - bw - 10 * u, mj + wh + bw, mj + ww + bw + 10 * u, mj + wh + bw + 14 * u, fill=(46, 56, 104, 255), r=4 * u)
        self.moldura = self.S(Lj.pronto(), wx - mj, wy - mj)
        # piso
        self.sp_piso = self.S(cn.piso_tabuas(w + 2 * pad, h + 2 * pad, self.floor_y + pad, (28, 34, 70), (8, 10, 24)), -pad, -pad)
        # facho de luz da lua no chao
        Lf = Lona(w, h, 1)
        fx0, fx1 = wx + ww * 0.05, wx + ww * 0.95
        Lf.poly([(fx0, wy + wh), (fx1, wy + wh), (fx1 + w * 0.30, h), (fx0 - w * 0.02, h)], fill=(150, 175, 240, 22))
        shaft = Lf.pronto().filter(ImageFilter.GaussianBlur(26 * u))
        self.sp_facho = self.S(shaft, 0, 0, recortar=True)
        # sombra sob a geladeira
        Ls = Lona(int(self.fw * 1.5), int(60 * u), 1)
        Ls.elipse(self.fw * 0.75, 30 * u, self.fw * 0.62, 17 * u, fill=(0, 0, 0, 235))
        sh = Ls.pronto().filter(ImageFilter.GaussianBlur(11 * u))
        self.sp_sombra = self.S(sh, int(self.fx + self.fw / 2 - self.fw * 0.75), self.floor_y - int(14 * u))
        # planta de primeiro plano
        pw, ph = int(w * (0.34 if v else 0.17)), int(h * (0.26 if v else 0.40))
        self.sp_planta = self.S(ob.planta(pw, ph, u, lado=-1), -int(20 * u), h - ph + int(30 * u), recortar=True)
        # termometro: posicao
        self.tubo = self.fh * 0.60
        self.tx = int(self.fx - (0.185 * w if v else 0.095 * w))

    # ---------------------------------------------------------------- animacao
    def estado(self, t):
        theta = 62 * (tw(t, 0.75, 1.15, "out_cubic") - tw(t, 4.25, 0.95, "in_out"))
        abre = clamp(theta / 62.0)
        flick = falha_luz(t, 3.35, 4.35, semente=4)
        luz = abre * (flick if t > 3.35 else 1.0) * (0.9 + 0.1 * math.sin(t * 7)) if t < 4.4 else 0.0
        led = 1.0 if t < 4.3 else 0.0
        nivel = 0.16 + 0.60 * tw(t, 1.5, 2.9, "in_out")
        return theta, luz, led, nivel

    def mundo(self, t):
        w, h, u, pad = self.w, self.h, self.u, self.pad
        m = Mundo(w, h, base_rgb=(8, 10, 22))
        zoom = 1.0 + 0.075 * tw(t, 0, self.dur, "in_out") + 0.05 * (1 - tw(t, 0, 0.5, "out_cubic"))
        m.camera(pan=(34 * tw(t, 0, self.dur, "in_out") * u, -10 * u * tw(t, 0, self.dur, "in_out")), zoom=zoom)
        theta, luz, led, nivel = self.estado(t)
        wx, wy, ww, wh = self.win
        # --- fundo
        m.camada(self.sp_parede, 0.10)
        # janela: ceu + janelas acesas apagando + estrelas
        ceu = self.ceu_img.copy()
        stars, sx0, sy0 = cn.estrelas_piscando(ww, int(wh * 0.5), t, n=14, seed=3)
        ceu.alpha_composite(stars, dest=(0, 0))
        jan = cn.janelas_acesas(ww, int(wh * 0.52), self.jan_lst, t, 3.4, 5.2, seed=7)
        ceu.alpha_composite(jan, dest=(0, wh - jan.height))
        m.camada(self.S(ceu, wx, wy), 0.12)
        m.camada(self.moldura, 0.12)
        m.luz(0.12, wx + ww * 0.7, wy + wh * 0.22, ww * 0.9, PAL["lua"], 0.20, 2.0)
        # --- piso e facho
        m.camada(self.sp_piso, 0.32)
        m.camada(self.sp_facho, 0.32)
        m.camada(self.sp_sombra, 0.62)
        # --- termometro (dinamico)
        quente = nivel
        termo, (bx, by), topo = ob.termometro(self.tubo, u, nivel, t, quente)
        tmarg = termo.height
        ty = self.floor_y - int(tmarg - 40 * u)
        tsp = self.S(termo, self.tx - int(30 * u + 30 * u), ty)
        m.camada(tsp, 0.66)
        # --- geladeira (heroi)
        ger, mg, (yd0, yd1), xi = ob.geladeira(self.fw, self.fh, u, t, theta, luz, led, rim=0.9)
        m.camada(self.S(ger, self.fx - mg, self.fy - mg), 0.66)
        # luz que sai da geladeira: no chao e no ambiente
        cx_int = self.fx - mg + xi
        cy_int = self.fy - mg + (yd0 + yd1) / 2
        if luz > 0.01:
            m.luz(0.66, cx_int, cy_int, self.fh * 0.70, (140, 200, 255), 0.30 * luz, 1.9)
            m.luz(0.66, cx_int - self.fw * 0.1, self.floor_y + 0.03 * h, self.fw * 1.9, (130, 190, 255), 0.45 * luz, 1.7, ry=self.fh * 0.18)
        if led > 0.5:
            m.luz(0.66, self.fx + self.fw - 38 * u, self.fy + 36 * u, 52 * u, PAL["alerta"], 0.55, 1.8)
        # poeira no facho
        area = (int(self.fx - self.fw * 1.3), int(self.fy), int(self.fx + self.fw * 1.3), int(self.floor_y))
        if luz > 0.05:
            d, dx, dy = cn.particulas_poeira(w, h, t, area, n=30, seed=8, a_max=0.55 * luz)
            m.camada(self.S(d, dx, dy), 0.78)
        # --- primeiro plano desfocado (parallax forte)
        m.camada(self.sp_planta, 1.45, suave=True)
        # escurecimento progressivo do apagao
        m.cobrir((3, 4, 12), 0.34 * tw(t, 3.6, 1.6, "in_out"))
        self._cache = dict(theta=theta, nivel=nivel, topo=topo, bx=bx, by=by, ty=ty, mg=mg, m=m)
        return m

    def hud(self, f, t):
        w, h, u = self.w, self.h, self.u
        c = self._cache
        m = c["m"]
        self.chip(f, t, self.c.get("hora", "22:10"), self.c.get("dia", "SEXTA"))
        # termometro: leitura que acompanha o mercurio (chamada com linha-guia)
        nivel = c["nivel"]
        temp = 4 + 15 * nivel
        px, py = m.ponto(0.66, self.tx - 30 * u + 56 * u * 0.5 + 0 * u, c["ty"] + (c["topo"] - 0))
        alvo = (px + 28 * u, py)
        pos_lab = (px - (0.22 if self.vert else 0.10) * w, py - (0.07 if self.vert else 0.09) * h)
        pp = tw(t, 1.35, 0.7, "out_cubic")
        hud.chamada(f, alvo, (alvo[0] - 40 * u, alvo[1] - 110 * u), f"{temp:.0f} \u00b0C", pp, u,
                    cor=(255, 150, 140), tam=30, detalhe="temperatura interna")
        # etiqueta "4 HORAS"
        pe = tw(t, 2.5, 0.65, "out_back")
        if pe > 0:
            et = hud.etiqueta(u, "4 HORAS", fundo=PAL["alerta"], tam=54, subtexto="porta fechada")
            if self.vert:
                ex, ey = self.w * 0.70, self.h * 0.215
            else:
                ex, ey = self.w * 0.80, self.h * 0.20
            hud.colar(f, et, ex, ey + (1 - pe) * 40 * u, ang=-4 + (1 - pe) * 8, esc=0.7 + 0.3 * pe, opac=tw(t, 2.5, 0.2, "out_cubic"))


# ============================================================================== CENA 2
class CenaNivel(CenaBase):
    """Caixa d'agua no topo de um predio, enchendo de 0 a 100 %: a agua muda de cor/estado e a leitura acompanha."""

    def construir(self):
        w, h, u, pad = self.w, self.h, self.u, self.pad
        v = self.vert
        self.th_ = int(h * (0.285 if v else 0.50))
        self.tw_ = int(self.th_ * (1.30 if v else 1.05))
        self.roof_y = int(h * (0.725 if v else 0.80))
        self.leg_h = int(h * (0.085 if v else 0.11))
        self.cx = int(w * (0.42 if v else 0.34))
        self.tank_bot = self.roof_y - self.leg_h
        self.tank_top = self.tank_bot - self.th_
        self.tx0 = self.cx - self.tw_ // 2
        # --- ceu, lua, skylines
        self.sp_ceu = self.S(cn.ceu(w + 2 * pad, h + 2 * pad, 130, seed=5), -pad, -pad)
        moon = cn.lua(int(36 * u))
        self.sp_lua = self.S(moon, int(w * (0.80 if v else 0.62) - moon.width / 2), int(h * (0.13 if v else 0.16) - moon.height / 2), recortar=True)
        for nome, seed, cor, alt, k in (("sky_far", 8, (16, 22, 50), (0.30, 0.75), 0.06), ("sky_near", 3, (11, 15, 36), (0.35, 1.0), 0.14)):
            fh_ = int(h * (0.20 if nome == "sky_far" else 0.17))
            sk, jan = cn.skyline(w + 2 * pad, fh_, seed=seed, cor=cor, altura=alt, larg=(46, 104), janela=(7, 10), passo=(18, 24))
            lit = cn.janelas_acesas(w + 2 * pad, fh_, jan, 0.0, 1e9, 1e9 + 1, seed=seed + 1, base_alpha=0.55 if nome == "sky_far" else 0.9)
            sk.alpha_composite(lit)
            setattr(self, "sp_" + nome, self.S(sk, -pad, self.roof_y - fh_ + (0 if nome == "sky_near" else -int(8 * u))))
        # --- fachada do predio + platibanda
        fh_ = h - self.roof_y + pad
        Lf = Lona(w + 2 * pad, fh_, 2)
        Lf.poly_grad([(0, 0), (w + 2 * pad, 0), (w + 2 * pad, fh_), (0, fh_)], (38, 47, 92), (13, 17, 38))
        import random
        rnd = random.Random(12)
        cw, ch = 150 * u, 120 * u
        yy = 70 * u
        while yy + 70 * u < fh_:
            xx = 30 * u
            while xx + 56 * u < w + 2 * pad:
                on = rnd.random() < 0.55
                cor = mix(PAL["ambar"], (255, 236, 200), rnd.random() * 0.4) if on else (18, 23, 50)
                Lf.rect(xx, yy, xx + 60 * u, yy + 76 * u, fill=cor + (255 if on else 255,), r=4 * u)
                if on:
                    Lf.rect(xx, yy, xx + 60 * u, yy + 76 * u, outline=(255, 210, 120, 70), w=2 * u, r=4 * u)
                xx += cw
            yy += ch
        Lf.rect(0, 0, w + 2 * pad, 30 * u, fill=(70, 84, 140, 255))
        Lf.rect(0, 0, w + 2 * pad, 6 * u, fill=(168, 186, 245, 160))
        Lf.rect(0, 30 * u, w + 2 * pad, 52 * u, fill=(0, 0, 0, 90))
        self.sp_fachada = self.S(Lf.pronto(), -pad, self.roof_y)
        # --- estrutura da caixa (corpo / moldura) + mascara da agua
        Lc, mg, inner, geo = ob.caixa_estrutura(self.tw_, self.th_, self.leg_h, u)
        self.mg = mg
        self.sp_corpo = self.S(Lc.pronto(), self.tx0 - mg, self.tank_top - mg)
        Lm = Lona(Lc.w, Lc.h, 2)
        ob.caixa_moldura(Lm, geo, u)
        self.sp_moldura = self.S(Lm.pronto(), self.tx0 - mg, self.tank_top - mg)
        self.inner = (int(inner[0]), int(inner[1]), int(inner[2]), int(inner[3]))
        iw, ih = self.inner[2] - self.inner[0], self.inner[3] - self.inner[1]
        self.iw, self.ih = iw, ih
        self.mask = mascara_rrect_local(iw, ih, 18 * u)
        # --- tubulacao (estatica)
        self.xp = int(self.cx + self.tw_ / 2 + (0.14 * w if v else 0.085 * w))
        self.y_in = int(self.tank_bot - 0.26 * self.th_)
        self.caminho = [(self.xp, self.roof_y - 70 * u), (self.xp, self.y_in), (self.cx + self.tw_ / 2 - 6 * u, self.y_in)]
        Lp = Lona(w, h, 2)
        for cor, wd in (((20, 26, 56, 255), 30 * u), ((74, 90, 150, 255), 24 * u), ((150, 172, 240, 120), 6 * u)):
            Lp.linha(self.caminho, cor, w=wd, cap=False)
        for pt in (self.caminho[1],):
            Lp.elipse(pt[0], pt[1], 17 * u, fill=(74, 90, 150, 255), outline=(20, 26, 56, 255), w=3 * u)
        Lp.rect(self.xp - 22 * u, self.roof_y - 96 * u, self.xp + 22 * u, self.roof_y - 70 * u, fill=(90, 108, 170, 255), r=5 * u)
        self.sp_tubo = self.S(Lp.pronto(), 0, 0, recortar=True)
        # --- cabo de primeiro plano
        Lk = Lona(w + 2 * pad, int(160 * u), 2)
        pts = []
        for i in range(0, 41):
            x = i / 40.0 * (w + 2 * pad)
            pts.append((x, 40 * u + 70 * u * math.sin(math.pi * i / 40.0)))
        Lk.linha(pts, (4, 6, 14, 255), w=7 * u, cap=False)
        Lk.linha([(x, y - 3 * u) for x, y in pts], (110, 136, 220, 90), w=2 * u, cap=False)
        self.sp_cabo = self.S(Lk.pronto().filter(ImageFilter.GaussianBlur(2.2 * u)), -pad, int(h * (0.47 if v else 0.30)))

    def nivel(self, t):
        return 0.0 if t < 0.9 else 0.03 + 0.97 * tw(t, 0.9, 3.4, "in_out")

    def estado(self, n):
        return "VAZIA" if n < 0.12 else "ENCHENDO" if n < 0.995 else "CHEIA"

    def mundo(self, t):
        w, h, u, pad = self.w, self.h, self.u, self.pad
        m = Mundo(w, h, base_rgb=(8, 10, 24))
        k = tw(t, 0, self.dur, "in_out")
        m.camera(pan=(10 * u * k, (44 - 82 * k) * u), zoom=1.0 + 0.06 * k + 0.05 * (1 - tw(t, 0, 0.5, "out_cubic")))
        n = self.nivel(t)
        fim = tw(t, 4.35, 0.6, "out_cubic")
        cor = ob._cor_nivel(n)
        m.camada(self.sp_ceu, 0.04)
        st, sx, sy = cn.estrelas_piscando(w, h, t, n=40, seed=4, area=(0, 0, w, int(h * 0.5)))
        m.camada(self.S(st, sx, sy), 0.05)
        m.camada(self.sp_lua, 0.06)
        m.camada(self.sp_sky_far, 0.06)
        m.camada(self.sp_sky_near, 0.14)
        m.camada(self.sp_fachada, 0.42)
        # tubulacao + corpo + agua + moldura (mesma camada: ficam alinhados)
        K = 0.70
        m.camada(self.sp_tubo, K)
        m.camada(self.sp_corpo, K)
        ix0, iy0, ix1, iy1 = self.inner
        ag = ob.agua(self.iw, self.ih, n, t, u, extra_brilho=fim, formato_mask=self.mask)
        m.camada(self.S(ag, self.tx0 - self.mg + ix0, self.tank_top - self.mg + iy0, recortar=n > 0.002), K)
        m.camada(self.sp_moldura, K)
        # bomba
        bomba = ob.bomba(u, t, 1.0 if 0.9 <= t < 4.3 else 0.0)
        m.camada(self.S(bomba, int(self.xp - bomba.width / 2), int(self.roof_y - 96 * u - bomba.height * 0.58)), K)
        # particulas de fluxo no cano
        if 0.9 <= t < 4.3:
            P = self.caminho
            seg = [math.hypot(P[i + 1][0] - P[i][0], P[i + 1][1] - P[i][1]) for i in range(len(P) - 1)]
            tot = sum(seg)
            Lp = Lona(w, h, 1)
            for i in range(14):
                s = ((t * 150 * u + i * tot / 14.0) % tot)
                acc = 0.0
                for j, sl in enumerate(seg):
                    if s <= acc + sl:
                        f = (s - acc) / sl
                        x = P[j][0] + (P[j + 1][0] - P[j][0]) * f
                        y = P[j][1] + (P[j + 1][1] - P[j][1]) * f
                        Lp.elipse(x, y, 5.5 * u, fill=alfa(mix(cor, (255, 255, 255), 0.5), 0.95))
                        Lp.elipse(x, y, 11 * u, fill=alfa(cor, 0.22))
                        break
                    acc += sl
            m.camada(self.S(Lp.pronto(), 0, 0, recortar=True), K)
        # luzes: a agua ilumina o entorno; flash ao completar
        m.luz(K, self.cx, self.tank_top + self.th_ * (1 - n * 0.5), self.tw_ * 1.15, cor, 0.16 + 0.30 * n, 1.8)
        flash = math.exp(-(max(0, t - 4.3)) * 3.2) if t >= 4.3 else 0.0
        if flash > 0.01:
            m.luz(K, self.cx, self.tank_top + self.th_ / 2, self.tw_ * 1.7, PAL["agua"], 0.6 * flash, 1.5)
        m.camada(self.sp_cabo, 1.5, suave=True)
        self._c = dict(m=m, n=n, cor=cor)
        return m

    def hud(self, f, t):
        w, h, u = self.w, self.h, self.u
        c = self._c
        m, n, cor = c["m"], c["n"], c["cor"]
        v = self.vert
        self.chip(f, t, self.c.get("hora", "22:15"), self.c.get("dia", "SEXTA"))
        # etiqueta
        pe = tw(t, 0.45, 0.6, "out_back")
        et = hud.etiqueta(u, "REGRA 1", fundo=PAL["alerta"], tam=50, subtexto="guarde água")
        ex, ey = (w * 0.27, h * 0.205) if v else (w * 0.72, h * 0.16)
        hud.colar(f, et, ex - (1 - pe) * 80 * u, ey, ang=-4 + (1 - pe) * -6, esc=0.7 + 0.3 * pe, opac=tw(t, 0.45, 0.2, "out_cubic"))
        # leitura grande
        pn = tw(t, 0.7, 0.5, "out_back")
        num = hud.numero_grande(u, f"{int(round(n * 100))}%", 170 if v else 250, cor, extrusao=8)
        nx, ny = (w * 0.72, h * 0.225) if v else (w * 0.72, h * 0.43)
        hud.colar(f, num, nx, ny, esc=0.8 + 0.2 * pn + 0.05 * math.exp(-max(0, t - 4.3) * 4) * (t >= 4.3), opac=tw(t, 0.7, 0.3, "out_cubic"))
        lab = Lona(int(420 * u), int(50 * u), 2)
        lab.texto_esp(210 * u, 25 * u, "NÍVEL DA CAIXA", "mono", 24 * u, (160, 174, 214, 255), esp=3.2 * u, anchor="m")
        hud.colar(f, lab.pronto(), nx, ny - (150 if v else 190) * u, opac=tw(t, 0.8, 0.3, "out_cubic"))
        pil = hud.pilula(u, self.estado(n), cor, tam=30)
        hud.colar(f, pil, nx, ny + (125 if v else 175) * u, opac=tw(t, 0.9, 0.3, "out_cubic"))
        # conclusao: aneis + selo
        if t >= 4.3:
            tt = t - 4.3
            cx, cy = m.ponto(0.70, self.cx, self.tank_top + self.th_ / 2)
            Lr = Lona(w, h, 1)
            for i in range(3):
                p = clamp((tt - i * 0.18) / 1.0)
                if 0 < p < 1:
                    Lr.elipse(cx, cy, self.tw_ * (0.55 + 0.75 * out_cubic(p)), self.th_ * (0.55 + 0.75 * out_cubic(p)),
                              outline=alfa(PAL["agua"], 0.6 * (1 - p)), w=max(2, 5 * u * (1 - p)))
            f.alpha_composite(Lr.pronto())
            ps = tw(t, 4.35, 0.5, "out_back")
            sel = ob.selo_ok(120 * u, tw(t, 4.5, 0.5, "out_cubic"))
            hud.colar(f, sel, cx + self.tw_ * 0.40, cy - self.th_ * 0.52, esc=ps, opac=tw(t, 4.35, 0.15, "linear"))


def mascara_rrect_local(w, h, r):
    from .pintura import mascara_rrect
    return mascara_rrect(w, h, r, 2)


# ============================================================================== CENA 3
class CenaPessoaTela(CenaBase):
    """Pessoa de costas diante de uma tela: contra-luz azulada na silhueta, vela quente ao lado (contraste frio/quente)."""

    def construir(self):
        w, h, u, pad = self.w, self.h, self.u, self.pad
        v = self.vert
        self.sw = int(w * 0.66) if v else int(h * 0.45 * 1.5)
        self.sh = int(self.sw * 0.74) if v else int(h * 0.45)
        self.tvx = int(w * 0.5 - self.sw / 2)
        self.tvy = int(h * (0.215 if v else 0.115))
        self.floor_y = int(h * (0.64 if v else 0.66))
        self.s = u * (1.0 if v else 0.95)
        self.pcx = int(w * 0.5)
        self.pcy = int(h * (0.700 if v else 0.915))
        # parede + piso
        Lw = Lona(w + 2 * pad, h + 2 * pad, 1)
        parede = cn.parede(w + 2 * pad, h + 2 * pad, topo=(22, 30, 62), base=(10, 14, 32))
        self.sp_parede = self.S(parede, -pad, -pad)
        piso = cn.piso_tabuas(w + 2 * pad, h + 2 * pad, self.floor_y + pad, (24, 30, 62), (7, 9, 22))
        self.sp_piso = self.S(piso, -pad, -pad)
        # moldura da tv + movel
        m = int(40 * u)
        Lt = Lona(self.sw + 2 * m, self.sh + 2 * m + int(150 * u), 2)
        Lt.rect(m - 18 * u, m - 18 * u, m + self.sw + 18 * u, m + self.sh + 18 * u, fill=(10, 13, 30, 255), r=22 * u)
        Lt.rect(m - 18 * u, m - 18 * u, m + self.sw + 18 * u, m + self.sh + 18 * u, outline=(110, 132, 210, 120), w=2.5 * u, r=22 * u)
        # pe da tv + aparador
        yb = m + self.sh + 18 * u
        Lt.rect(m + self.sw * 0.42, yb, m + self.sw * 0.58, yb + 36 * u, fill=(16, 20, 42, 255))
        Lt.rect(m + self.sw * 0.30, yb + 36 * u, m + self.sw * 0.70, yb + 50 * u, fill=(24, 30, 60, 255), r=6 * u)
        self.mgt = m
        self.sp_tv = self.S(Lt.pronto(), self.tvx - m, self.tvy - m)
        # reflexo de vidro (diagonal suave) sobre a tela
        Lr = Lona(self.sw, self.sh, 2)
        Lr.poly([(self.sw * 0.0, 0), (self.sw * 0.34, 0), (self.sw * 0.06, self.sh), (0, self.sh)], fill=(255, 255, 255, 16))
        self.reflexo = Lr.pronto()
        # corpo da pessoa (estatico)
        corpo, (cx, cy) = ob.pessoa_corpo(self.s)
        self.sp_corpo = self.S(corpo, int(self.pcx - cx), int(self.pcy - cy))
        self.corpo_orig = (cx, cy)
        # mesa + vela
        mesa, (fx, fy) = ob.mesa_vela(u, 0)
        self.mesa_w, self.mesa_h = mesa.size
        topo_mesa = int(h * (0.575 if v else 0.62))
        self.mx = int(w * (0.135 if v else 0.15) - self.mesa_w / 2)
        self.my = topo_mesa - int(self.mesa_h * 0.48)
        self.sp_mesa = self.S(mesa, self.mx, self.my)
        self.chama_xy = (self.mx + fx, self.my + fy)
        # primeiro plano: planta desfocada do lado direito
        pw, ph = int(w * (0.30 if v else 0.15)), int(h * (0.30 if v else 0.55))
        self.sp_planta = self.S(ob.planta(pw, ph, u, lado=+1, seed=9), w - pw + int(20 * u), h - ph + int(10 * u), recortar=True)

    def mundo(self, t):
        w, h, u, pad = self.w, self.h, self.u, self.pad
        m = Mundo(w, h, base_rgb=(7, 9, 22))
        k = tw(t, 0, self.dur, "in_out")
        m.camera(pan=(24 * u * k, -8 * u * k), zoom=1.0 + 0.085 * k + 0.05 * (1 - tw(t, 0, 0.5, "out_cubic")))
        msgs = [(0.9, "in", "Tá todo mundo bem?"), (1.9, "out", "Sem luz aqui. Tô bem."), (3.6, "in", "Guarda a bateria!")]
        # pulso de brilho a cada mensagem
        pulso_msg = sum(math.exp(-(max(0, t - ti)) * 5.0) * (t >= ti) for ti, _, _ in msgs)
        bateria = 0.12 if t < 3.0 else 0.11
        alerta = 1.0 if 3.0 <= t < 4.8 else 0.0
        dig = tw(t, 2.8, 0.2, "linear") * (1 - tw(t, 3.45, 0.15, "linear")) if 2.8 <= t < 3.6 else 0.0
        brilho = 0.88 + 0.07 * math.sin(t * 11) * math.sin(t * 3.1) + 0.10 * pulso_msg
        K = 0.60
        # fundo
        m.camada(self.sp_parede, 0.14)
        m.camada(self.sp_piso, 0.32)
        # luz da tela lavando parede e piso
        cxs, cys = self.tvx + self.sw / 2, self.tvy + self.sh / 2
        m.luz(0.14, cxs, cys, self.sw * 1.55, (70, 170, 255), 0.38 * brilho, 1.6)
        m.luz(0.32, cxs, self.floor_y + 0.05 * h, self.sw * 1.3, (60, 150, 245), 0.34 * brilho, 1.6, ry=self.sh * 0.5)
        # tv + conteudo
        m.camada(self.sp_tv, K)
        tela = ob.tela_chat(self.sw, self.sh, u, t, msgs, bateria, alerta, dig)
        tela.alpha_composite(self.reflexo)
        # brilho extra da tela (leve sobrexposicao quando chega mensagem)
        m.camada(self.S(tela, self.tvx, self.tvy), K)
        m.luz(K, cxs, cys, self.sw * 0.62, (140, 210, 255), 0.10 * brilho, 1.4, ry=self.sh * 0.62)
        # vela (quente) - luz ambar contrasta com o azul da tela
        m.camada(self.sp_mesa, 0.55)
        flame = ob.chama(u, t)
        m.camada(self.S(flame, int(self.chama_xy[0] - flame.width / 2), int(self.chama_xy[1] - flame.height * 0.72)), 0.55)
        fl = 0.85 + 0.15 * math.sin(t * 13) * math.sin(t * 7.3)
        m.luz(0.55, self.chama_xy[0], self.chama_xy[1], 230 * u, (255, 170, 80), 0.55 * fl, 1.7)
        m.luz(0.55, self.chama_xy[0], self.chama_xy[1] + 80 * u, 360 * u, (255, 150, 60), 0.20 * fl, 1.5, ry=170 * u)
        # contra-luz atras da pessoa (silhueta recortada contra a tela)
        m.luz(0.8, self.pcx, self.pcy - 190 * self.s, 0.55 * w, (70, 175, 255), 0.30 * brilho, 1.7, ry=0.30 * h)
        # pessoa: respira e vira levemente a cabeca
        resp = 1.0 + 0.006 * math.sin(2 * math.pi * t / 3.4)
        cx0, cy0 = self.corpo_orig
        corpo, _ = ob.pessoa_corpo(self.s, luz=0.55 + 0.45 * brilho)
        sp = self.S(corpo, int(self.pcx - cx0), int(self.pcy - cy0 - (resp - 1) * 400 * self.s))
        m.camada(sp, 1.0)
        giro = math.sin(math.pi * clamp((t - 3.0) / 0.9)) * 0.85 if 3.0 <= t < 3.9 else 0.0
        cab, (hx, hy) = ob.pessoa_cabeca(self.s, luz=0.55 + 0.45 * brilho, giro=giro)
        cab = cab.rotate(-3.0 * giro + 0.6 * math.sin(t * 0.8), resample=Image.BICUBIC)
        dx = 11 * self.s * giro
        m.camada(self.S(cab, int(self.pcx - hx + dx), int(self.pcy - 192 * self.s - hy - (resp - 1) * 400 * self.s)), 1.0)
        # poeira em suspensao, perto da tela
        d, dx_, dy_ = cn.particulas_poeira(w, h, t, (int(w * 0.1), int(h * 0.1), int(w * 0.9), int(h * 0.55)), n=26, seed=14, cor=(180, 220, 255), a_max=0.5)
        m.camada(self.S(d, dx_, dy_), 0.9)
        m.camada(self.sp_planta, 1.5, suave=True)
        self._c = dict(m=m, bat=bateria, alerta=alerta)
        return m

    def hud(self, f, t):
        w, h, u = self.w, self.h, self.u
        c = self._c
        m = c["m"]
        self.chip(f, t, self.c.get("hora", "06:00"), self.c.get("dia", "SÁBADO"))
        # chamada na bateria da tela
        hb = self.sh * 0.13
        bx, by = self.tvx + self.sw - hb * 0.85, self.tvy + hb / 2
        px, py = m.ponto(0.60, bx, by)
        pp = tw(t, 3.0, 0.7, "out_cubic")
        lx = px - (0.22 if self.vert else 0.14) * w
        ly = py - (0.080 if self.vert else 0.085) * h
        hud.chamada(f, (px, py), (lx, ly), f"{int(round(c['bat'] * 100))}%  BATERIA", pp, u, cor=(255, 140, 130), tam=30, detalhe="o bem mais precioso")


# ============================================================================== CENA 4
class CenaNumero(CenaBase):
    """Numero gigante dominante (contagem 0 -> 90) + calendario de 90 dias que acende em sincronia + etiqueta."""

    def construir(self):
        w, h, u, pad = self.w, self.h, self.u, self.pad
        v = self.vert
        self.alvo = int(self.c.get("valor", 90))
        self.cols = 15
        self.rows = (self.alvo + self.cols - 1) // self.cols
        self.passo = (58 if v else 50) * u
        self.cx_n = w * (0.5 if v else 0.285)
        self.cy_n = h * (0.385 if v else 0.45)
        self.tam_n = 560 if v else 500
        self.gx0 = (w - (self.cols - 1) * self.passo) / 2 if v else w * 0.555
        self.gy0 = h * (0.592 if v else 0.30)
        # fundo: degradê + halo vermelho
        bg = degradado(w + 2 * pad, h + 2 * pad, [(0, (14, 10, 28)), (0.5, (20, 12, 34)), (1, (8, 8, 20))]).convert("RGBA")
        self.sp_bg = self.S(bg, -pad, -pad)
        self.cache_num = {}
        # embers de fundo/primeiro plano sao desenhados por quadro; calendario idem
        self.vy = h * (0.46 if v else 0.40)

    def numero_img(self, texto, esc=1.0):
        k = (texto, round(esc, 3))
        if k not in self.cache_num:
            img = hud.numero_grande(self.u * esc, texto, self.tam_n, (255, 62, 72), extrusao=16, brilho=0.6, claro=0.22)
            if len(self.cache_num) > 40:
                self.cache_num.clear()
            self.cache_num[k] = img
        return self.cache_num[k]

    def piso_grade(self, t):
        w, h, u, pad = self.w, self.h, self.u, self.pad
        y0 = int(self.vy)
        Lg = Lona(w + 2 * pad, h + 2 * pad - y0, 2)
        cx = (w + 2 * pad) / 2
        H = h + 2 * pad - y0
        for i in range(-12, 13):
            Lg.linha([(cx + i * 22 * u, 0), (cx + i * (w * 0.20), H)], alfa(PAL["alerta"], 0.12), w=1.6 * u, cap=False)
        ph = (t * 0.22) % 1.0
        for j in range(12):
            q = ((j + ph) / 12.0)
            yy = H * q ** 2.1
            Lg.linha([(0, yy), (w + 2 * pad, yy)], alfa(PAL["alerta"], 0.04 + 0.12 * q), w=1.6 * u, cap=False)
        img = Lg.pronto()
        return self.S(img, -pad, y0)

    def embers(self, t, n, seed, k_far):
        import random
        w, h, u = self.w, self.h, self.u
        L = Lona(w, h, 1)
        rnd = random.Random(seed)
        for i in range(n):
            bx = rnd.uniform(0, w)
            vel = rnd.uniform(0.04, 0.12) * (1.6 if k_far else 1.0)
            y = h * (1.1 - ((t * vel + rnd.random()) % 1.0) * 1.25)
            x = bx + 26 * u * math.sin(t * rnd.uniform(0.6, 1.4) + i)
            a = (0.35 + 0.65 * rnd.random()) * (0.5 + 0.5 * math.sin(t * 2 + i))
            r = rnd.choice([1.6, 2.4, 3.4]) * u * (1.6 if k_far else 1.0)
            c = mix(PAL["alerta"], PAL["ambar"], rnd.random())
            L.elipse(x, y, r * 3, fill=alfa(c, 0.10 * a))
            L.elipse(x, y, r, fill=alfa(c, 0.9 * a))
        return self.S(L.pronto(), 0, 0, recortar=True)

    def calendario(self, n_acesos, t):
        w, h, u = self.w, self.h, self.u
        Lc = Lona(w, h, 2)
        p = self.passo
        for i in range(self.alvo):
            r_, c_ = divmod(i, self.cols)
            x, y = self.gx0 + c_ * p, self.gy0 + r_ * p
            s = p * 0.38
            if i < n_acesos:
                f = i / max(1, self.alvo - 1)
                cor = mix(PAL["ambar"], PAL["alerta"], f)
                pop = 1.0 + 0.45 * math.exp(-(n_acesos - 1 - i) * 0.5) if i >= n_acesos - 4 else 1.0
                Lc.rect(x - s * pop, y - s * pop, x + s * pop, y + s * pop, fill=cor + (255,), r=s * 0.35)
                Lc.rect(x - s * pop, y - s * pop, x + s * pop, y - s * pop * 0.1, fill=(255, 255, 255, 40), r=s * 0.3)
            else:
                Lc.rect(x - s, y - s, x + s, y + s, outline=(120, 132, 180, 90), w=1.8 * u, r=s * 0.35)
        return self.S(Lc.pronto(), 0, 0, recortar=True)

    def mundo(self, t):
        w, h, u, pad = self.w, self.h, self.u, self.pad
        m = Mundo(w, h, base_rgb=(9, 8, 20))
        k = tw(t, 0, self.dur, "in_out")
        sh = max(0.0, 1 - (t - 2.3) / 0.4) if 2.3 <= t < 2.7 else 0.0
        from ..comum.tween import tremor
        m.camera(pan=(tremor(t, 7 * u * sh, 38, 1) + 12 * u * k, tremor(t, 6 * u * sh, 41, 2)), zoom=1.0 + 0.05 * k + 0.05 * (1 - tw(t, 0, 0.45, "out_cubic")))
        prog = tw(t, 0.5, 1.8, "out_expo")
        n = int(round(self.alvo * prog))
        fim = t >= 2.3
        m.camada(self.sp_bg, 0.05)
        m.luz(0.05, self.cx_n, self.cy_n, 0.75 * min(w, h * 1.4) * (1.0 + 0.04 * math.sin(t * 2)), (255, 50, 70), 0.30 + 0.14 * prog, 2.0)
        m.camada(self.piso_grade(t), 0.20)
        m.camada(self.embers(t, 26, 3, True), 0.45)
        m.camada(self.calendario(n, t), 0.75)
        # numero: escala com "pop" ao terminar
        esc = 1.0 + (0.10 * math.exp(-(t - 2.3) * 5.5) * math.cos((t - 2.3) * 9) if t >= 2.3 else 0.0) + 0.04 * (1 - tw(t, 0.2, 0.4, "out_cubic"))
        img = self.numero_img(str(n), 1.0)
        if abs(esc - 1.0) > 0.004:
            img = img.resize((int(img.width * esc), int(img.height * esc)), Image.BICUBIC)
        a = tw(t, 0.25, 0.3, "out_cubic")
        # varredura de brilho especular
        if 2.7 <= t < 3.6:
            q = (t - 2.7) / 0.9
            band = Lona(img.width, img.height, 1)
            x0 = -img.height * 0.2 + q * (img.width + img.height * 0.4)
            band.poly([(x0, 0), (x0 + img.height * 0.16, 0), (x0 + img.height * 0.16 - img.height * 0.35, img.height), (x0 - img.height * 0.35, img.height)], fill=(255, 255, 255, 200))
            bb = band.pronto().filter(ImageFilter.GaussianBlur(10 * u))
            from PIL import ImageChops
            mk = ImageChops.multiply(bb.getchannel("A"), img.getchannel("A"))
            sw = Image.new("RGBA", img.size, (255, 255, 255, 0))
            sw.putalpha(mk.point(lambda v_: int(v_ * 0.55)))
            img = img.copy()
            img.alpha_composite(sw)
        if a < 0.99:
            img = img.copy()
            img.putalpha(img.getchannel("A").point(lambda v_, f=a: int(v_ * f)))
        m.camada(self.S(img, int(self.cx_n - img.width / 2), int(self.cy_n - img.height * 0.5)), 0.88)
        if t >= 2.3:
            m.luz(0.88, self.cx_n, self.cy_n, self.tam_n * u * 1.25, PAL["alerta"], 0.35 * math.exp(-(t - 2.3) * 1.4), 1.6)
        m.camada(self.embers(t, 14, 11, False), 1.35, suave=True)
        self._c = dict(m=m, n=n)
        return m

    def hud(self, f, t):
        w, h, u = self.w, self.h, self.u
        c = self._c
        n = c["n"]
        v = self.vert
        self.chip(f, t, f"DIA {n}", "SEM LUZ")
        # rotulo "DIAS" sob o numero
        pd = tw(t, 0.9, 0.55, "out_cubic")
        lab = Lona(int(520 * u), int(120 * u), 2)
        lab.texto_esp(260 * u, 60 * u, "DIAS", "forte", 92 * u, (236, 241, 255, 255), esp=26 * u, anchor="m")
        lx, ly = (self.cx_n, self.h * 0.548) if v else (self.cx_n, self.h * 0.800)
        hud.colar(f, lab.pronto(), lx, ly + (1 - pd) * 24 * u, opac=pd)
        # tag superior
        pt = tw(t, 0.6, 0.5, "out_back")
        pil = hud.pilula(u, "CENÁRIO EXTREMO", PAL["ambar"], tam=30)
        tx, ty = (self.w * 0.5, self.h * 0.20) if v else (self.cx_n, self.h * 0.195)
        hud.colar(f, pil, tx, ty - (1 - pt) * 30 * u, esc=0.8 + 0.2 * pt, opac=tw(t, 0.6, 0.2, "out_cubic"))
        # etiqueta
        pe = tw(t, 2.35, 0.6, "out_back")
        if pe > 0:
            et = hud.etiqueta(u, "SEM ENERGIA", fundo=PAL["alerta"], tam=46, subtexto="o pior cenário")
            ex, ey = (self.w * 0.765, self.h * 0.292) if v else (self.w * 0.43, self.h * 0.285)
            hud.colar(f, et, ex, ey + (1 - pe) * 60 * u, ang=-6 + (1 - pe) * 10, esc=0.65 + 0.35 * pe, opac=tw(t, 2.35, 0.15, "out_cubic"))
