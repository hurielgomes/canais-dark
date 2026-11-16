"""
pintura.py - primitivas de desenho do motor Cenas 2D (somente Pillow).

Lona  : tela RGBA com supersampling (desenha em ss x, reduz no fim) para bordas lisas.
        Coordenadas SEMPRE em pixels logicos (do video final).
Tambem: gradientes, brilhos radiais (aditivos), sombras suaves, texto com espacamento, curvas suavizadas.
"""
import math
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

AQUI = Path(__file__).resolve().parent
FONTES = {
    "preto": AQUI / "assets" / "fontes" / "Inter-Black.otf",
    "forte": AQUI / "assets" / "fontes" / "Inter-ExtraBold.otf",
    "semi": AQUI / "assets" / "fontes" / "Inter-SemiBold.otf",
    "medio": AQUI / "assets" / "fontes" / "Inter-Medium.otf",
    "mono": AQUI / "assets" / "fontes" / "DejaVuSansMono-Bold.ttf",
}


@lru_cache(maxsize=256)
def fonte(nome, tam):
    return ImageFont.truetype(str(FONTES[nome]), max(4, int(round(tam))))


# ------------------------------------------------------------------ cores
def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(len(a)))


def alfa(cor, a):
    return (cor[0], cor[1], cor[2], int(255 * max(0.0, min(1.0, a))))


# ------------------------------------------------------------------ curvas
def suavizar(pts, n=3, fechado=True):
    """Chaikin: transforma um poligono anguloso em curva organica"""
    pts = list(pts)
    for _ in range(n):
        novo = []
        m = len(pts)
        rng = range(m) if fechado else range(m - 1)
        for i in rng:
            p, q = pts[i], pts[(i + 1) % m]
            novo.append((0.75 * p[0] + 0.25 * q[0], 0.75 * p[1] + 0.25 * q[1]))
            novo.append((0.25 * p[0] + 0.75 * q[0], 0.25 * p[1] + 0.75 * q[1]))
        pts = novo
    return pts


def deslocar(pts, dx, dy):
    return [(x + dx, y + dy) for x, y in pts]


# ------------------------------------------------------------------ gradientes e luz
def degradado(w, h, stops, horizontal=False):
    """imagem RGB w x h; stops = [(pos 0..1, (r,g,b)), ...]  (vertical: topo->base)"""
    n = max(2, min(512, w if horizontal else h))
    px = []
    for i in range(n):
        u = i / (n - 1)
        for k in range(len(stops) - 1):
            if u <= stops[k + 1][0] or k == len(stops) - 2:
                a, b = stops[k], stops[k + 1]
                px.append(mix(a[1], b[1], (u - a[0]) / max(1e-6, b[0] - a[0])))
                break
    faixa = Image.new("RGB", (n, 1) if horizontal else (1, n))
    faixa.putdata(px)
    return faixa.resize((w, h), Image.BILINEAR)


@lru_cache(maxsize=64)
def _queda(expo):
    # o radial_gradient do Pillow vale 181 nas bordas (255 so nos cantos): normalizar para zerar exatamente na borda do circulo
    return [int(255 * (max(0.0, 1 - v / 181.0) ** expo)) for v in range(256)]


@lru_cache(maxsize=128)
def _radial(tam, expo):
    r = Image.radial_gradient("L").resize((tam, tam), Image.BILINEAR)
    return r.point(_queda(expo))


@lru_cache(maxsize=128)
def brilho_mask(r, expo=2.0):
    """mascara L (2r x 2r) com queda radial: 255 no centro, 0 na borda"""
    return _radial(int(max(4, r * 2)), expo)


