"""
telejornal.py - estilo 'Broadcast News Package' (economia, documentar, jornalistico).
Paleta e regras inspiradas no estilo Broadcast News Package do Lemo-Opuscar (MIT): tinta escura, limao, ouro, papel.
Tipo de cena disponivel: "grafico" (grafico de linha + cartao de dados + faixa de manchete).
"""
from PIL import Image, ImageFilter, ImageDraw

from ..nucleo import (Tela, clamp, contar, ease_in_out, ease_out, hex2, janela, legenda_palavras, lerp, mix, overshoot,
                      degrade_vertical)

TINTA, TINTA2, LIMAO, OURO, PAPEL = hex2("#121417"), hex2("#1B1E23"), hex2("#F2CF1D"), hex2("#D4B064"), hex2("#F4F1E8")
CINZA = (160, 165, 170)


def layout(w, h):
    if w >= h:   # 16:9
        return dict(
            tipo="h", selo=(80, 64, 330, 112), assunto=(352, 88), canal=(1840, 88),
            grafico=(120, 190, 1180, 740), cartao=(1280, 190, 1840, 740),
            faixa=(70, 820, 1500, 930), tab=230, logo=(1560, 830, 1850, 920), aviso=(330, 962),
            legenda=(1019, 1000, 36), manchete=46, manchete_linhas=1, cartao_num=140, cartao_val=84)
    return dict(      # 9:16
        tipo="v", selo=(60, 70, 310, 118), assunto=(60, 160), canal=(1020, 94),
        grafico=(90, 290, 990, 900), cartao=(60, 960, 1020, 1400),
        faixa=(40, 1470, 1040, 1620), tab=190, logo=(760, 1650, 1040, 1730), aviso=(60, 1672),
        legenda=(1790, 900, 44), manchete=40, manchete_linhas=2, cartao_num=130, cartao_val=70)


