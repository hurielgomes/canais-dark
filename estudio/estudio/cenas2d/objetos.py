"""
objetos.py - biblioteca de objetos procedurais (formas e gradientes; nenhuma imagem externa).
Cada objeto e uma funcao que devolve RGBA (estatico) ou recebe o estado animado e redesenha.
"""
import math
import random

from PIL import Image, ImageFilter

from .cenarios import PAL
from .pintura import Lona, alfa, brilho_sprite, degradado, mascara_rrect, mix, sombra, suavizar

# ====================================================================== GELADEIRA
INOX0, INOX1 = (74, 86, 120), (40, 47, 76)


def geladeira(fw, fh, u, t, theta, luz, led=1.0, rim=0.8):
    """
    fridge de uma porta + freezer. theta = abertura da porta (graus), luz = brilho do interior (0..1),
    led = luz-piloto, rim = intensidade do contra-luz lunar na borda esquerda.
    Retorna (RGBA, y_porta_topo, y_porta_base, x_interior_centro) em coordenadas do sprite.
    """
    m = int(40 * u)
    W, H = int(fw + 2 * m), int(fh + 2 * m)
    L = Lona(W, H, 2)
    r = 24 * u
    # corpo
    L.poly_grad([(m, m + r), (m + r, m), (m + fw - r, m), (m + fw, m + r), (m + fw, m + fh), (m, m + fh)], INOX0, INOX1)
    L.rect(m, m, m + fw, m + fh, outline=(0, 0, 0, 120), w=2 * u, r=r)
    # reflexo vertical suave
    L.rect(m + fw * 0.12, m + 14 * u, m + fw * 0.2, m + fh - 14 * u, fill=(255, 255, 255, 20), r=8 * u)
    # contra-luz lunar na borda esquerda
    if rim > 0:
        L.rect(m, m + r, m + 5 * u, m + fh - 6 * u, fill=alfa(mix(PAL["lua"], (255, 255, 255), 0.3), 0.55 * rim))
        L.rect(m + 5 * u, m + r, m + 11 * u, m + fh - 6 * u, fill=alfa(PAL["lua"], 0.16 * rim))
    # divisoria freezer / refrigerador
    yd0 = m + fh * 0.30
    yd1 = m + fh - 16 * u
    L.rect(m, yd0 - 3 * u, m + fw, yd0 + 3 * u, fill=(0, 0, 0, 140))
    # ----- interior (visivel quando a porta abre)
    ix0, ix1 = m + 16 * u, m + fw - 16 * u
    iy0, iy1 = yd0 + 14 * u, yd1 - 8 * u
    cor_i0 = mix((14, 20, 38), (150, 200, 236), luz)
    cor_i1 = mix((10, 14, 30), (104, 150, 200), luz)
    L.poly_grad([(ix0, iy0), (ix1, iy0), (ix1, iy1), (ix0, iy1)], cor_i0, cor_i1)
    # prateleiras de vidro + itens
    n = 4
    for i in range(n):
        yy = iy0 + (iy1 - iy0) * (i + 1) / (n + 1)
        L.rect(ix0, yy, ix1, yy + 7 * u, fill=mix((30, 40, 70), (190, 225, 250), luz * 0.9) + (255,))
        L.rect(ix0, yy + 7 * u, ix1, yy + 12 * u, fill=(0, 0, 0, int(60 * luz)))
    rnd = random.Random(11)
    cores_i = [(255, 120, 100), (255, 200, 90), (120, 220, 170), (130, 170, 255), (240, 240, 250)]
    for i in range(n + 1):
        y_base = iy0 + (iy1 - iy0) * (i + 1) / (n + 1) if i < n else iy1
        x = ix0 + 14 * u
        while x < ix1 - 40 * u:
            ww = rnd.uniform(26, 56) * u
            hh = rnd.uniform(50, 92) * u
            c = rnd.choice(cores_i)
            c = mix((22, 28, 48), c, 0.25 + 0.75 * luz)
            if rnd.random() < 0.5:                                      # garrafa
                L.rect(x, y_base - hh, x + ww * 0.62, y_base, fill=c + (255,), r=7 * u)
                L.rect(x + ww * 0.18, y_base - hh - 16 * u, x + ww * 0.44, y_base - hh + 4 * u, fill=c + (255,), r=3 * u)
            else:                                                       # caixinha
                L.rect(x, y_base - hh * 0.7, x + ww, y_base, fill=c + (255,), r=4 * u)
            x += ww + rnd.uniform(10, 24) * u
    # sombra interna nas laterais (profundidade)
    L.rect(ix0, iy0, ix0 + 16 * u, iy1, fill=(0, 0, 0, int(90 - 40 * luz)))
    L.rect(ix1 - 16 * u, iy0, ix1, iy1, fill=(0, 0, 0, int(90 - 40 * luz)))
    # ----- porta principal em perspectiva (articulada no lado direito)
    th = math.radians(theta)
    xh = m + fw
    xf = xh - fw * math.cos(th) if theta > 0.01 else m
    xf = max(xf, m)
    e = (yd1 - yd0) * 0.05 * math.sin(th)
    quad = [(xf, yd0 - e), (xh, yd0), (xh, yd1), (xf, yd1 + e)]
    esc = 1 - 0.30 * math.sin(th)                                      # porta se "vira": escurece
    L.poly_grad(quad, mix(INOX0, (0, 0, 0), 1 - esc), mix(INOX1, (0, 0, 0), 1 - esc))
    L.poly(quad, outline=(0, 0, 0, 120), w=2 * u)
    if theta > 0.01:                                                    # espessura da porta (borda clara)
        L.poly([(xf, yd0 - e), (xf + 9 * u, yd0 - e * 0.9), (xf + 9 * u, yd1 + e * 0.9), (xf, yd1 + e)],
               fill=(190, 205, 235, 210))
        # sombra projetada pela porta no interior
        L.poly([(xf - 40 * u, yd0), (xf, yd0 - e), (xf, yd1 + e), (xf - 40 * u, yd1)], fill=(0, 0, 0, int(40 + 60 * (1 - luz))))
    # puxador (acompanha a borda livre)
    px = xf + 26 * u * math.cos(th)
    L.rect(px, yd0 + (yd1 - yd0) * 0.14, px + 10 * u * max(0.25, math.cos(th)), yd0 + (yd1 - yd0) * 0.42,
           fill=(214, 224, 244, 255), r=4 * u)
    # freezer (sempre fechado) + puxador
    L.rect(m + 26 * u, m + 28 * u, m + 36 * u, yd0 - 28 * u, fill=(214, 224, 244, 255), r=4 * u)
    # led piloto
    cor_led = mix((40, 20, 24), PAL["alerta"], led)
    L.elipse(m + fw - 38 * u, m + 36 * u, 6.5 * u, fill=cor_led + (255,))
    if led > 0.2:
        L.elipse(m + fw - 38 * u, m + 36 * u, 14 * u, fill=alfa(PAL["alerta"], 0.22 * led))
    # rodape
    L.rect(m + 14 * u, m + fh, m + fw - 14 * u, m + fh + 12 * u, fill=(10, 12, 24, 255), r=3 * u)
    return L.pronto(), m, (yd0, yd1), ((ix0 + xf) / 2.0)


