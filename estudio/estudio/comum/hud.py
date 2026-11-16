"""
hud.py - elementos de interface (HUD) minimos para o motor Cenas 2D.

Todos desenham em uma Lona pequena (so a area do elemento) e devolvem RGBA; `colar()` aplica
posicao/rotacao/escala/opacidade animadas no quadro. Funcoes puras de t (o progresso `p` vem de tween.tw).
"""
import math

from PIL import Image, ImageFilter

from ..cenas2d.pintura import Lona, alfa, fonte, mix, sombra


def colar(frame_rgba, img, cx, cy, ang=0.0, esc=1.0, opac=1.0, ancora=(0.5, 0.5)):
    """cola `img` (RGBA) centrada em (cx,cy) com rotacao (graus), escala e opacidade. ancora = ponto de pivo (0..1)."""
    if opac <= 0.003 or esc <= 0.003:
        return
    w, h = img.size
    if abs(esc - 1.0) > 0.003:
        img = img.resize((max(1, int(w * esc)), max(1, int(h * esc))), Image.BICUBIC)
        w, h = img.size
    if abs(ang) > 0.05:
        img = img.rotate(ang, resample=Image.BICUBIC, expand=True)
        w2, h2 = img.size
        ox, oy = (w2 - w) / 2.0, (h2 - h) / 2.0
    else:
        w2, h2, ox, oy = w, h, 0.0, 0.0
    if opac < 0.999:
        a = img.getchannel("A").point(lambda v: int(v * opac))
        img = img.copy()
        img.putalpha(a)
    x0 = int(round(cx - w2 * ancora[0]))
    y0 = int(round(cy - h2 * ancora[1]))
    W, H = frame_rgba.size
    ax0, ay0, ax1, ay1 = max(0, x0), max(0, y0), min(W, x0 + w2), min(H, y0 + h2)
    if ax1 <= ax0 or ay1 <= ay0:
        return
    frame_rgba.alpha_composite(img.crop((ax0 - x0, ay0 - y0, ax1 - x0, ay1 - y0)), dest=(ax0, ay0))


def chip_relogio(u, hora, dia, t, acento=(255, 77, 79), tema=None):
    """pilula '● 22:10  SEXTA' (ponto pulsa). Retorna RGBA."""
    th = tema or {}
    fundo = th.get("chip_fundo", (10, 14, 32, 215))
    borda = th.get("chip_borda", (255, 255, 255, 46))
    txt = th.get("texto", (244, 247, 255, 255))
    mudo = th.get("mudo", (150, 163, 196, 255))
    ts = 34 * u
    tmp = Lona(10, 10, 1)
    wh = tmp.largura(hora, "preto", ts)
    wd = tmp.largura(dia, "semi", ts * 0.62) + len(dia) * 2.2 * u if dia else 0
    pad, dot = 26 * u, 15 * u
    W = int(pad + dot + 16 * u + wh + (18 * u + wd if dia else 0) + pad)
    H = int(ts * 1.95)
    m = int(24 * u)
    L = Lona(W + 2 * m, H + 2 * m, 2)
    sh = Lona(W + 2 * m, H + 2 * m, 1)
    sh.rect(m, m + 6 * u, m + W, m + H + 6 * u, fill=(0, 0, 0, 150), r=H / 2)
    sombra_img = sh.pronto().filter(ImageFilter.GaussianBlur(10 * u))
    L.img.paste(sombra_img.resize(L.img.size, Image.BILINEAR), (0, 0))
    L.rect(m, m, m + W, m + H, fill=fundo, r=H / 2, outline=borda, w=max(1.5, 1.6 * u))
    pulso = 0.55 + 0.45 * (0.5 + 0.5 * math.sin(t * 5.2))
    cx0, cy0 = m + pad + dot / 2, m + H / 2
    L.elipse(cx0, cy0, dot * 1.15, fill=alfa(acento, 0.18 * pulso))
    L.elipse(cx0, cy0, dot / 2, fill=alfa(acento, 0.55 + 0.45 * pulso))
    x = m + pad + dot + 16 * u
    L.texto(x, m + H / 2 + 1 * u, hora, "preto", ts, txt, anchor="lm")
    if dia:
        L.texto_esp(x + wh + 18 * u, m + H / 2 + 1 * u, dia, "semi", ts * 0.62, mudo, esp=2.2 * u, anchor="l")
    return L.pronto(), m


