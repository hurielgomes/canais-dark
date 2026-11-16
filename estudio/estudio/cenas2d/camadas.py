"""
camadas.py - sistema de camadas do motor Cenas 2D.

Ideia central
-------------
* Cada elemento visual e um SPRITE: imagem RGBA + posicao no quadro (px). Sprites estaticos sao desenhados uma
  unica vez ao montar a cena; os animados sao redesenhados a cada quadro (so a regiao que ocupam).
* Cada sprite pertence a uma CAMADA de profundidade k (0 = fundo distante, 1 = plano do heroi, >1 = primeiro plano).
* A camera 2D tem pan (px) e zoom. Cada camada reage de forma diferente: camadas proximas se movem/aproximam
  mais -> PARALLAX e sensacao de profundidade.
* Tudo e funcao pura de t; nenhum estado entre quadros.

Custo: cada sprite e reamostrado com Image.resize(box=...) apenas na area que ocupa (subpixel, sem tremor).
"""
import math

from PIL import Image, ImageChops, ImageFilter

from .pintura import brilho_mask, luz_aditiva


class Sprite:
    """imagem RGBA + posicao (x, y) em pixels do quadro. Guarda a versao pre-multiplicada (sem halos ao reamostrar)."""
    __slots__ = ("pm", "x", "y", "w", "h")

    def __init__(self, rgba, x, y, recortar=True):
        if recortar:
            bb = rgba.getchannel("A").getbbox()
            if bb is None:
                bb = (0, 0, 1, 1)
            m = 2
            bb = (max(0, bb[0] - m), max(0, bb[1] - m), min(rgba.width, bb[2] + m), min(rgba.height, bb[3] + m))
            rgba = rgba.crop(bb)
            x, y = x + bb[0], y + bb[1]
        self.pm = rgba.convert("RGBa")
        self.x, self.y, self.w, self.h = x, y, rgba.width, rgba.height


class Mundo:
    """quadro em construcao: camera + composicao de camadas, luzes e pos-processamento"""

    def __init__(self, w, h, base_rgb=(0, 0, 0)):
        self.w, self.h = w, h
        self.frame = Image.new("RGBA", (w, h), tuple(base_rgb) + (255,))
        self.pan = (0.0, 0.0)
        self.zoom = 1.0
        self.cx, self.cy = w / 2.0, h / 2.0

    # --- camera -----------------------------------------------------------
    def camera(self, pan=(0.0, 0.0), zoom=1.0, centro=None):
        self.pan, self.zoom = pan, zoom
        if centro:
            self.cx, self.cy = centro

    def transf(self, k):
        """(escala, desloc_x, desloc_y) da camada de profundidade k. k=0 quase parada; k grande move/aproxima mais"""
        zk = 0.15 + 0.85 * min(k, 1.6) / 1.0 if k > 0 else 0.0
        s = 1.0 + (self.zoom - 1.0) * zk
        return s, -self.pan[0] * k, -self.pan[1] * k

    def ponto(self, k, x, y):
        s, sx, sy = self.transf(k)
        return self.cx + (x - self.cx) * s + sx, self.cy + (y - self.cy) * s + sy

    # --- composicao -------------------------------------------------------
    def camada(self, sprites, k, suave=False):
        if not isinstance(sprites, (list, tuple)):
            sprites = [sprites]
        s, sx, sy = self.transf(k)
        rs = Image.BILINEAR if suave or k < 0.5 else Image.BICUBIC
        W, H = self.w, self.h
        for sp in sprites:
            if sp is None:
                continue
            X0 = self.cx + (sp.x - self.cx) * s + sx
            Y0 = self.cy + (sp.y - self.cy) * s + sy
            X1 = self.cx + (sp.x + sp.w - self.cx) * s + sx
            Y1 = self.cy + (sp.y + sp.h - self.cy) * s + sy
            dx0, dy0 = max(0, int(math.floor(X0))), max(0, int(math.floor(Y0)))
            dx1, dy1 = min(W, int(math.ceil(X1))), min(H, int(math.ceil(Y1)))
            if dx1 <= dx0 or dy1 <= dy0:
                continue
            ux0 = (dx0 - self.cx - sx) / s + self.cx - sp.x
            uy0 = (dy0 - self.cy - sy) / s + self.cy - sp.y
            ux1 = (dx1 - self.cx - sx) / s + self.cx - sp.x
            uy1 = (dy1 - self.cy - sy) / s + self.cy - sp.y
            ux0, uy0 = max(0.0, ux0), max(0.0, uy0)
            ux1, uy1 = min(float(sp.w), ux1), min(float(sp.h), uy1)
            if ux1 - ux0 < 0.5 or uy1 - uy0 < 0.5:
                continue
            peca = sp.pm.resize((dx1 - dx0, dy1 - dy0), rs, box=(ux0, uy0, ux1, uy1)).convert("RGBA")
            self.frame.alpha_composite(peca, dest=(dx0, dy0))

    def luz(self, k, x, y, r, cor, intens=1.0, expo=2.0, ry=None):
        """luz ADITIVA presa a camada k (acompanha o parallax e o zoom)"""
        X, Y = self.ponto(k, x, y)
        s = self.transf(k)[0]
        luz_aditiva(self.frame, X, Y, r * s, cor, intens, expo, None if ry is None else ry * s)

    def cobrir(self, rgba_cor, a):
        """cobre o quadro inteiro com cor/alfa (fades, flashes)"""
        if a <= 0:
            return
        ov = Image.new("RGBA", self.frame.size, tuple(rgba_cor[:3]) + (int(255 * min(1.0, a)),))
        self.frame.alpha_composite(ov)

    def rgb(self):
        return self.frame.convert("RGB")