# ====================================================================== TERMOMETRO
def termometro(h_tubo, u, nivel, t, quente=0.0):
    """termometro vertical; nivel 0..1 (altura do mercurio). Retorna (RGBA, (cx_bulbo, cy_bulbo), y_topo_mercurio)."""
    m = int(30 * u)
    tw_ = 56 * u
    rb = 52 * u
    W = int(tw_ + 2 * m + 120 * u)
    H = int(h_tubo + rb * 2 + 2 * m)
    L = Lona(W, H, 2)
    x0 = m + 30 * u
    cx = x0 + tw_ / 2
    y0 = m
    y1 = m + h_tubo
    cyb = y1 + rb * 0.55
    # vidro
    L.rect(x0, y0, x0 + tw_, y1 + rb * 0.4, fill=(210, 226, 255, 40), r=tw_ / 2, outline=(210, 226, 255, 130), w=2.4 * u)
    L.elipse(cx, cyb, rb, fill=(210, 226, 255, 40), outline=(210, 226, 255, 130), w=2.4 * u)
    # graduacao
    for i in range(11):
        yy = y1 - (h_tubo - 40 * u) * i / 10.0 - 10 * u
        comp = 26 * u if i % 5 == 0 else 14 * u
        L.linha([(x0 + tw_ + 10 * u, yy), (x0 + tw_ + 10 * u + comp, yy)], (200, 214, 245, 150 if i % 5 == 0 else 90), w=2.2 * u, cap=False)
    # mercurio
    cor = mix((255, 110, 100), (255, 60, 70), quente)
    top = y1 - (h_tubo - 40 * u) * nivel - 4 * u
    iw = tw_ * 0.46
    L.rect(cx - iw / 2, top, cx + iw / 2, y1 + rb * 0.5, fill=cor + (255,), r=iw / 2)
    L.elipse(cx, cyb, rb * 0.78, fill=cor + (255,))
    L.elipse(cx - rb * 0.22, cyb - rb * 0.22, rb * 0.2, fill=(255, 255, 255, 90))
    L.rect(cx - iw * 0.18, top + 8 * u, cx - iw * 0.04, y1, fill=(255, 255, 255, 70), r=3 * u)
    return L.pronto(), (cx - m + m, cyb), top


