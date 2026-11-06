"""
whiteboard.py - estilo 'Whiteboard Explainer' (educativo): quadro branco, caneta que escreve e desenha ao vivo.
Inspirado no estilo Whiteboard Explainer do Lemo-Opuscar (MIT). Letra: EMS Tech (SIL OFL), traco unico.
Itens (cena tipo "livre"): texto, ondulada, sol, seta, arco, linha, dispersao.
"""
import json
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from ..nucleo import Tela, clamp, ease_in_out, hex2, janela, legenda_palavras, degrade_vertical

CORES = {"preto": hex2("#23262c"), "azul": hex2("#2a5cb3"), "laranja": hex2("#d97757"), "verde": hex2("#3c8a5a"), "vermelho": hex2("#c0392b")}
_EMS = json.loads((Path(__file__).resolve().parent.parent / "fonts" / "EMSTech.json").read_text(encoding="utf-8"))["glyphs"]


def tracos_texto(x, y, txt, alt, esp=0.04):
    k = alt / 1000.0
    cx, saida = x, []
    for c in txt:
        g = _EMS.get(c, _EMS[" "])
        for s in g["s"]:
            saida.append([(cx + s[i] * k, y - s[i + 1] * k) for i in range(0, len(s), 2)])
        cx += (g["w"] + esp * 1000) * k
    return saida


def largura_texto(txt, alt, esp=0.04):
    return sum((_EMS.get(c, _EMS[" "])["w"] + esp * 1000) * alt / 1000.0 for c in txt)