# ====================================================================== pos-processamento
_cache_vig = {}


def vinheta(frame_rgb, forca=0.55, raio=1.05):
    k = (frame_rgb.size, forca, raio)
    if k not in _cache_vig:
        w, h = frame_rgb.size
        m = brilho_mask(int(max(w, h) * raio * 0.5), 1.0).resize((w, h), Image.BILINEAR)
        # centro claro (255) -> sem escurecer; borda (0) -> escurece ate `forca`
        alfa = m.point(lambda v: int(255 * forca * (1 - v / 255.0)))
        ov = Image.new("RGBA", (w, h), (0, 0, 4, 0))
        ov.putalpha(alfa)
        _cache_vig[k] = ov
    out = frame_rgb.convert("RGBA")
    out.alpha_composite(_cache_vig[k])
    return out.convert("RGB")


def bloom(frame_rgb, limiar=150, ganho=1.2, niveis=((6, 5), (12, 7))):
    """brilho suave em volta das areas claras (barato: trabalha em baixa resolucao)"""
    w, h = frame_rgb.size
    lut = [min(255, int(max(0, v - limiar) * ganho * (255.0 / max(1, 255 - limiar)))) for v in range(256)]
    soma = None
    for div, raio in niveis:
        peq = frame_rgb.resize((max(8, w // div), max(8, h // div)), Image.BILINEAR)
        peq = peq.point(lut * 3).filter(ImageFilter.GaussianBlur(raio))
        gr = peq.resize((w, h), Image.BICUBIC)
        soma = gr if soma is None else ImageChops.add(soma, gr)
    return ImageChops.screen(frame_rgb, soma)


_lut_grade = {}


def grade(frame_rgb, contraste=1.08, saturacao=1.0, tint=(0, 0, 0)):
    """curva de contraste suave (S) com leve tint nas sombras"""
    k = (contraste, tint)
    if k not in _lut_grade:
        lut = []
        for c in range(3):
            for v in range(256):
                u = v / 255.0
                u = 0.5 + (u - 0.5) * contraste
                u = u + (1 - u) * (tint[c] / 255.0) * (1 - v / 255.0)
                lut.append(int(max(0, min(255, u * 255))))
        _lut_grade[k] = lut
    return frame_rgb.point(_lut_grade[k])


_cache_grao = {}


def grao(frame_rgb, forca=6, semente=0):
    """textura de ruido (tile pre-computado) - da 'filme' e evita faixas nos degrades escuros"""
    import random
    w, h = frame_rgb.size
    if (w, h) not in _cache_grao:
        rnd = random.Random(7)
        tile = Image.new("L", (256, 256))
        tile.putdata([rnd.randint(0, 255) for _ in range(256 * 256)])
        _cache_grao[(w, h)] = [tile, Image.new("L", (w, h))]
    tile = _cache_grao[(w, h)][0]
    ox, oy = (semente * 37) % 256, (semente * 91) % 256
    t2 = ImageChops.offset(tile, ox, oy)
    ruido = Image.new("L", (w, h))
    for yy in range(0, h, 256):
        for xx in range(0, w, 256):
            ruido.paste(t2, (xx, yy))
    ruido = ruido.point(lambda v, f=forca: 128 + int((v - 128) * f / 128.0))
    return ImageChops.add(frame_rgb, Image.merge("RGB", (ruido, ruido, ruido)), scale=1.0, offset=-128)