# ====================================================================== PLANTA (primeiro plano)
def planta(w, h, u, lado=-1, seed=6, cor=(8, 12, 26), borda=(120, 150, 235)):
    """folhagem escura de canto (para primeiro plano desfocado). lado -1 = canto esquerdo, +1 = direito"""
    rnd = random.Random(seed)
    L = Lona(w, h, 2)
    ox = 0 if lado < 0 else w
    oy = h
    for i in range(9):
        ang = math.radians(rnd.uniform(-78, -8)) if lado < 0 else math.radians(rnd.uniform(-172, -102))
        comp = rnd.uniform(0.55, 1.0) * h * 0.55
        larg = comp * rnd.uniform(0.14, 0.2)
        cx = ox + rnd.uniform(-20, 60) * lado * u
        pts = []
        for s in range(0, 21):
            f = s / 20.0
            curva = math.sin(f * math.pi) * larg
            px = cx + math.cos(ang) * comp * f
            py = oy + math.sin(ang) * comp * f
            nx, ny = -math.sin(ang), math.cos(ang)
            pts.append((px + nx * curva, py + ny * curva))
        for s in range(20, -1, -1):
            f = s / 20.0
            curva = math.sin(f * math.pi) * larg
            px = cx + math.cos(ang) * comp * f
            py = oy + math.sin(ang) * comp * f
            nx, ny = -math.sin(ang), math.cos(ang)
            pts.append((px - nx * curva * 0.9, py - ny * curva * 0.9))
        tom = mix(cor, (14, 22, 44), rnd.random() * 0.6)
        L.poly(pts, fill=tom + (255,))
        # nervura clara no topo da folha (contra-luz)
        L.linha(pts[:21], alfa(borda, 0.75), w=3.2 * u, cap=False)
    # vaso
    L.rect(ox - 120 * u if lado < 0 else ox - 120 * u, oy - 120 * u, ox + 120 * u if lado < 0 else ox + 120 * u, oy + 20, fill=cor + (255,), r=12 * u)
    return L.pronto().filter(ImageFilter.GaussianBlur(3.2 * u))