def fundo(tela, L):
    w, h = tela.w, tela.h
    degrade_vertical(tela, (22, 24, 28), (14, 16, 19))
    passo = 80
    for x in range(0, w, passo):
        tela.linha([(x, 0), (x, h)], (255, 255, 255, 7), 1, cap=False)
    for y in range(0, h, passo):
        tela.linha([(0, y), (w, y)], (255, 255, 255, 7), 1, cap=False)
    # vinheta suave
    m = Image.new("L", (w // 8, h // 8), 0)
    dm = ImageDraw.Draw(m)
    dm.ellipse([-w // 16, -h // 16, w // 8 + w // 16, h // 8 + h // 16], fill=255)
    m = m.filter(ImageFilter.GaussianBlur(18)).resize(tela.img.size)
    escuro = Image.new("RGB", tela.img.size, (0, 0, 0))
    tela.img = Image.composite(tela.img, Image.blend(tela.img, escuro, 0.35), m)
    tela.d = ImageDraw.Draw(tela.img, "RGBA")


def caber(tela, txt, nome, tam, largura):
    """reduz o tamanho da fonte ate o texto caber na largura"""
    while tam > 20 and tela.largura_texto(txt, nome, tam) > largura:
        tam -= 4
    return tam


def quebrar(tela, txt, nome, tam, largura, max_linhas):
    palavras, linhas, cur = txt.split(), [], ""
    for p in palavras:
        teste = (cur + " " + p).strip()
        if tela.largura_texto(teste, nome, tam) <= largura or not cur:
            cur = teste
        else:
            linhas.append(cur)
            cur = p
    if cur:
        linhas.append(cur)
    return linhas[:max_linhas]


def quadro_grafico(tela, t, cena, canal, L):
    w, h = tela.w, tela.h
    # ---- cabecalho
    sx0, sy0, sx1, sy1 = L["selo"]
    p_selo = ease_out(janela(t, 0.0, 0.45))
    dx = -(1 - p_selo) * (sx1 + 20)
    tela.rect(sx0 + dx, sy0, sx1 + dx, sy1, fill=LIMAO)
    tela.texto((sx0 + sx1) / 2 + dx, (sy0 + sy1) / 2, cena.get("secao", "MERCADOS"), "cond", 34, TINTA, anchor="mm")
    a = janela(t, 0.25, 0.4)
    tela.texto(*L["assunto"], cena.get("assunto", ""), "cond", 28, (OURO[0], OURO[1], OURO[2], int(255 * a)), anchor="lm")
    tela.texto(*L["canal"], cena.get("rotulo_canto", "NOT\u00cdCIAS"), "cond", 28, PAPEL, anchor="rm")

    # ---- grafico
    x0, y0, x1, y1 = L["grafico"]
    serie = cena["serie"]
    n = len(serie)
    lo = cena.get("min", min(serie) - (max(serie) - min(serie)) * 0.12)
    hi = cena.get("max", max(serie) + (max(serie) - min(serie)) * 0.12)
    ag = janela(t, 0.1, 0.5)
    for k in range(5):
        yy = y0 + k * (y1 - y0) / 4
        tela.linha([(x0, yy), (x1, yy)], (255, 255, 255, int(22 * ag)), 1, cap=False)
    pts = [(x0 + i * (x1 - x0) / (n - 1), y1 - (v - lo) / (hi - lo) * (y1 - y0)) for i, v in enumerate(serie)]
    p = ease_out(janela(t, 0.3, 2.2))
    u = p * (n - 1)
    idx = int(u)
    parcial = pts[:idx + 1]
    if idx < n - 1:
        f = u - idx
        parcial.append((lerp(pts[idx][0], pts[idx + 1][0], f), lerp(pts[idx][1], pts[idx + 1][1], f)))
    if len(parcial) >= 2:
        tela.poly(parcial + [(parcial[-1][0], y1), (parcial[0][0], y1)], fill=(244, 241, 232, 38))
        tela.linha(parcial, PAPEL, 7 if tela.w >= tela.h else 8)
    # limite tracejado
    lim = cena.get("limite")
    if lim:
        al = janela(t, 0.7, 0.4)
        ylim = y1 - (lim["valor"] - lo) / (hi - lo) * (y1 - y0)
        step = 26
        xx = x0
        while xx < x1:
            tela.linha([(xx, ylim), (min(xx + 14, x1), ylim)], (OURO[0], OURO[1], OURO[2], int(255 * al)), 3, cap=False)
            xx += step
        tela.texto(x0 + 8, ylim - 14, lim["rotulo"], "cond", 26, (OURO[0], OURO[1], OURO[2], int(255 * al)), anchor="ls")
    # ultimo ponto, linha vertical e etiqueta
    pp = janela(t, 2.45, 0.35)
    if pp > 0:
        px, py = pts[-1]
        tela.elipse(px, py, 13 * overshoot(pp), fill=LIMAO)
        tela.linha([(px, py + 16), (px, py + 16 + (y1 - py - 16) * ease_out(janela(t, 2.5, 0.4)))], LIMAO, 3, cap=False)
    tag = cena.get("tag")
    if tag:
        pt = overshoot(janela(t, 2.8, 0.4))
        if pt > 0:
            tw = tela.largura_texto(tag, "cond", 38) + 70
            cx = x0 + (x1 - x0) * 0.5
            cy = y0 + 62
            tela.rect(cx - tw / 2 * pt, cy - 32 * pt, cx + tw / 2 * pt, cy + 32 * pt, fill=LIMAO)
            if pt > 0.7:
                tela.texto(cx, cy, tag, "cond", 38, TINTA, anchor="mm")
    rot = cena.get("rotulos_x", [])
    if rot:
        al = janela(t, 0.5, 0.5)
        for i, lab in enumerate(rot):
            xx = x0 + i * (x1 - x0) / max(1, len(rot) - 1) * 0.97
            tela.texto(xx, y1 + 40, lab, "cond", 24, (CINZA[0], CINZA[1], CINZA[2], int(255 * al)), anchor="lm")

    # ---- cartao de dados (entra pela direita / por baixo)
    c = cena.get("cartao")
    if c:
        cx0, cy0, cx1, cy1 = L["cartao"]
        pc = ease_out(janela(t, 1.0, 0.55))
        if L["tipo"] == "h":
            ox, oy = (1 - pc) * (w - cx0 + 40), 0
        else:
            ox, oy = 0, (1 - pc) * (h - cy0 + 40)
        X0, Y0, X1, Y1 = cx0 + ox, cy0 + oy, cx1 + ox, cy1 + oy
        tela.rect(X0, Y0, X1, Y1, fill=TINTA2)
        tela.rect(X0, Y0, X1, Y0 + 9, fill=LIMAO)
        alt = Y1 - Y0
        tela.texto(X0 + 40, Y0 + alt * 0.12, c.get("titulo", ""), "cond", 28, OURO, anchor="lm")
        pn = ease_out(janela(t, 1.6, 1.4))
        tam_n = caber(tela, c["destaque"].replace("0", "8"), "bold", L["cartao_num"], X1 - X0 - 80)
        tela.texto(X0 + 38, Y0 + alt * 0.34, contar(c["destaque"], pn), "bold", tam_n, LIMAO, anchor="lm")
        tela.texto(X0 + 40, Y0 + alt * 0.49, c.get("destaque_rotulo", ""), "cond", 26, (190, 190, 185), anchor="lm")
        tela.linha([(X0 + 40, Y0 + alt * 0.56), (X1 - 40, Y0 + alt * 0.56)], (255, 255, 255, 40), 2, cap=False)
        pv = ease_out(janela(t, 1.9, 1.2))
        tam_v = caber(tela, c.get("valor", "").replace("0", "8"), "bold", L["cartao_val"], X1 - X0 - 80)
        tela.texto(X0 + 40, Y0 + alt * 0.70, contar(c.get("valor", ""), pv), "bold", tam_v, PAPEL, anchor="lm")
        tela.texto(X0 + 40, Y0 + alt * 0.82, c.get("valor_rotulo", ""), "cond", 26, (190, 190, 185), anchor="lm")
        tela.texto(X0 + 40, Y0 + alt * 0.93, c.get("nota", ""), "cond", 32, LIMAO, anchor="lm")

    # ---- faixa de manchete (sobe) + logo
    fx0, fy0, fx1, fy1 = L["faixa"]
    pf = ease_out(janela(t, 3.1, 0.5))
    oy = (1 - pf) * (h - fy0 + 30)
    tela.rect(fx0, fy0 + oy, fx1, fy1 + oy, fill=PAPEL)
    tela.rect(fx0, fy0 + oy, fx0 + L["tab"], fy1 + oy, fill=LIMAO)
    tela.texto(fx0 + L["tab"] / 2, (fy0 + fy1) / 2 + oy, cena.get("secao", "MERCADOS"), "cond", 30, TINTA, anchor="mm")
    prog = ease_in_out(janela(t, 3.4, 0.9))
    manchete = cena.get("faixa", "")
    mx = fx0 + L["tab"] + 30
    if L["manchete_linhas"] == 1:
        tela.texto_revelado(mx, (fy0 + fy1) / 2 + oy, manchete, "cond", L["manchete"], TINTA, prog)
    else:
        linhas = quebrar(tela, manchete, "cond", L["manchete"], fx1 - mx - 20, 2)
        for i, ln in enumerate(linhas):
            yy = (fy0 + fy1) / 2 + oy + (i - (len(linhas) - 1) / 2) * (L["manchete"] * 1.25)
            tela.texto_revelado(mx, yy, ln, "cond", L["manchete"], TINTA, clamp(prog * 1.6 - i * 0.6))
    ax, ay = L["aviso"]
    if cena.get("aviso"):
        tela.texto(ax, ay + oy * 0, cena["aviso"], "cond", 24, (OURO[0], OURO[1], OURO[2], int(255 * janela(t, 3.7, 0.4))), anchor="lm")
    lx0, ly0, lx1, ly1 = L["logo"]
    al = janela(t, 3.6, 0.4)
    if al > 0:
        tela.rect(lx0, ly0, lx1, ly1, fill=(LIMAO[0], LIMAO[1], LIMAO[2], int(255 * al)))
        tela.texto((lx0 + lx1) / 2, (ly0 + ly1) / 2, canal, "cond", 44 if L["tipo"] == "h" else 36, (TINTA[0], TINTA[1], TINTA[2], int(255 * al)), anchor="mm")

    # ---- legenda
    ly, lmax, ltam = L["legenda"]
    legenda_palavras(tela, t, cena.get("legenda", []), ly, ltam, lmax)


TIPOS = {"grafico": quadro_grafico}

# ====================================================================================
# Cenas automaticas: manchete, destaque, lista (o programa posiciona tudo)
# ====================================================================================
def cabecalho(tela, t, cena, L):
    sx0, sy0, sx1, sy1 = L["selo"]
    p_selo = ease_out(janela(t, 0.0, 0.45))
    dx = -(1 - p_selo) * (sx1 + 20)
    tela.rect(sx0 + dx, sy0, sx1 + dx, sy1, fill=LIMAO)
    tela.texto((sx0 + sx1) / 2 + dx, (sy0 + sy1) / 2, cena.get("secao", "NOT\u00cdCIAS"), "cond", 34, TINTA, anchor="mm")
    a = janela(t, 0.25, 0.4)
    tela.texto(*L["assunto"], cena.get("assunto", ""), "cond", 28, (OURO[0], OURO[1], OURO[2], int(255 * a)), anchor="lm")
    tela.texto(*L["canal"], cena.get("rotulo_canto", ""), "cond", 28, PAPEL, anchor="rm")


def rodape(tela, t, cena, canal, L):
    lx0, ly0, lx1, ly1 = L["logo"]
    al = janela(t, 0.8, 0.4)
    if al > 0:
        tela.rect(lx0, ly0, lx1, ly1, fill=(LIMAO[0], LIMAO[1], LIMAO[2], int(255 * al)))
        tela.texto((lx0 + lx1) / 2, (ly0 + ly1) / 2, canal, "cond", 44 if L["tipo"] == "h" else 36, (TINTA[0], TINTA[1], TINTA[2], int(255 * al)), anchor="mm")
    ly, lmax, ltam = L["legenda"]
    legenda_palavras(tela, t, cena.get("legenda", []), ly, ltam, lmax)


def quadro_manchete(tela, t, cena, canal, L):
    cabecalho(tela, t, cena, L)
    vert = L["tipo"] == "v"
    x = 120 if not vert else 80
    larg = (1680 if not vert else 920)
    tam = 112 if not vert else 96
    linhas = quebrar(tela, cena["titulo"], "cond", tam, larg, 4)
    while len(linhas) > 3 and tam > 60:
        tam -= 6
        linhas = quebrar(tela, cena["titulo"], "cond", tam, larg, 4)
    alt_bloco = len(linhas) * tam * 1.2
    y0 = (tela.h * 0.38) - alt_bloco / 2
    pb = ease_out(janela(t, 0.3, 0.6))
    tela.rect(x - 34, y0, x - 18, y0 + alt_bloco * pb, fill=LIMAO)
    for i, ln in enumerate(linhas):
        yy = y0 + tam * 0.6 + i * tam * 1.2
        tela.texto_revelado(x, yy, ln, "cond", tam, PAPEL, ease_in_out(janela(t, 0.5 + i * 0.45, 0.6)))
    if cena.get("subtitulo"):
        a = janela(t, 1.4 + 0.45 * len(linhas), 0.5)
        yy = y0 + alt_bloco + 50
        for j, ln in enumerate(quebrar(tela, cena["subtitulo"], "cond", 40, larg, 2)):
            tela.texto(x, yy + j * 52, ln, "cond", 40, (OURO[0], OURO[1], OURO[2], int(255 * a)), anchor="lm")
    if cena.get("faixa"):
        fx0, fy0, fx1, fy1 = L["faixa"]
        pf = ease_out(janela(t, 1.8, 0.5))
        oy = (1 - pf) * (tela.h - fy0 + 30)
        tela.rect(fx0, fy0 + oy, fx1, fy1 + oy, fill=PAPEL)
        tela.rect(fx0, fy0 + oy, fx0 + L["tab"], fy1 + oy, fill=LIMAO)
        tela.texto(fx0 + L["tab"] / 2, (fy0 + fy1) / 2 + oy, cena.get("secao", "NOT\u00cdCIAS"), "cond", 30, TINTA, anchor="mm")
        mx = fx0 + L["tab"] + 30
        for i, ln in enumerate(quebrar(tela, cena["faixa"], "cond", L["manchete"], fx1 - mx - 20, 2)):
            yy = (fy0 + fy1) / 2 + oy + (i - (len(quebrar(tela, cena["faixa"], "cond", L["manchete"], fx1 - mx - 20, 2)) - 1) / 2) * (L["manchete"] * 1.25)
            tela.texto(mx, yy, ln, "cond", L["manchete"], TINTA, anchor="lm")
    rodape(tela, t, cena, canal, L)


def quadro_destaque(tela, t, cena, canal, L):
    cabecalho(tela, t, cena, L)
    vert = L["tipo"] == "v"
    cx0, cy0, cx1, cy1 = (360, 210, 1560, 800) if not vert else (60, 480, 1020, 1240)
    pc = ease_out(janela(t, 0.4, 0.6))
    oy = (1 - pc) * (tela.h - cy0 + 40)
    X0, Y0, X1, Y1 = cx0, cy0 + oy, cx1, cy1 + oy
    tela.rect(X0, Y0, X1, Y1, fill=TINTA2)
    tela.rect(X0, Y0, X1, Y0 + 10, fill=LIMAO)
    alt = Y1 - Y0
    tela.texto(X0 + 50, Y0 + alt * 0.12, cena.get("titulo", ""), "cond", 34, OURO, anchor="lm")
    pn = ease_out(janela(t, 0.9, 1.6))
    tam_n = caber(tela, cena["numero"].replace("0", "8"), "bold", 230 if not vert else 190, X1 - X0 - 100)
    tela.texto(X0 + 48, Y0 + alt * 0.42, contar(cena["numero"], pn), "bold", tam_n, LIMAO, anchor="lm")
    tela.texto(X0 + 50, Y0 + alt * 0.66, cena.get("rotulo", ""), "cond", 36, (200, 200, 195), anchor="lm")
    tela.linha([(X0 + 50, Y0 + alt * 0.74), (X1 - 50, Y0 + alt * 0.74)], (255, 255, 255, 40), 2, cap=False)
    for j, ln in enumerate(quebrar(tela, cena.get("nota", ""), "cond", 38, X1 - X0 - 100, 2)):
        a = janela(t, 1.8, 0.5)
        tela.texto(X0 + 50, Y0 + alt * 0.84 + j * 48, ln, "cond", 38, (LIMAO[0], LIMAO[1], LIMAO[2], int(255 * a)), anchor="lm")
    rodape(tela, t, cena, canal, L)


def quadro_lista(tela, t, cena, canal, L):
    cabecalho(tela, t, cena, L)
    vert = L["tipo"] == "v"
    itens = cena["itens"][:5]
    n = len(itens)
    x0 = 120 if not vert else 60
    x1 = 1800 if not vert else 1020
    topo = 200 if not vert else 260
    base = 840 if not vert else 1560
    alt_c = min(190 if not vert else 230, (base - topo - (n - 1) * 24) / n)
    tela.texto(x0, topo - 40, cena.get("titulo", "PONTOS-CHAVE"), "cond", 40, OURO, anchor="lm")
    for i, txt in enumerate(itens):
        ini = 0.6 + i * max(0.6, (float(cena["duracao"]) - 2.0) / n)
        p = ease_out(janela(t, ini, 0.5))
        if p <= 0:
            continue
        y0 = topo + i * (alt_c + 24)
        ox = (1 - p) * (tela.w - x0)
        tela.rect(x0 + ox, y0, x1 + ox, y0 + alt_c, fill=TINTA2)
        tela.rect(x0 + ox, y0, x0 + ox + 12, y0 + alt_c, fill=LIMAO)
        tela.texto(x0 + ox + 60, y0 + alt_c / 2, str(i + 1), "bold", min(90, alt_c * 0.5), LIMAO, anchor="mm")
        linhas = quebrar(tela, txt, "cond", 46 if not vert else 44, x1 - x0 - 190, 3)
        for j, ln in enumerate(linhas):
            yy = y0 + alt_c / 2 + (j - (len(linhas) - 1) / 2) * 56
            tela.texto(x0 + ox + 120, yy, ln, "cond", 46 if not vert else 44, PAPEL, anchor="lm")
    rodape(tela, t, cena, canal, L)


TIPOS.update({"manchete": quadro_manchete, "destaque": quadro_destaque, "lista": quadro_lista})



class Estilo:
    nome = "telejornal"

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.L = layout(w, h)

    def fundo(self, tela):
        fundo(tela, self.L)

    def quadro(self, tela, t, cena, canal):
        TIPOS[cena["tipo"]](tela, t, cena, canal, self.L)