def etiqueta(u, texto, fundo=(255, 77, 79), cor_texto=(255, 255, 255), tam=46, subtexto=None, forma="pilula"):
    """sticker com leve volume (sombra de contato + brilho no topo). Retorna RGBA (margens incluidas)."""
    ts = tam * u
    tmp = Lona(10, 10, 1)
    wt = tmp.largura(texto, "preto", ts)
    ws = tmp.largura(subtexto, "semi", ts * 0.5) if subtexto else 0
    W = int(max(wt, ws) + ts * 1.5)
    H = int(ts * (1.7 if not subtexto else 2.5))
    m = int(30 * u)
    L = Lona(W + 2 * m, H + 2 * m, 2)
    sh = Lona(W + 2 * m, H + 2 * m, 1)
    sh.rect(m, m + 9 * u, m + W, m + H + 9 * u, fill=(0, 0, 0, 170), r=ts * 0.34)
    L.img.paste(sh.pronto().filter(ImageFilter.GaussianBlur(9 * u)).resize(L.img.size, Image.BILINEAR), (0, 0))
    r = ts * 0.34
    base = Lona(W, H, 2)
    base.rect(0, 0, W, H, fill=fundo + (255,), r=r)
    # degrade: topo mais claro (volume)
    topo = mix(fundo, (255, 255, 255), 0.22)
    base2 = Lona(W, H, 2)
    base2.poly_grad([(0, 0), (W, 0), (W, H), (0, H)], topo, mix(fundo, (0, 0, 0), 0.22))
    mask = base.pronto().getchannel("A")
    g = base2.pronto().convert("RGB")
    L.img.paste(g.resize((W * 2, H * 2), Image.BILINEAR), (m * 2, m * 2), mask.resize((W * 2, H * 2), Image.BILINEAR))
    L.rect(m + 3 * u, m + 3 * u, m + W - 3 * u, m + H * 0.46, fill=(255, 255, 255, 26), r=r * 0.8)
    cy = m + H / 2 - (ts * 0.26 if subtexto else 0)
    L.texto(m + W / 2, cy, texto, "preto", ts, cor_texto + (255,), anchor="mm")
    if subtexto:
        L.texto(m + W / 2, m + H / 2 + ts * 0.62, subtexto, "semi", ts * 0.5, alfa(cor_texto, 0.82), anchor="mm")
    return L.pronto()


def chamada(frame_rgba, p0, p1, texto, p, u, cor=(255, 255, 255), tam=26, detalhe=None):
    """linha-guia de p0 (alvo) ate p1 (etiqueta de texto); p = 0..1 desenha a linha e depois revela o texto."""
    if p <= 0:
        return
    pl = min(1.0, p / 0.55)
    pt = max(0.0, (p - 0.45) / 0.55)
    x0, y0 = p0
    x1, y1 = p1
    xe, ye = x0 + (x1 - x0) * pl, y0 + (y1 - y0) * pl
    W, H = frame_rgba.size
    L = Lona(W, H, 1)
    L.linha([(x0, y0), (xe, ye)], alfa(cor, 0.9), w=max(2, 2.5 * u), cap=False)
    L.elipse(x0, y0, 9 * u, fill=alfa(cor, 1.0))
    L.elipse(x0, y0, 17 * u * (1 + 0.15 * math.sin(p * 9)), outline=alfa(cor, 0.5), w=max(1.5, 2 * u))
    frame_rgba.alpha_composite(L.pronto())
    if pt > 0:
        ts = tam * u
        tmp = Lona(10, 10, 1)
        wt = max(tmp.largura(texto, "forte", ts), tmp.largura(detalhe or "", "medio", ts * 0.72))
        bw, bh = wt + ts * 1.1, ts * (1.9 if detalhe else 1.5)
        T = Lona(int(bw + 6), int(bh + 6), 2)
        T.rect(3, 3, 3 + bw, 3 + bh, fill=(8, 11, 26, 235), r=ts * 0.28, outline=alfa(cor, 0.55), w=max(1.5, 1.8 * u))
        T.texto(3 + bw / 2, 3 + bh / 2 - (ts * 0.28 if detalhe else 0), texto, "forte", ts, cor + (255,), anchor="mm")
        if detalhe:
            T.texto(3 + bw / 2, 3 + bh / 2 + ts * 0.46, detalhe, "medio", ts * 0.72, (170, 182, 214, 255), anchor="mm")
        ox = 0.0 if x1 >= x0 else 1.0
        colar(frame_rgba, T.pronto(), x1, y1, esc=0.9 + 0.1 * pt, opac=pt, ancora=(ox, 0.5))