# ====================================================================== CAIXA D'AGUA
def _cor_nivel(n):
    """cor da agua conforme o nivel: vazio (coral) -> medio (ambar) -> cheio (azul)"""
    if n < 0.45:
        return mix(PAL["alerta"], PAL["ambar"], n / 0.45)
    return mix(PAL["ambar"], PAL["agua"], min(1.0, (n - 0.45) / 0.45))


def caixa_estrutura(tw_, th_, leg_h, u):
    """parte ESTATICA: pernas de aco, corpo de vidro escuro, tampa e flange. Retorna (RGBA, margem, (ix0,iy0,ix1,iy1) interior)."""
    m = int(40 * u)
    W, H = int(tw_ + 2 * m), int(th_ + leg_h + 2 * m)
    L = Lona(W, H, 2)
    x0, y0 = m, m
    # pernas (travessas em X)
    for fx in (0.14, 0.86):
        xx = x0 + tw_ * fx
        L.rect(xx - 9 * u, y0 + th_ - 6 * u, xx + 9 * u, y0 + th_ + leg_h + 4 * u, fill=(60, 72, 112, 255), r=3 * u)
        L.rect(xx - 9 * u, y0 + th_ - 6 * u, xx - 5 * u, y0 + th_ + leg_h + 4 * u, fill=(150, 170, 230, 90))
    L.linha([(x0 + tw_ * 0.14, y0 + th_ + 8 * u), (x0 + tw_ * 0.86, y0 + th_ + leg_h * 0.92)], (60, 72, 112, 255), w=6 * u, cap=False)
    L.linha([(x0 + tw_ * 0.86, y0 + th_ + 8 * u), (x0 + tw_ * 0.14, y0 + th_ + leg_h * 0.92)], (60, 72, 112, 255), w=6 * u, cap=False)
    # corpo
    r = 34 * u
    L.rect(x0, y0, x0 + tw_, y0 + th_, fill=(12, 19, 42, 255), r=r)
    ins = 16 * u
    inner = (x0 + ins, y0 + ins, x0 + tw_ - ins, y0 + th_ - ins)
    return L, m, inner, (x0, y0, tw_, th_, r, ins)


def caixa_moldura(L, geo, u):
    """arremates por cima da agua: vidro (reflexo), aro, tampa"""
    x0, y0, tw_, th_, r, ins = geo
    L.rect(x0, y0, x0 + tw_, y0 + th_, outline=(150, 176, 240, 170), w=4 * u, r=r)
    L.rect(x0 + ins * 0.6, y0 + ins * 0.6, x0 + tw_ - ins * 0.6, y0 + th_ - ins * 0.6, outline=(0, 0, 0, 70), w=2 * u, r=r * 0.8)
    # reflexos de vidro
    L.rect(x0 + tw_ * 0.10, y0 + th_ * 0.10, x0 + tw_ * 0.15, y0 + th_ * 0.88, fill=(255, 255, 255, 46), r=8 * u)
    L.rect(x0 + tw_ * 0.17, y0 + th_ * 0.16, x0 + tw_ * 0.19, y0 + th_ * 0.62, fill=(255, 255, 255, 30), r=4 * u)
    # tampa
    L.rect(x0 + tw_ * 0.30, y0 - 22 * u, x0 + tw_ * 0.70, y0 + 6 * u, fill=(72, 86, 134, 255), r=10 * u)
    L.rect(x0 + tw_ * 0.30, y0 - 22 * u, x0 + tw_ * 0.70, y0 - 14 * u, fill=(150, 170, 230, 130), r=6 * u)
    # abracadeiras
    for fy in (0.33, 0.66):
        L.rect(x0 - 5 * u, y0 + th_ * fy, x0 + tw_ + 5 * u, y0 + th_ * fy + 9 * u, fill=(60, 72, 112, 200), r=3 * u)


