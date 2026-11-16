"""
cenarios.py - fundos procedurais do preset `alerta_noturno` (nenhuma imagem externa).
Cada funcao devolve imagens RGBA (a serem embrulhadas em Sprite) ou desenha em uma Lona.
"""
import math
import random

from PIL import Image, ImageFilter

from .pintura import Lona, alfa, brilho_sprite, degradado, mix, suavizar

# --------------------------------------------------------------------------- paleta do preset
PAL = {
    "bg0": (6, 8, 18), "bg1": (11, 15, 34), "bg2": (21, 28, 60), "bg3": (34, 44, 88),
    "lua": (178, 198, 245), "alerta": (255, 77, 79), "alerta_claro": (255, 120, 112),
    "ambar": (255, 190, 92), "ciano": (92, 204, 255), "branco": (240, 244, 255), "mudo": (150, 163, 196),
    "agua": (60, 170, 255), "verde": (70, 214, 150),
}


def parede(w, h, topo=None, base=None):
    topo = topo or PAL["bg2"]
    base = base or PAL["bg0"]
    return degradado(w, h, [(0, topo), (0.55, mix(topo, base, 0.55)), (1, base)]).convert("RGBA")


def ceu(w, h, estrelas=90, seed=1, horizonte=None):
    """gradiente de ceu noturno com estrelas estaticas (as que piscam sao desenhadas por quadro)"""
    img = degradado(w, h, [(0, (9, 12, 30)), (0.6, (20, 28, 66)), (1, (52, 62, 112))]).convert("RGBA")
    rnd = random.Random(seed)
    L = Lona(w, h, 1)
    for _ in range(estrelas):
        x, y = rnd.uniform(0, w), rnd.uniform(0, h * 0.78)
        a = rnd.uniform(0.25, 0.85)
        r = rnd.choice([0.7, 0.9, 1.1, 1.4])
        L.elipse(x, y, r, fill=(220, 230, 255, int(255 * a)))
    img.alpha_composite(L.pronto())
    return img


def estrelas_piscando(w, h, t, n=26, seed=9, area=None):
    """estrelas que cintilam (RGBA do tamanho de `area`=(x0,y0,x1,y1) ou do quadro)"""
    x0, y0, x1, y1 = area or (0, 0, w, h)
    L = Lona(x1 - x0, y1 - y0, 1)
    rnd = random.Random(seed)
    for i in range(n):
        x, y = rnd.uniform(0, x1 - x0), rnd.uniform(0, (y1 - y0) * 0.8)
        f = rnd.uniform(0.8, 2.2)
        a = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(t * f * 2.2 + i * 1.9))
        r = rnd.choice([1.1, 1.5, 1.9])
        L.elipse(x, y, r * 1.8, fill=(190, 210, 255, int(40 * a)))
        L.elipse(x, y, r, fill=(240, 245, 255, int(235 * a)))
    return L.pronto(), x0, y0


def lua(r, cor=None):
    """disco da lua com crateras suaves e halo (RGBA)"""
    cor = cor or PAL["lua"]
    m = int(r * 3.3)
    L = Lona(int(2 * r + 2 * m), int(2 * r + 2 * m), 2)
    cx = cy = r + m
    L.elipse(cx, cy, r, fill=cor + (255,))
    L.elipse(cx - r * 0.32, cy - r * 0.18, r * 0.24, fill=mix(cor, (110, 130, 190), 0.5) + (120,))
    L.elipse(cx + r * 0.28, cy + r * 0.30, r * 0.17, fill=mix(cor, (110, 130, 190), 0.5) + (110,))
    L.elipse(cx + r * 0.22, cy - r * 0.36, r * 0.1, fill=mix(cor, (110, 130, 190), 0.5) + (95,))
    img = L.pronto()
    halo = brilho_sprite(int(r * 3.1), cor, 0.34, 2.2)
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.alpha_composite(halo, dest=(int(cx - halo.width / 2), int(cy - halo.height / 2)))
    out.alpha_composite(img)
    return out