def arco_pts(cx, cy, R, a0, a1, n=120):
    return [(cx + R * math.cos(math.radians(a0 + (a1 - a0) * i / n)), cy + R * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def construir(item):
    """devolve (lista de polilinhas, ponta_de_seta_opcional) em coordenadas do quadro"""
    t = item["t"]
    if t == "texto":
        return tracos_texto(item["x"], item["y"], item["txt"], item.get("alt", 90)), None
    if t == "ondulada":
        n = int(item["larg"] / 11)
        return [[(item["x"] + i * 11, item["y"] + 6 * math.sin(i * 0.55)) for i in range(n)]], None
    if t == "sol":
        x, y, r = item["x"], item["y"], item["r"]
        circ = [(x + r * math.cos(a), y + r * math.sin(a)) for a in [i * math.pi * 2 / 48 for i in range(49)]]
        raios = []
        for k in range(14):
            a = k * math.pi * 2 / 14
            r0, r1 = r * 1.3, r * (1.9 + (k % 2) * 0.28)
            raios.append([(x + r0 * math.cos(a), y + r0 * math.sin(a)), (x + r1 * math.cos(a), y + r1 * math.sin(a))])
        return [circ] + raios, None
    if t == "seta":
        a, b = item["de"], item["para"]
        return [[tuple(a), tuple(b)]], (tuple(a), tuple(b))
    if t == "arco":
        return [arco_pts(item["cx"], item["cy"], item["R"], item["a0"], item["a1"])], None
    if t == "linha":
        return [[tuple(p) for p in item["pontos"]]], None
    if t == "dispersao":
        rnd = random.Random(item.get("semente", 9))
        cx, cy, larg, alt = item["x"], item["y"], item["larg"], item["alt"]
        saida = []
        for _ in range(item.get("n", 24)):
            bx, by = cx + rnd.uniform(0, larg), cy + rnd.uniform(0, alt)
            ang, ln = rnd.uniform(0, math.pi * 2), rnd.uniform(34, 66)
            saida.append([(bx, by), (bx + ln * math.cos(ang), by + ln * math.sin(ang))])
        return saida, None
    raise ValueError(f"item desconhecido: {t}")


def comprimento(pl):
    return sum(math.dist(pl[i], pl[i + 1]) for i in range(len(pl) - 1))


def desenhar_item(tela, item, p, mostrar_caneta=True):
    pls, seta = construir(item)
    cor = CORES.get(item.get("cor", "preto"), CORES["preto"])
    w = item.get("w", 7 if item["t"] != "texto" else max(4, item.get("alt", 90) / 14))
    total = sum(comprimento(pl) + 1e-6 for pl in pls)
    alvo = total * clamp(p)
    pos = None
    acum = 0.0
    for pl in pls:
        L = comprimento(pl) + 1e-6
        if acum >= alvo:
            break
        if acum + L <= alvo:
            tela.linha(pl, cor, w) if len(pl) > 1 else tela.elipse(pl[0][0], pl[0][1], w / 2, fill=cor)
            pos = pl[-1]
        else:
            falta = alvo - acum
            parcial = [pl[0]]
            for i in range(len(pl) - 1):
                seg = math.dist(pl[i], pl[i + 1])
                if falta >= seg:
                    parcial.append(pl[i + 1])
                    falta -= seg
                else:
                    f = falta / max(seg, 1e-6)
                    parcial.append((pl[i][0] + (pl[i + 1][0] - pl[i][0]) * f, pl[i][1] + (pl[i + 1][1] - pl[i][1]) * f))
                    break
            if len(parcial) > 1:
                tela.linha(parcial, cor, w)
            pos = parcial[-1]
            acum += L
            break
        acum += L
    if seta and p > 0.96:
        a, b = seta
        ang = math.atan2(b[1] - a[1], b[0] - a[0])
        cab = 36
        tela.poly([(b[0] + cab * math.cos(ang), b[1] + cab * math.sin(ang)),
                   (b[0] + cab * 0.8 * math.cos(ang + 2.5), b[1] + cab * 0.8 * math.sin(ang + 2.5)),
                   (b[0] + cab * 0.8 * math.cos(ang - 2.5), b[1] + cab * 0.8 * math.sin(ang - 2.5))], fill=cor)
    if mostrar_caneta and pos is not None and 0 < p < 1:
        mx, my = pos
        tela.poly([(mx + 8, my + 14), (mx + 160, my - 22), (mx + 170, my + 6), (mx + 18, my + 42)], fill=(0, 0, 0, 38))
        tela.poly([(mx, my), (mx + 150, my - 34), (mx + 160, my - 6), (mx + 10, my + 28)], fill=cor)
        tela.poly([(mx - 20, my + 4), (mx, my), (mx + 10, my + 28), (mx - 12, my + 20)], fill=(235, 235, 235))


def fundo(tela):
    degrade_vertical(tela, (250, 250, 249), (236, 238, 238))
    brilho = Image.new("RGBA", tela.img.size, (0, 0, 0, 0))
    S, w, h = tela.S, tela.w, tela.h
    ImageDraw.Draw(brilho).polygon([(w * 0.62 * S, 0), (w * 0.86 * S, 0), (w * 0.55 * S, h * S), (w * 0.34 * S, h * S)], fill=(255, 255, 255, 55))
    tela.img = Image.alpha_composite(tela.img.convert("RGBA"), brilho.filter(ImageFilter.GaussianBlur(40))).convert("RGB")
    tela.d = ImageDraw.Draw(tela.img, "RGBA")
    rnd = random.Random(4)
    for _ in range(8):
        x, y = rnd.uniform(80, w - 200), rnd.uniform(h * 0.28, h * 0.85)
        tela.linha([(x, y), (x + rnd.uniform(60, 220), y + rnd.uniform(-25, 25))], (60, 70, 80, 13), 14)


class Estilo:
    nome = "whiteboard"

    def __init__(self, w, h):
        self.w, self.h = w, h

    def fundo(self, tela):
        fundo(tela)

    def quadro(self, tela, t, cena, canal):
        for it in cena["itens"]:
            p = janela(t, it["ini"], it["dur"])
            if p > 0:
                desenhar_item(tela, it, ease_in_out(p) if it["t"] in ("sol", "arco", "seta") else p)
        ls = cena.get("legenda", [])
        if ls:
            legenda_palavras(tela, t, ls, self.h - 52, 34, 1100, fundo=(20, 22, 30, 205))


# ====================================================================================
# Cenas automaticas (posicionamento feito pelo programa): titulo, passos, lista, destaque
# ====================================================================================
def quebrar_ems(txt, alt, largura):
    linhas, cur = [], ""
    for p in txt.split():
        teste = (cur + " " + p).strip()
        if largura_texto(teste, alt) <= largura or not cur:
            cur = teste
        else:
            linhas.append(cur)
            cur = p
    if cur:
        linhas.append(cur)
    return linhas


def ajustar_ems(txt, alt_max, largura, max_linhas, alt_min=44):
    alt = alt_max
    while True:
        linhas = quebrar_ems(txt, alt, largura)
        if len(linhas) <= max_linhas or alt <= alt_min:
            return alt, linhas[:max_linhas] if len(linhas) > max_linhas else linhas
        alt -= 4


def _agendar(itens, dur, inicio=0.35, folga=0.9):
    """distribui os inicios dos itens ao longo da cena (a escrita acompanha a fala)"""
    pesos = []
    for it in itens:
        if it["t"] == "texto":
            pesos.append(0.25 + 0.075 * len(it["txt"]))
        elif it["t"] in ("arco", "sol"):
            pesos.append(0.7)
        else:
            pesos.append(0.5)
    total = sum(pesos)
    disp = max(1.0, dur - inicio - folga)
    esc = min(1.5, disp / total)
    t = inicio
    for it, pw in zip(itens, pesos):
        it["ini"] = round(t, 3)
        it["dur"] = round(max(0.25, pw * esc), 3)
        t += pw * esc


def _titulo_linhas(titulo, w, margem, alt_max, max_linhas=2):
    return ajustar_ems(titulo, alt_max, w - 2 * margem, max_linhas)


def expandir(cena, w, h):
    """converte uma cena automatica em itens com coordenadas"""
    tipo = cena["tipo"]
    vert = h > w
    mg = 90 if vert else 110
    itens = []

    def texto(x, y, txt, alt, cor="preto", centro=False):
        if centro:
            x = x - largura_texto(txt, alt) / 2
        itens.append({"t": "texto", "x": x, "y": y, "txt": txt, "alt": alt, "cor": cor})

    if tipo == "titulo":
        alt, linhas = ajustar_ems(cena["titulo"], 190 if not vert else 150, w - 2 * mg, 3)
        bloco = len(linhas) * alt * 1.15
        y = h * 0.42 - bloco / 2 + alt
        for ln in linhas:
            texto(w / 2, y, ln, alt, "preto", True)
            y += alt * 1.15
        larg = max(largura_texto(ln, alt) for ln in linhas)
        itens.append({"t": "ondulada", "x": w / 2 - larg / 2, "y": y - alt * 0.7, "larg": larg, "cor": "laranja"})
        if cena.get("subtitulo"):
            a2, l2 = ajustar_ems(cena["subtitulo"], 80, w - 2 * mg, 2, 40)
            yy = y + a2 * 1.1
            for ln in l2:
                texto(w / 2, yy, ln, a2, "azul", True)
                yy += a2 * 1.15
    elif tipo in ("passos", "lista"):
        alt_t, linhas_t = _titulo_linhas(cena["titulo"], w, mg, 110 if not vert else 96, 2)
        y = mg * 0.9 + alt_t
        for ln in linhas_t:
            texto(mg, y, ln, alt_t, "preto")
            y += alt_t * 1.12
        larg = max(largura_texto(ln, alt_t) for ln in linhas_t)
        itens.append({"t": "ondulada", "x": mg, "y": y - alt_t * 0.72, "larg": larg, "cor": "laranja"})
        itens_txt = cena["itens"][:5] if "itens" in cena else cena["passos"][:5]
        n = len(itens_txt)
        topo = y + alt_t * 0.6
        base = h - (150 if not vert else 260)
        linha_h = min(200 if not vert else 300, (base - topo) / max(1, n))
        cores = ["azul", "laranja", "verde", "azul", "laranja"]
        for i, txt in enumerate(itens_txt):
            cy = topo + linha_h * (i + 0.5)
            alt = min(100 if not vert else 84, linha_h * 0.55)
            x_txt = mg + alt * 1.9
            a2, ls = ajustar_ems(txt, alt, w - x_txt - mg, 2, 40)
            if tipo == "passos":
                r = a2 * 0.62
                itens.append({"t": "arco", "cx": mg + r, "cy": cy, "R": r, "a0": 0, "a1": 360, "cor": cores[i], "w": 6})
                texto(mg + r - largura_texto(str(i + 1), a2 * 0.9) / 2, cy + a2 * 0.3, str(i + 1), a2 * 0.9, cores[i])
            else:
                itens.append({"t": "linha", "pontos": [[mg + a2 * 0.1, cy - a2 * 0.35], [mg + a2 * 0.5, cy], [mg + a2 * 0.1, cy + a2 * 0.35]], "cor": cores[i], "w": 9})
            yy = cy + a2 * 0.3 - (len(ls) - 1) * a2 * 0.55
            for ln in ls:
                texto(x_txt, yy, ln, a2, "preto")
                yy += a2 * 1.1
    elif tipo == "destaque":
        alt, linhas = ajustar_ems(cena["frase"], 170 if not vert else 140, w - 2 * mg - 60, 4)
        bloco = len(linhas) * alt * 1.15
        y = h * 0.45 - bloco / 2 + alt
        for ln in linhas:
            texto(w / 2, y, ln, alt, "azul", True)
            y += alt * 1.15
        larg = max(largura_texto(ln, alt) for ln in linhas)
        itens.append({"t": "ondulada", "x": w / 2 - larg / 2, "y": y - alt * 0.75, "larg": larg, "cor": "laranja"})
        for sx, sy, ang in [(-1, -1, 225), (1, -1, 315), (-1, 1, 135), (1, 1, 45)]:
            cx = w / 2 + sx * (larg / 2 + 60)
            cy = h * 0.45 + sy * (bloco / 2 + 10)
            a = math.radians(ang)
            itens.append({"t": "linha", "pontos": [[cx, cy], [cx + 50 * math.cos(a), cy + 50 * math.sin(a)]], "cor": "laranja", "w": 8})
    else:
        raise ValueError(f"tipo de cena desconhecido no whiteboard: {tipo}")
    _agendar(itens, float(cena["duracao"]))
    return itens


_cache_itens = {}


def _quadro_auto(self, tela, t, cena, canal):
    chave = (id(cena), self.w, self.h)
    if chave not in _cache_itens:
        _cache_itens[chave] = cena["itens"] if cena["tipo"] == "livre" else expandir(cena, self.w, self.h)
    itens = _cache_itens[chave]
    for it in itens:
        p = janela(t, it["ini"], it["dur"])
        if p > 0:
            desenhar_item(tela, it, ease_in_out(p) if it["t"] in ("sol", "arco", "seta") else p)
    ls = cena.get("legenda", [])
    if ls:
        if self.h > self.w:
            legenda_palavras(tela, t, ls, self.h - 150, 44, 900, fundo=(20, 22, 30, 205))
        else:
            legenda_palavras(tela, t, ls, self.h - 52, 34, 1100, fundo=(20, 22, 30, 205))


Estilo.quadro = _quadro_auto