def agua(iw, ih, nivel, t, u, extra_brilho=0.0, formato_mask=None):
    """agua dentro da caixa (RGBA iw x ih): superficie com 2 ondas, bolhas e gradiente que clareia com o nivel"""
    L = Lona(iw, ih, 2)
    if nivel <= 0.002:
        return L.pronto()
    cor = _cor_nivel(nivel)
    topo = ih * (1 - nivel)
    amp = 7 * u * (1 - 0.55 * nivel) * (1.0 if nivel < 0.995 else 0.0)

    def onda(ph, a, fr):
        pts = [(x, topo + a * math.sin(x / (iw / fr) * 2 * math.pi + ph)) for x in range(0, iw + 8, 8)]
        return pts

    back = onda(t * 2.0 + 1.3, amp * 0.8, 1.6)
    frente = onda(-t * 2.6, amp, 1.15)
    clara = mix(cor, (255, 255, 255), 0.30)
    L.poly_grad(back + [(iw, ih), (0, ih)], alfa(clara, 0.0)[:3], mix(cor, (0, 0, 0), 0.25), y0=topo, y1=ih)
    L.poly(back + [(iw, ih), (0, ih)], fill=None)
    # faixa clara na superficie (espuma)
    L.linha(frente, mix(cor, (255, 255, 255), 0.55) + (230,), w=3.2 * u, cap=False)
    L.poly_grad(frente + [(iw, ih), (0, ih)], mix(cor, (255, 255, 255), 0.12), mix(cor, (0, 0, 0), 0.45), y0=topo, y1=ih)
    # bolhas
    rnd = random.Random(21)
    for i in range(14):
        bx = rnd.uniform(0.08, 0.92) * iw + 8 * u * math.sin(t * 1.6 + i)
        vel = rnd.uniform(0.18, 0.38)
        by = ih - ((t * vel + rnd.random()) % 1.0) * (ih - topo)
        if by > topo + 8 * u:
            rr = rnd.choice([3, 4.5, 6]) * u
            L.elipse(bx, by, rr, outline=(255, 255, 255, 130), w=1.6 * u)
    img = L.pronto()
    # brilho interno (a agua "acende" quando enche)
    if extra_brilho > 0.01:
        glow = Image.new("RGBA", img.size, tuple(mix(cor, (255, 255, 255), 0.4)) + (int(70 * extra_brilho),))
        a = img.getchannel("A")
        glow.putalpha(a.point(lambda v, k=extra_brilho: int(v * 0.28 * k)))
        img.alpha_composite(glow)
    if formato_mask is not None:
        a = ImageChops_mult(img.getchannel("A"), formato_mask)
        img.putalpha(a)
    return img


def ImageChops_mult(a, b):
    from PIL import ImageChops
    return ImageChops.multiply(a, b)


def bomba(u, t, ligada=1.0):
    """bomba com ventoinha girando (RGBA, centro em (w/2,h/2))"""
    W = H = int(190 * u)
    L = Lona(W, H, 2)
    cx = W / 2
    L.rect(cx - 62 * u, H * 0.50, cx + 62 * u, H * 0.90, fill=(54, 66, 108, 255), r=10 * u)
    L.rect(cx - 62 * u, H * 0.50, cx + 62 * u, H * 0.56, fill=(150, 170, 230, 120), r=6 * u)
    L.elipse(cx, H * 0.40, 46 * u, fill=(34, 42, 78, 255), outline=(150, 170, 230, 160), w=3 * u)
    ang = t * 7.0 * ligada
    for k in range(4):
        a = ang + k * math.pi / 2
        L.poly([(cx, H * 0.40), (cx + 38 * u * math.cos(a - 0.35), H * 0.40 + 38 * u * math.sin(a - 0.35)),
                (cx + 38 * u * math.cos(a + 0.35), H * 0.40 + 38 * u * math.sin(a + 0.35))], fill=(200, 220, 255, 235))
    L.elipse(cx, H * 0.40, 8 * u, fill=(255, 255, 255, 255))
    led = mix((60, 30, 34), PAL["verde"], ligada)
    L.elipse(cx + 40 * u, H * 0.70, 6 * u, fill=led + (255,))
    return L.pronto()