# --------------------------------------------------------------------------- skyline
def skyline(w, h_faixa, seed=3, cor=(12, 16, 36), altura=(0.25, 0.85), larg=(60, 150), janela=(11, 16), passo=(26, 34), margem=0.0):
    """silhueta de predios (RGBA w x h_faixa, base no fundo) + lista de janelas [(x,y,w,h)]"""
    rnd = random.Random(seed)
    L = Lona(w, h_faixa, 2)
    janelas = []
    x = -rnd.uniform(0, 40)
    while x < w:
        bw = rnd.uniform(*larg)
        bh = h_faixa * rnd.uniform(*altura)
        tom = mix(cor, (30, 40, 80), rnd.uniform(0.0, 0.25))
        L.rect(x, h_faixa - bh, x + bw, h_faixa + 4, fill=tom + (255,))
        if rnd.random() < 0.3:                                   # antena
            L.rect(x + bw * 0.5 - 1.5, h_faixa - bh - 26, x + bw * 0.5 + 1.5, h_faixa - bh, fill=tom + (255,))
        jw, jh = janela
        px, py = passo
        yy = h_faixa - bh + 18
        while yy + jh < h_faixa - 10:
            xx = x + 12
            while xx + jw < x + bw - 8:
                if rnd.random() < 0.62:
                    janelas.append((xx, yy, jw, jh))
                xx += px * 0.62
            yy += py
        x += bw + rnd.uniform(-6, 10)
    return L.pronto(), janelas


def janelas_acesas(w, h_faixa, janelas, t, apagar_de, apagar_ate, seed=5, cor=None, base_alpha=0.92):
    """desenha as janelas acesas; entre apagar_de e apagar_ate vao apagando uma a uma (apagao)"""
    cor = cor or PAL["ambar"]
    L = Lona(w, h_faixa, 1)
    rnd = random.Random(seed)
    for i, (x, y, jw, jh) in enumerate(janelas):
        alvo = apagar_de + (apagar_ate - apagar_de) * rnd.random()
        if t >= alvo:
            if t < alvo + 0.12:                                   # ultimo lampejo
                a = 0.3 * (1 - (t - alvo) / 0.12)
            else:
                continue
        else:
            a = base_alpha * (0.78 + 0.22 * rnd.random())
        c = mix(cor, (255, 235, 190), rnd.random() * 0.4)
        L.rect(x, y, x + jw, y + jh, fill=c + (int(255 * a),))
    return L.pronto()


def piso_tabuas(w, h, y0, cor_topo, cor_base, sentido=1.0, seed=2):
    """chao em perspectiva simples (tabuas convergindo) a partir da linha y0"""
    hh = h - y0
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    g = degradado(w, hh, [(0, cor_topo), (1, cor_base)]).convert("RGBA")
    img.paste(g, (0, y0))
    L = Lona(w, h, 2)
    cx = w * 0.5
    fuga_y = y0 - hh * 0.9
    for k in range(-9, 10):
        xb = cx + k * w * 0.34
        L.linha([(cx + (xb - cx) * 0.06, y0), (xb, h + 20)], (0, 0, 0, 52), w=2.2, cap=False)
    for j in range(1, 7):
        yy = y0 + hh * (j / 7.0) ** 1.7
        L.linha([(0, yy), (w, yy)], (255, 255, 255, 9), w=1.5, cap=False)
    sup = L.pronto()
    img.alpha_composite(sup)
    # linha de encontro parede/piso
    ln = Lona(w, h, 2)
    ln.rect(0, y0 - 2, w, y0 + 4, fill=(0, 0, 0, 90))
    ln.rect(0, y0 + 4, w, y0 + 7, fill=(255, 255, 255, 14))
    img.alpha_composite(ln.pronto())
    return img


def particulas_poeira(w, h, t, area, n=34, seed=4, cor=(255, 255, 255), a_max=0.55, vel=14.0):
    """graos de poeira em suspensao dentro de uma area (x0,y0,x1,y1); retorna RGBA do tamanho da area + origem"""
    x0, y0, x1, y1 = area
    L = Lona(x1 - x0, y1 - y0, 1)
    rnd = random.Random(seed)
    for i in range(n):
        bx, by = rnd.uniform(0, x1 - x0), rnd.uniform(0, y1 - y0)
        ph = rnd.uniform(0, 6.28)
        x = bx + 18 * math.sin(t * 0.5 + ph) + vel * 0.4 * t * (1 if i % 2 else -1) % (x1 - x0) * 0
        y = (by - vel * t * rnd.uniform(0.3, 1.0)) % (y1 - y0)
        a = a_max * (0.35 + 0.65 * (0.5 + 0.5 * math.sin(t * 1.3 + ph)))
        r = rnd.choice([1.2, 1.6, 2.2, 2.8])
        L.elipse(x % (x1 - x0), y, r * 1.8, fill=alfa(cor, a * 0.18))
        L.elipse(x % (x1 - x0), y, r, fill=alfa(cor, a))
    return L.pronto(), x0, y0