def luz_aditiva(frame, cx, cy, r, cor, intens=1.0, expo=2.0, ry=None):
    """soma luz colorida ao frame RGB (mistura 'tela'/aditiva). ry!=None -> elipse"""
    r = int(max(4, r))
    ry = int(max(4, ry)) if ry else r
    m = brilho_mask(r, expo)
    if ry != r:
        m = m.resize((r * 2, ry * 2), Image.BILINEAR)
    if intens != 1.0:
        m = m.point(lambda v, k=intens: min(255, int(v * k)))
    x0, y0 = int(cx - r), int(cy - ry)
    W, H = frame.size
    ax0, ay0 = max(0, x0), max(0, y0)
    ax1, ay1 = min(W, x0 + 2 * r), min(H, y0 + 2 * ry)
    if ax1 <= ax0 or ay1 <= ay0:
        return
    mm = m.crop((ax0 - x0, ay0 - y0, ax1 - x0, ay1 - y0))
    cor_img = Image.new("RGB", mm.size, tuple(cor[:3]))
    glow = ImageChops.multiply(cor_img, Image.merge("RGB", (mm, mm, mm)))
    reg = frame.crop((ax0, ay0, ax1, ay1)).convert("RGB")
    frame.paste(ImageChops.add(reg, glow), (ax0, ay0))


def brilho_sprite(r, cor, alfa_max=1.0, expo=2.0, ry=None):
    """RGBA (2r x 2ry) com cor fixa e alfa em queda radial - para colar com alpha"""
    r = int(max(4, r))
    ry = int(max(4, ry)) if ry else r
    m = brilho_mask(r, expo)
    if ry != r:
        m = m.resize((r * 2, ry * 2), Image.BILINEAR)
    if alfa_max < 1:
        m = m.point(lambda v, k=alfa_max: int(v * k))
    img = Image.new("RGBA", m.size, tuple(cor[:3]) + (0,))
    img.putalpha(m)
    return img


def mascara_rrect(w, h, r, ss=2):
    m = Image.new("L", (int(w * ss), int(h * ss)), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w * ss - 1, h * ss - 1], radius=r * ss, fill=255)
    return m.reduce(ss)


def sombra(forma_L, raio, cor=(0, 0, 0), a=0.6):
    """sombra suave a partir de uma mascara L: devolve RGBA com a mesma dimensao (+margem tratada pelo chamador)"""
    m = forma_L.filter(ImageFilter.GaussianBlur(raio)).point(lambda v: int(v * a))
    img = Image.new("RGBA", forma_L.size, tuple(cor) + (0,))
    img.putalpha(m)
    return img