def selo_ok(d, p, cor=None):
    """selo circular com marca de verificacao que se desenha (p = 0..1)"""
    cor = cor or PAL["verde"]
    m = int(d * 0.25)
    L = Lona(int(d + 2 * m), int(d + 2 * m), 2)
    c = d / 2 + m
    L.elipse(c, c + d * 0.05, d / 2 + 2, fill=(0, 0, 0, 120))
    L.elipse(c, c, d / 2, fill=mix(cor, (0, 0, 0), 0.15) + (255,))
    L.elipse(c, c - d * 0.08, d / 2 * 0.86, fill=mix(cor, (255, 255, 255), 0.25) + (70,))
    pts = [(c - d * 0.24, c + d * 0.02), (c - d * 0.07, c + d * 0.20), (c + d * 0.26, c - d * 0.17)]
    seg1 = min(1.0, p / 0.45)
    seg2 = max(0.0, (p - 0.45) / 0.55)
    q1 = (pts[0][0] + (pts[1][0] - pts[0][0]) * seg1, pts[0][1] + (pts[1][1] - pts[0][1]) * seg1)
    ln = [pts[0], q1]
    if seg2 > 0:
        ln = [pts[0], pts[1], (pts[1][0] + (pts[2][0] - pts[1][0]) * seg2, pts[1][1] + (pts[2][1] - pts[1][1]) * seg2)]
    L.linha(ln, (255, 255, 255, 255), w=d * 0.12)
    return L.pronto()


# ====================================================================== PESSOA DE COSTAS
def pessoa_corpo(s, rim=(130, 215, 255), luz=1.0):
    """tronco + pescoco vistos de costas, com contra-luz (rim) no topo. s = escala. Retorna (RGBA, (cx, y_pescoco))."""
    W, H = int(820 * s), int(780 * s)
    cx, cy = W / 2, 300 * s
    L = Lona(W, H, 2)
    pts = [(-70, -40), (-150, -6), (-250, 38), (-318, 118), (-350, 230), (-362, 470), (362, 470), (350, 230), (318, 118), (250, 38), (150, -6), (70, -40)]
    pts = suavizar([(cx + x * s, cy + y * s) for x, y in pts], 3)
    L.poly(deslocar_pts(pts, 0, -7 * s), fill=alfa(rim, 0.85 * luz))                     # contra-luz (crescente no topo)
    L.poly(deslocar_pts(pts, 0, -14 * s), fill=alfa(rim, 0.22 * luz))
    L.poly_grad(pts, mix((16, 22, 48), (52, 70, 124), 0.55 * luz), (9, 12, 28), y0=cy - 40 * s, y1=cy + 300 * s)
    # costura/gola
    L.poly(suavizar([(cx - 60 * s, cy - 36 * s), (cx, cy - 6 * s), (cx + 60 * s, cy - 36 * s), (cx + 40 * s, cy - 52 * s), (cx - 40 * s, cy - 52 * s)], 2),
           fill=(26, 34, 70, 255))
    L.linha([(cx, cy - 6 * s), (cx, cy + 330 * s)], (0, 0, 0, 60), w=3 * s, cap=False)
    # pescoco
    L.rect(cx - 36 * s, cy - 150 * s, cx + 36 * s, cy - 30 * s, fill=(34, 42, 82, 255), r=14 * s)
    L.rect(cx - 36 * s, cy - 150 * s, cx - 30 * s, cy - 40 * s, fill=alfa(rim, 0.55 * luz), r=3 * s)
    return L.pronto(), (cx, cy)


def deslocar_pts(pts, dx, dy):
    return [(x + dx, y + dy) for x, y in pts]