def numero_grande(u, texto, tam, cor, extrusao=9, brilho=0.55, nome="preto", claro=0.38):
    """numeral dominante: face em degrade, extrusao escura (volume), contorno e brilho. Retorna RGBA."""
    ts = tam * u
    tmp = Lona(10, 10, 1)
    wt = tmp.largura(texto, nome, ts)
    m = int(ts * 0.42)
    W, H = int(wt + 2 * m), int(ts * 1.2 + 2 * m + extrusao * u)
    cx, cy = W / 2, m + ts * 0.62
    # brilho (halo colorido atras)
    G = Lona(W, H, 1)
    G.texto(cx, cy, texto, nome, ts, alfa(cor, 0.95), anchor="mm", stroke=ts * 0.05, stroke_fill=alfa(cor, 0.9))
    halo = G.pronto().filter(ImageFilter.GaussianBlur(ts * 0.10))
    halo.putalpha(halo.getchannel("A").point(lambda v, k=brilho: int(min(255, v * k * 1.6))))
    out = halo
    # extrusao
    E = Lona(W, H, 2)
    esc = mix(cor, (0, 0, 0), 0.72)
    for i in range(int(extrusao * u), 0, -1):
        E.texto(cx, cy + i, texto, nome, ts, esc + (255,), anchor="mm", stroke=ts * 0.018, stroke_fill=esc + (255,))
    out.alpha_composite(E.pronto())
    # face: mascara do texto + degrade
    M = Lona(W, H, 2)
    M.texto(cx, cy, texto, nome, ts, (255, 255, 255, 255), anchor="mm")
    mask = M.pronto().getchannel("A")
    topo, base = mix(cor, (255, 255, 255), claro), mix(cor, (0, 0, 0), 0.10)
    g = Image.new("RGB", (1, H))
    g.putdata([mix(topo, base, max(0.0, min(1.0, (j - (cy - ts * 0.42)) / (ts * 0.84)))) for j in range(H)])
    face = g.resize((W, H)).convert("RGBA")
    face.putalpha(mask)
    out.alpha_composite(face)
    # fio de luz no topo das letras
    hl = Lona(W, H, 2)
    hl.texto(cx, cy - 2 * u, texto, nome, ts, (255, 255, 255, 0), anchor="mm", stroke=0)
    return out


def pilula(u, texto, cor, tam=30, preenchida=False, mudo=(150, 163, 196)):
    """pilula de estado:  ● ENCHENDO   (ponto na cor do estado)"""
    ts = tam * u
    tmp = Lona(10, 10, 1)
    wt = tmp.largura(texto, "forte", ts) + len(texto) * 2.4 * u
    m = int(20 * u)
    W, H = int(wt + ts * 2.3), int(ts * 1.8)
    L = Lona(W + 2 * m, H + 2 * m, 2)
    L.rect(m, m, m + W, m + H, fill=(9, 13, 30, 225), r=H / 2, outline=alfa(cor, 0.65), w=max(1.6, 2 * u))
    L.elipse(m + ts * 0.95, m + H / 2, ts * 0.52, fill=mix((9, 13, 30), cor, 0.28) + (255,))
    L.elipse(m + ts * 0.95, m + H / 2, ts * 0.27, fill=cor + (255,))
    L.texto_esp(m + ts * 1.55, m + H / 2 + 1, texto, "forte", ts, (236, 241, 255, 255), esp=2.4 * u, anchor="l")
    return L.pronto()