# ------------------------------------------------------------------ Lona
class Lona:
    def __init__(self, w, h, ss=2):
        self.w, self.h, self.ss = int(w), int(h), ss
        self.img = Image.new("RGBA", (self.w * ss, self.h * ss), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)

    def P(self, x, y):
        return (x * self.ss, y * self.ss)

    def _pts(self, pts):
        s = self.ss
        return [(x * s, y * s) for x, y in pts]

    def poly(self, pts, fill=None, outline=None, w=0):
        P = self._pts(pts)
        if fill is not None:
            self.d.polygon(P, fill=fill)
        if outline is not None and w:
            self.d.line(P + [P[0]], fill=outline, width=max(1, int(w * self.ss)), joint="curve")

    def linha(self, pts, cor, w=3, cap=True):
        P = self._pts(pts)
        self.d.line(P, fill=cor, width=max(1, int(w * self.ss)), joint="curve")
        if cap:
            r = w * self.ss / 2
            for x, y in (P[0], P[-1]):
                self.d.ellipse([x - r, y - r, x + r, y + r], fill=cor)

    def rect(self, x0, y0, x1, y1, fill=None, r=0, outline=None, w=0):
        a, b = self.P(x0, y0), self.P(x1, y1)
        if r:
            self.d.rounded_rectangle([a, b], radius=r * self.ss, fill=fill, outline=outline, width=int(w * self.ss))
        else:
            self.d.rectangle([a, b], fill=fill, outline=outline, width=int(w * self.ss))

    def elipse(self, cx, cy, rx, ry=None, fill=None, outline=None, w=0):
        ry = rx if ry is None else ry
        self.d.ellipse([self.P(cx - rx, cy - ry), self.P(cx + rx, cy + ry)], fill=fill, outline=outline,
                       width=int(w * self.ss))

    def arco(self, cx, cy, r, a0, a1, cor, w=4):
        self.d.arc([self.P(cx - r, cy - r), self.P(cx + r, cy + r)], a0, a1, fill=cor, width=max(1, int(w * self.ss)))

    def texto(self, x, y, s, nome, tam, cor, anchor="la", stroke=0, stroke_fill=None):
        self.d.text(self.P(x, y), s, font=fonte(nome, tam * self.ss), fill=cor, anchor=anchor,
                    stroke_width=int(stroke * self.ss), stroke_fill=stroke_fill)

    def largura(self, s, nome, tam):
        return self.d.textlength(s, font=fonte(nome, tam * self.ss)) / self.ss

    def texto_esp(self, x, y, s, nome, tam, cor, esp=0.0, anchor="l"):
        """texto com espacamento extra entre letras (esp em px logicos); anchor l|m|r (linha de base 'm' vertical)"""
        larg = sum(self.largura(c, nome, tam) for c in s) + esp * (len(s) - 1)
        x0 = x if anchor == "l" else x - larg / 2 if anchor == "m" else x - larg
        for c in s:
            self.d.text(self.P(x0, y), c, font=fonte(nome, tam * self.ss), fill=cor, anchor="lm")
            x0 += self.largura(c, nome, tam) + esp
        return larg

    def poly_grad(self, pts, c0, c1, y0=None, y1=None):
        """poligono preenchido com degrade vertical c0 (topo) -> c1 (base); y0/y1 em px logicos (opcional)"""
        P = self._pts(pts)
        xs, ys = [p[0] for p in P], [p[1] for p in P]
        bx0, by0, bx1, by1 = int(min(xs)) - 1, int(min(ys)) - 1, int(max(xs)) + 2, int(max(ys)) + 2
        m = Image.new("L", (bx1 - bx0, by1 - by0), 0)
        ImageDraw.Draw(m).polygon([(x - bx0, y - by0) for x, y in P], fill=255)
        ya = y0 * self.ss if y0 is not None else by0
        yb = y1 * self.ss if y1 is not None else by1
        g = Image.new("RGB", (1, by1 - by0))
        g.putdata([mix(c0, c1, (by0 + j - ya) / max(1.0, yb - ya)) for j in range(by1 - by0)])
        self.img.paste(g.resize((bx1 - bx0, by1 - by0)), (bx0, by0), m)

    def forma_grad(self, mask_L, x, y, c0, c1):
        """cola um degrade vertical usando uma mascara L (em px logicos) na posicao x,y"""
        w, h = mask_L.size
        g = degradado(1, max(2, h), [(0, c0), (1, c1)]).resize((w, h))
        m = mask_L.resize((int(w * self.ss), int(h * self.ss)), Image.BILINEAR) if self.ss != 1 else mask_L
        g = g.resize(m.size)
        self.img.paste(g, (int(x * self.ss), int(y * self.ss)), m)

    def colar(self, rgba, x, y):
        """alpha-composite de uma imagem RGBA (em resolucao logica) na posicao logica x,y"""
        if self.ss != 1:
            rgba = rgba.resize((rgba.width * self.ss, rgba.height * self.ss), Image.BILINEAR)
        ox, oy = int(x * self.ss), int(y * self.ss)
        self._composite(rgba, ox, oy)

    def _composite(self, rgba, ox, oy):
        W, H = self.img.size
        ax0, ay0 = max(0, ox), max(0, oy)
        ax1, ay1 = min(W, ox + rgba.width), min(H, oy + rgba.height)
        if ax1 <= ax0 or ay1 <= ay0:
            return
        src = rgba.crop((ax0 - ox, ay0 - oy, ax1 - ox, ay1 - oy))
        base = self.img.crop((ax0, ay0, ax1, ay1))
        self.img.paste(Image.alpha_composite(base, src), (ax0, ay0))
        self.d = ImageDraw.Draw(self.img)

    def pronto(self):
        return self.img.reduce(self.ss) if self.ss > 1 else self.img