def pessoa_cabeca(s, rim=(130, 215, 255), luz=1.0, giro=0.0):
    """cabeca de costas (cabelo) com contra-luz; giro -1..1 estreita/alarga a silhueta. Retorna (RGBA, (cx, cy))."""
    rx, ry = 90 * s * (1 - 0.10 * abs(giro)), 108 * s
    m = int(30 * s)
    W, H = int(2 * rx + 2 * m + 40 * s), int(2 * ry + 2 * m)
    L = Lona(W, H, 2)
    cx, cy = W / 2 + giro * 10 * s, H / 2
    L.elipse(cx, cy - 8 * s, rx, ry, fill=alfa(rim, 0.9 * luz))                           # crescente de luz
    L.elipse(cx, cy - 4 * s, rx, ry, fill=alfa(rim, 0.25 * luz))
    L.elipse(cx, cy, rx, ry, fill=(14, 18, 40, 255))
    # volume do cabelo (degrade + brilho)
    L.elipse(cx - rx * 0.25, cy - ry * 0.35, rx * 0.5, ry * 0.45, fill=(34, 44, 86, 130))
    L.elipse(cx - rx * 0.05, cy - ry * 0.55, rx * 0.62, ry * 0.30, fill=(60, 80, 150, 70))
    # orelhas
    L.elipse(cx - rx * 0.98, cy + 8 * s, 14 * s, 25 * s, fill=(36, 44, 84, 255))
    L.elipse(cx + rx * 0.98, cy + 8 * s, 14 * s, 25 * s, fill=(36, 44, 84, 255))
    return L.pronto(), (cx, cy)


# ====================================================================== TELA (celular/TV com chat)
def tela_chat(sw, sh, u, t, msgs, bateria, alerta=0.0, digitando=None):
    """conteudo da tela: cabecalho (avatar, nome, bateria) + balões que entram. msgs=[(t_ini, 'in'|'out', texto)]."""
    L = Lona(sw, sh, 2)
    L.poly_grad([(0, 0), (sw, 0), (sw, sh), (0, sh)], (22, 34, 62), (12, 20, 42))
    hb = sh * 0.13
    L.rect(0, 0, sw, hb, fill=(14, 24, 50, 255))
    L.elipse(hb * 0.55, hb / 2, hb * 0.27, fill=(86, 110, 170, 255))
    L.elipse(hb * 0.55, hb / 2 - hb * 0.07, hb * 0.1, fill=(200, 214, 245, 255))
    L.texto(hb * 1.0, hb * 0.40, "Família", "forte", hb * 0.30, (240, 245, 255, 255), anchor="lm")
    L.texto(hb * 1.0, hb * 0.72, "online", "medio", hb * 0.20, (110, 220, 170, 255), anchor="lm")
    # bateria
    bw, bh = hb * 0.80, hb * 0.34
    bx, by = sw - bw - hb * 0.45, hb / 2 - bh / 2
    cor_b = mix((255, 255, 255), PAL["alerta"], 0.35 + 0.65 * (0.5 + 0.5 * math.sin(t * 9)) * alerta + 0.0) if alerta > 0 else mix((255, 255, 255), PAL["alerta"], 0.8)
    L.rect(bx, by, bx + bw, by + bh, outline=cor_b + (255,), w=2.6 * u, r=bh * 0.22)
    L.rect(bx + bw + 2 * u, by + bh * 0.3, bx + bw + 7 * u, by + bh * 0.7, fill=cor_b + (255,), r=2 * u)
    L.rect(bx + 3.5 * u, by + 3.5 * u, bx + 3.5 * u + (bw - 7 * u) * bateria, by + bh - 3.5 * u, fill=PAL["alerta"] + (255,), r=bh * 0.14)
    L.texto(bx - 10 * u, hb / 2, f"{int(round(bateria * 100))}%", "forte", hb * 0.26, PAL["alerta_claro"] + (255,), anchor="rm")
    # baloes
    y = hb + sh * 0.05
    tam = sh * 0.062
    for (ti, lado, txt) in msgs:
        p = tw(t, ti, 0.45, "out_back")
        if p <= 0:
            y += tam * 2.0
            continue
        tmp = Lona(10, 10, 1)
        ww = tmp.largura(txt, "semi", tam) + tam * 1.1
        hh = tam * 1.7
        slide = (1 - p) * tam * 1.2
        x0 = tam * 0.8 if lado == "in" else sw - ww - tam * 0.8
        cor = (52, 66, 112) if lado == "in" else (36, 150, 104)
        a = clamp(p * 1.4)
        L.rect(x0, y + slide, x0 + ww, y + slide + hh, fill=cor + (int(255 * a),), r=hh * 0.45)
        L.texto(x0 + ww / 2, y + slide + hh / 2, txt, "semi", tam, (255, 255, 255, int(255 * a)), anchor="mm")
        y += hh + tam * 0.45
    if digitando is not None and digitando > 0:
        for i in range(3):
            fase = 0.5 + 0.5 * math.sin(t * 8 - i * 0.9)
            L.elipse(tam * 1.5 + i * tam * 0.85, y + tam * 0.9, tam * 0.22 * (0.7 + 0.5 * fase), fill=(180, 196, 232, int(255 * digitando * (0.4 + 0.6 * fase))))
    return L.pronto()


