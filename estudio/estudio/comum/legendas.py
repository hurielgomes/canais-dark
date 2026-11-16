"""
legendas.py - legenda 'sem caixa' com palavra-chave colorida e palavra ativa em destaque (preset alerta_noturno).

* O texto do trecho aparece de uma vez; cada palavra "bate" (pop) quando e falada.
* Palavras-chave (`destaques`) ficam na cor de acento desde o inicio.
* Legibilidade vem de sombra suave + faixa de escurecimento na base do quadro (nao de uma caixa).
* AREAS_SEGURAS: onde a legenda pode ficar em cada formato (zonas de interface de Reels/TikTok/Shorts evitadas).
"""
import math
import re
import unicodedata

from PIL import Image, ImageFilter

from ..cenas2d.pintura import Lona, degradado, fonte
from .tween import out_back, clamp

# fracoes do quadro: (y_centro_da_legenda, largura_maxima, tam_fonte_rel_a_menor_dimensao)
AREAS_SEGURAS = {
    "9x16": {"y": 0.805, "larg": 0.84, "tam": 0.066, "topo_ui": 0.10, "base_ui": 0.80},
    "16x9": {"y": 0.895, "larg": 0.62, "tam": 0.060, "topo_ui": 0.06, "base_ui": 0.88},
}


def _norm(s):
    s = unicodedata.normalize("NFD", s.lower())
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in s if unicodedata.category(c) != "Mn"))


def _marca_destaques(palavras, destaques):
    """marca (bool) as palavras que pertencem a alguma expressao-chave (aceita varias palavras)"""
    marcadas = [False] * len(palavras)
    nrm = [_norm(p) for p in palavras]
    for d in destaques or []:
        alvo = [_norm(x) for x in d.split()]
        n = len(alvo)
        for i in range(len(palavras) - n + 1):
            if nrm[i:i + n] == alvo:
                for j in range(i, i + n):
                    marcadas[j] = True
    return marcadas


_cache_scrim = {}


def faixa_base(frame_rgba, w, h, y0=0.62, forca=0.62):
    """escurece suavemente a parte de baixo do quadro (integra a legenda sem caixa)"""
    k = (w, h, y0, forca)
    if k not in _cache_scrim:
        ya = int(h * y0)
        a = Image.new("L", (1, h - ya))
        a.putdata([int(255 * forca * (j / max(1, h - ya - 1)) ** 1.6) for j in range(h - ya)])
        a = a.resize((w, h - ya))
        ov = Image.new("RGBA", (w, h), (0, 0, 6, 0))
        band = Image.new("RGBA", (w, h - ya), (0, 0, 6, 0))
        band.putalpha(a)
        ov.paste(band, (0, ya))
        _cache_scrim[k] = ov
    frame_rgba.alpha_composite(_cache_scrim[k])


def desenhar(frame_rgba, t, trechos, w, h, formato, destaques=None, cor_destaque=(255, 92, 92), ocultar=False):
    """desenha a legenda do instante t. trechos = [{ini, fim, texto}]"""
    atual = next((tr for tr in trechos if tr["ini"] <= t < tr["fim"]), None)
    if atual is None:
        return
    area = AREAS_SEGURAS[formato]
    u = min(w, h) / 1080.0
    tam = min(w, h) * area["tam"]
    palavras = atual["texto"].split()
    marc = _marca_destaques(palavras, destaques)
    pesos = [len(p) + 1.5 for p in palavras]
    total = sum(pesos)
    dur = atual["fim"] - atual["ini"]
    # instante de inicio de cada palavra (proporcional ao tamanho, como a voz)
    inicios, acum = [], 0.0
    for pw in pesos:
        inicios.append(atual["ini"] + dur * 0.92 * acum / total)
        acum += pw
    tmp = Lona(10, 10, 1)
    espaco = max(tmp.largura(" ", "forte", tam), tam * 0.30)
    maxw = w * area["larg"]
    linhas, cur, larg = [], [], 0.0
    for i, p in enumerate(palavras):
        wp = tmp.largura(p, "forte", tam)
        if cur and larg + espaco + wp > maxw:
            linhas.append((cur, larg))
            cur, larg = [], 0.0
        cur.append((i, p, wp))
        larg += (espaco if len(cur) > 1 else 0) + wp
    if cur:
        linhas.append((cur, larg))
    alt = tam * 1.22
    topo = h * area["y"] - len(linhas) * alt / 2
    fade = clamp((t - atual["ini"]) / 0.12) * clamp((atual["fim"] - t) / 0.10)
    ativa = max(i for i in range(len(palavras)) if inicios[i] <= t + 1e-6)
    W0, H0 = int(maxw + 4 * tam), int(len(linhas) * alt + 3 * tam)
    sombra = Lona(W0, H0, 1)
    texto = Lona(W0, H0, 2)
    ox, oy = (W0 - maxw) / 2, tam * 1.2
    y = oy
    for linha, lw in linhas:
        x = ox + (maxw - lw) / 2
        yy = y + alt / 2
        for i, p, wp in linha:
            u_p = (t - inicios[i]) / 0.20
            bump = math.sin(math.pi * clamp(u_p)) if 0 <= u_p <= 1 else 0.0
            esc = 1.0 + 0.045 * bump
            lev = -0.075 * tam * bump
            falada = inicios[i] <= t + 1e-6
            cor = cor_destaque if marc[i] else ((255, 255, 255) if falada else (196, 205, 230))
            sz = tam * esc
            cx = x + wp / 2
            sombra.texto(cx, yy + 0.07 * tam + lev, p, "forte", sz, (0, 0, 0, 255), anchor="mm")
            texto.texto(cx, yy + lev, p, "forte", sz, cor + (255,), anchor="mm")
            x += wp + espaco
        y += alt
    sh = sombra.pronto().filter(ImageFilter.GaussianBlur(0.16 * tam))
    sh.putalpha(sh.getchannel("A").point(lambda v: min(255, int(v * 1.5))))
    img = texto.pronto()
    X, Y = int(w / 2 - W0 / 2), int(topo - oy + 0)
    if fade < 0.999:
        for im in (sh, img):
            im.putalpha(im.getchannel("A").point(lambda v, f=fade: int(v * f)))
    frame_rgba.alpha_composite(sh, dest=(X, Y)) if X >= 0 and Y >= 0 else _cola(frame_rgba, sh, X, Y)
    _cola(frame_rgba, img, X, Y)


def _cola(frame, img, x, y):
    W, H = frame.size
    ax0, ay0, ax1, ay1 = max(0, x), max(0, y), min(W, x + img.width), min(H, y + img.height)
    if ax1 > ax0 and ay1 > ay0:
        frame.alpha_composite(img.crop((ax0 - x, ay0 - y, ax1 - x, ay1 - y)), dest=(ax0, ay0))