def clamp(v, a=0.0, b=1.0):
    return a if v < a else b if v > b else v


def tw(t, ini, dur, ease="out_cubic"):
    from ..comum.tween import tw as _tw
    return _tw(t, ini, dur, ease)


# ====================================================================== MESA COM VELA
def mesa_vela(u, t):
    """mesinha lateral com vela acesa (chama cintilando). Retorna (RGBA, (x_chama, y_chama))."""
    W, H = int(260 * u), int(520 * u)
    L = Lona(W, H, 2)
    cx = W / 2
    L.rect(cx - 90 * u, H * 0.48, cx + 90 * u, H * 0.52, fill=(46, 56, 104, 255), r=5 * u)
    L.rect(cx - 90 * u, H * 0.48, cx + 90 * u, H * 0.485, fill=(150, 170, 230, 130))
    for dx in (-72, 72):
        L.rect(cx + dx * u - 7 * u, H * 0.52, cx + dx * u + 7 * u, H, fill=(28, 34, 70, 255))
    L.rect(cx - 17 * u, H * 0.30, cx + 17 * u, H * 0.48, fill=(236, 226, 205, 255), r=4 * u)
    L.rect(cx - 17 * u, H * 0.30, cx - 9 * u, H * 0.48, fill=(255, 255, 255, 70))
    L.rect(cx - 1.5 * u, H * 0.27, cx + 1.5 * u, H * 0.31, fill=(40, 30, 30, 255))
    return L.pronto(), (cx, H * 0.255)


def chama(u, t, intens=1.0):
    W, H = int(60 * u), int(90 * u)
    L = Lona(W, H, 2)
    f = 0.85 + 0.15 * math.sin(t * 13) * math.sin(t * 7.3)
    cx = W / 2 + 2 * u * math.sin(t * 9)
    pts = [(cx, H * 0.95 - 62 * u * f * intens), (cx + 11 * u, H * 0.72), (cx + 8 * u, H * 0.92), (cx, H * 0.97), (cx - 8 * u, H * 0.92), (cx - 11 * u, H * 0.72)]
    L.poly(suavizar(pts, 3), fill=(255, 178, 70, 255))
    L.poly(suavizar([(cx, H * 0.95 - 34 * u * f), (cx + 5 * u, H * 0.82), (cx, H * 0.95), (cx - 5 * u, H * 0.82)], 3), fill=(255, 240, 200, 255))
    return L.pronto()
