"""broadcast_motion.py - Broadcast News com motion graphics quadro a quadro.

Reaproveita roteiro, voz, midias e publicacao do broadcast_news.py.
Midia da cena (imagens/01.jpg, 01.mp4...) vira fundo animado com os graficos por cima.
PNG em <raiz>/icones/<nome>.png substitui o icone desenhado.
"""
from __future__ import annotations

import math
import re
import subprocess
import sys
import unicodedata
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))

import broadcast_news as bn  # noqa: E402

if hasattr(bn, "VISUAL_TYPES"):
    bn.VISUAL_TYPES.add("impacto")

FPS = bn.FPS
ICON_DIR = bn.ROOT / "icones"
CYAN, GOLD, RED, WHITE = (30, 192, 230), (255, 201, 63), (233, 57, 67), (246, 250, 255)
LIGHT, NAVY, GREEN, PURPLE = (205, 222, 236), (10, 34, 60), (60, 200, 130), (150, 110, 240)
PALETTE = [CYAN, GOLD, RED, GREEN, PURPLE, (240, 140, 60)]
F = lru_cache(maxsize=96)(bn.get_font)

ICONS = ["dolar", "ouro", "banco", "documento", "grafico", "pessoa", "globo", "relogio", "balanca", "alvo"]
KEYWORDS = {
    "dolar": ["dolar", "moeda", "dinheiro", "cambio", "preco", "custo", "salario", "imposto", "inflac", "juro", "divida"],
    "ouro": ["ouro", "metal", "reserva", "lastro", "commodit", "petroleo"],
    "banco": ["banco", "central", "credito", "financ", "governo", "congresso", "instituic", "estado"],
    "documento": ["lei", "decreto", "contrato", "documento", "regra", "norma", "acordo", "tratado", "constituic", "projeto"],
    "grafico": ["cresc", "queda", "alta", "baixa", "indice", "pib", "dado", "percent", "mercado", "bolsa", "taxa"],
    "pessoa": ["pessoa", "populac", "trabalhador", "cidadao", "presidente", "consumidor", "eleitor", "povo", "familia", "lider"],
    "globo": ["mundo", "pais", "internacional", "global", "export", "import", "guerra", "china", "eua", "europa"],
    "relogio": ["ano", "data", "prazo", "seculo", "historia", "decada", "tempo", "antes", "depois", "futuro"],
    "balanca": ["justica", "stf", "tribunal", "direito", "juiz", "equilibrio", "compar", "versus"],
    "alvo": ["meta", "objetivo", "resultado", "impacto", "foco", "estrategia", "consequen"],
}

MOTION_RULES = """

DIRECAO DE MOTION (motor animado):
- Varie os layouts: nao repita o mesmo type em mais de 2 cenas seguidas.
- Sempre que houver numero confirmado, use stat (um numero) ou chart (serie de numeros).
- Em chart, inclua "style": "barras" (comparar itens), "linha" (evolucao no tempo) ou "pizza" (partes de um todo que somam 100%).
- Em items, steps e events, inclua "icone" com um destes valores: dolar, ouro, banco, documento, grafico, pessoa, globo, relogio, balanca, alvo.
- busca_wikimedia deve descrever uma imagem coerente com a narracao e o icone da cena; ela sera usada como fundo.
- Nunca invente numeros para preencher graficos; sem dado confirmado, use flow, timeline, bullets ou comparison.
- Use type "impacto" em 2 a 4 cenas de virada: {"type":"impacto","linhas":["Produto chega do exterior","E TAXADO"],"destaque":"TAXADO"}. Linhas curtissimas (ate 5 palavras), destaque = 1 ou 2 palavras de impacto. Use logo apos o gancho e no climax.
"""


# ------------------------------------------------------------------ utilidades
def clamp(t):
    return max(0.0, min(1.0, t))


def ease(t):
    return 1 - (1 - clamp(t)) ** 3


def back(t):
    t, c = clamp(t), 1.7
    return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2


def norm(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def pick_icon(text, i, used=()):
    n = norm(text)
    hits = [k for k, kws in KEYWORDS.items() if any(w in n for w in kws)]
    for k in hits:
        if k not in used:
            return k
    return hits[0] if hits else ICONS[(i * 3) % len(ICONS)]


def wrap(d, text, font, maxw, maxl):
    lines = [l for l in bn.fit_text(d, str(text or ""), font, int(max(40, maxw))) if l]
    if len(lines) > maxl:
        lines = lines[:maxl]
        lines[-1] = lines[-1].rstrip(" .,;") + "…"
    return lines


def text_block(d, x, y, lines, font, fill, center=False, gap=6):
    for ln in lines:
        w = d.textlength(ln, font=font)
        d.text((x - w / 2 if center else x, y), ln, font=font, fill=fill)
        y += font.size + gap
    return y


def parse_number(value):
    m = re.search(r"-?\d[\d.,]*", value or "")
    if not m:
        return None
    s = m.group(0).rstrip(".,")
    if "," in s:
        dec, num = len(s.split(",")[-1]), float(s.replace(".", "").replace(",", "."))
    elif re.fullmatch(r"-?\d{1,3}(\.\d{3})+", s):
        dec, num = 0, float(s.replace(".", ""))
    else:
        dec, num = (len(s.split(".")[-1]) if "." in s else 0), float(s)
    return value[:m.start()], num, dec, value[m.start() + len(s):]


def fmt_br(x, dec):
    return f"{x:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ------------------------------------------------------------------ icones
@lru_cache(maxsize=96)
def icon_tile(name, size, color):
    S = 240
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((6, 6, S - 6, S - 6), fill=NAVY + (240,), outline=color + (255,), width=8)
    png = ICON_DIR / f"{name}.png"
    if png.is_file():
        try:
            g = Image.open(png).convert("RGBA")
            g.thumbnail((150, 150), Image.LANCZOS)
            img.alpha_composite(g, ((S - g.width) // 2, (S - g.height) // 2))
            return img.resize((size, size), Image.LANCZOS)
        except OSError:
            pass
    c, g, w, bg = color + (255,), GOLD + (255,), WHITE + (255,), NAVY + (255,)
    if name == "dolar":
        d.text((S / 2, S / 2), "$", font=F(150, True), fill=g, anchor="mm")
    elif name == "ouro":
        for cx, cy in ((92, 140), (148, 140), (120, 96)):
            d.polygon([(cx - 22, cy), (cx + 22, cy), (cx + 30, cy + 38), (cx - 30, cy + 38)], fill=g, outline=(170, 120, 20, 255))
    elif name == "banco":
        d.polygon([(48, 105), (120, 52), (192, 105)], fill=c)
        for x in (72, 104, 136, 168):
            d.rectangle((x - 8, 114, x + 8, 166), fill=w)
        d.rectangle((52, 170, 188, 186), fill=c)
    elif name == "documento":
        d.polygon([(72, 50), (140, 50), (168, 78), (168, 190), (72, 190)], fill=w)
        d.polygon([(140, 50), (140, 78), (168, 78)], fill=(170, 195, 215, 255))
        for y in (100, 124, 148, 170):
            d.line((88, y, 152, y), fill=bg, width=7)
    elif name == "grafico":
        d.line((60, 58, 60, 182, 192, 182), fill=w, width=7)
        for x, y in ((78, 140), (114, 114), (150, 86)):
            d.rectangle((x, y, x + 24, 178), fill=c)
        d.line((70, 150, 105, 122, 140, 98, 182, 62), fill=g, width=8, joint="curve")
    elif name == "pessoa":
        d.ellipse((90, 48, 150, 108), fill=w)
        d.pieslice((58, 118, 182, 242), 180, 360, fill=w)
    elif name == "globo":
        d.ellipse((55, 55, 185, 185), outline=c, width=7)
        d.ellipse((95, 55, 145, 185), outline=c, width=5)
        for y, x0 in ((88, 68), (120, 56), (152, 68)):
            d.line((x0, y, S - x0, y), fill=c, width=5)
    elif name == "relogio":
        d.ellipse((55, 55, 185, 185), outline=w, width=8)
        d.line((120, 120, 120, 74), fill=w, width=8)
        d.line((120, 120, 156, 136), fill=g, width=8)
        d.ellipse((112, 112, 128, 128), fill=g)
    elif name == "balanca":
        d.line((120, 58, 120, 184), fill=w, width=7)
        d.line((84, 186, 156, 186), fill=w, width=9)
        d.line((58, 80, 182, 80), fill=w, width=7)
        for x in (60, 180):
            d.line((x, 80, x - 18, 132), fill=w, width=4)
            d.line((x, 80, x + 18, 132), fill=w, width=4)
            d.chord((x - 26, 112, x + 26, 158), 0, 180, fill=g)
    elif name == "alvo":
        d.ellipse((52, 52, 188, 188), fill=c)
        d.ellipse((74, 74, 166, 166), fill=bg)
        d.ellipse((96, 96, 144, 144), fill=c)
        d.ellipse((112, 112, 128, 128), fill=g)
    return img.resize((size, size), Image.LANCZOS)


def paste_icon(layer, name, cx, cy, r, p, color):
    s, a = back(p), ease(p)
    size = int(2 * r * s)
    if size < 4 or a <= 0 or r < 4:
        return
    tile = icon_tile(name, 2 * r, color)
    if size != 2 * r:
        tile = tile.resize((size, size), Image.BILINEAR)
    if a < 1:
        tile = tile.copy()
        tile.putalpha(tile.getchannel("A").point(lambda v: int(v * a)))
    x, y = int(cx - size / 2), int(cy - size / 2)
    if x >= 0 and y >= 0 and x + size <= layer.width and y + size <= layer.height:
        layer.alpha_composite(tile, (x, y))


def arrow(d, p0, p1, prog, color):
    if prog <= 0:
        return
    prog = min(1.0, prog)
    x, y = p0[0] + (p1[0] - p0[0]) * prog, p0[1] + (p1[1] - p0[1]) * prog
    d.line((p0[0], p0[1], x, y), fill=color + (255,), width=7)
    ang, L = math.atan2(p1[1] - p0[1], p1[0] - p0[0]), 24
    d.polygon([(x, y), (x - L * math.cos(ang - .5), y - L * math.sin(ang - .5)),
               (x - L * math.cos(ang + .5), y - L * math.sin(ang + .5))], fill=color + (255,))


# ------------------------------------------------------------------ dados da cena
def nodes_of(v):
    k = v.get("type")
    if k == "flow":
        src = v.get("steps") or v.get("items")
    elif k == "timeline":
        src = v.get("events") or v.get("items")
    elif k == "comparison":
        src = [x for x in (v.get("left"), v.get("right")) if x]
    else:
        src = v.get("items")
    src = [x for x in (src or []) if isinstance(x, dict)][:4]
    if not src:
        src = [{"title": v.get("headline") or "Contexto", "body": v.get("subheadline", "")}]
    out, used = [], set()
    for i, e in enumerate(src):
        title = str(e.get("title") or e.get("date") or f"Etapa {i + 1}")
        body = str(e.get("detail") or e.get("body") or "")
        ic = e.get("icone") if e.get("icone") in ICONS else pick_icon(f"{title} {body}", i, used)
        used.add(ic)
        out.append({"title": title, "body": body, "value": str(e.get("value") or ""),
                    "date": str(e.get("date") or ""), "icon": ic})
    return out


def chart_style(ch, pairs):
    s = norm(ch.get("style") or ch.get("tipo") or "")
    if any(k in s for k in ("pizza", "rosca", "donut", "pie")):
        return "donut"
    if any(k in s for k in ("linha", "line")):
        return "line"
    if "bar" in s:
        return "bars"
    total = sum(v for _, v in pairs)
    if "%" in str(ch.get("unit", "")) and 95 <= total <= 105 and len(pairs) <= 5 and all(v >= 0 for _, v in pairs):
        return "donut"
    if len(pairs) >= 3 and all(re.fullmatch(r"\d{4}", l.strip()) for l, _ in pairs):
        return "line"
    return "bars"


# ------------------------------------------------------------------ moldura
def chrome_layer(W, H, vert, channel, category, index, total, has_media):
    if has_media:
        img = Image.new("RGBA", (W, H), (4, 13, 29, 0))
        img.putalpha(Image.linear_gradient("L").resize((W, H)).point(lambda v: int(150 + v * 0.3)))
    else:
        img = bn.gradient_background(W, H).convert("RGBA")
    d = ImageDraw.Draw(img)
    m = int(W * (0.065 if vert else 0.055))
    hh = 150 if vert else 112
    d.rectangle((0, 0, W, hh), fill=(4, 13, 29, 255))
    d.rectangle((0, hh - 7, W, hh), fill=CYAN + (255,))
    logo = bn.ROOT / "logo.png"
    placed = False
    if logo.is_file():
        try:
            lg = Image.open(logo).convert("RGBA")
            lg.thumbnail((W // 2, hh - 40), Image.LANCZOS)
            img.alpha_composite(lg, ((W - lg.width) // 2, (hh - 7 - lg.height) // 2))
            placed = True
        except OSError:
            pass
    if not placed:
        brand, bf = str(channel or "CANAL").upper()[:28], F(34, True)
        d.text((W // 2, (hh - 7) // 2), brand, font=bf, fill=WHITE + (255,), anchor="mm")

    ty = H - 57
    d.rectangle((0, ty - 14, W, ty - 8), fill=RED + (255,))
    d.rectangle((0, ty - 8, W, H), fill=(10, 67, 103, 255))
    d.text((m, ty + 6), f"{category.upper()}   •   FATOS   •   CONTEXTO   •   DADOS   •   {index:02d}/{total:02d}",
           font=F(19, True), fill=WHITE + (255,))
    return img, m, hh


def ffmpeg_cmd(W, H, frames, partial, media):
    base = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    raw = ["-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"]
    enc = ["-an", "-frames:v", str(frames), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
           "-pix_fmt", "yuv420p", str(partial)]
    if not media:
        return base + raw + enc
    if media.suffix.lower() in bn.cv.EXT_VIDEO:
        inp = ["-stream_loop", "-1", "-i", str(media.resolve())]
        bg = f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1"
    else:
        w2, h2 = int(W * 1.25) // 2 * 2, int(H * 1.25) // 2 * 2
        inp = ["-loop", "1", "-framerate", str(FPS), "-i", str(media.resolve())]
        bg = (f"[0:v]scale={w2}:{h2}:force_original_aspect_ratio=increase,crop={w2}:{h2},"
              f"zoompan=z='min(1+on*0.0005,1.12)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
              f"d=1:s={W}x{H}:fps={FPS},setsar=1")
    fc = (bg + ",eq=saturation=0.85[bg];[1:v]format=rgba[fg];"
          "[bg][fg]overlay=0:0:format=auto:shortest=1,format=yuv420p[v]")
    return base + inp + raw + ["-filter_complex", fc, "-map", "[v]"] + enc


# ------------------------------------------------------------------ clipe animado
def render_motion_clip(scene, index, total, channel, category, fmt, duration, dest: Path, media=None):
    W, H = bn.WIDTHS[fmt]
    vert = fmt == "9x16"
    chrome, m, hh = chrome_layer(W, H, vert, channel, category, index, total, bool(media))
    v = scene.get("visual") if isinstance(scene.get("visual"), dict) else {}
    kind = v.get("type", "bullets")
    probe = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    narr = str(scene.get("narracao", ""))

    kf, tf, sf = F(20, True), F(48 if vert else 56, True), F(26)
    kicker = str(v.get("kicker") or category or "INFORMACAO").upper()[:36]
    title = str(v.get("headline") or narr.split(".")[0])
    ky = hh + (44 if vert else 34)
    title_y = ky + 66
    tlines = wrap(probe, title, tf, W - 2 * m, 3 if vert else 2)
    sub_y = title_y + len(tlines) * (tf.size + 8) + 10
    slines = wrap(probe, v.get("subheadline", ""), sf, W - 2 * m, 2)
    top = sub_y + len(slines) * (sf.size + 6) + 40
    bottom = H - 110
    start = 0.9
    accent = RED if kind == "timeline" else CYAN

    nodes = nodes_of(v)
    n = len(nodes)
    step = min(1.4, max(0.55, (duration * 0.6 - start) / max(1, n)))

    pairs, style = [], "bars"
    ch = v.get("chart") if isinstance(v.get("chart"), dict) else {}
    if kind == "chart":
        for lb, val in zip((ch.get("labels") or [])[:6], (ch.get("values") or [])[:6]):
            try:
                pairs.append((str(lb), float(val)))
            except (TypeError, ValueError):
                pass
        if pairs:
            style = chart_style(ch, pairs)
        else:
            kind = "bullets"
    unit = str(ch.get("unit") or "")
    stat = parse_number(str(v.get("value") or "")) if kind == "stat" else None
    imp_rows, n_groups = [], 1
    if kind == "impacto":
        big = F(100 if vert else 108, True)
        for gi, ln in enumerate([str(x) for x in (v.get("linhas") or [])][:4] or [title]):
            for row in wrap(probe, ln, big, W - 2 * m, 3):
                imp_rows.append((gi, row))
        tlines, slines, start = [], [], 0.3
        n_groups = (imp_rows[-1][0] + 1) if imp_rows else 1

    # ---- textos com efeito de digitacao (citacao, manchete, definicao)
    typed_lines, typed_font, typed_dur, chips = [], None, 0.0, []
    hr = 110 if not vert else 95
    tx = m + 2 * hr + 70 if not vert else m
    ty0 = top + 10 if not vert else top + 2 * hr + 40
    if kind == "quote":
        typed_font = F(40 if vert else 44, True)
        typed_lines = wrap(probe, v.get("quote") or v.get("subheadline") or title, typed_font, W - 2 * m - 60, 6)
    elif kind in ("headline", "definition"):
        typed_font = F(38 if vert else 42, True)
        msg = v.get("definition") or v.get("key_message") or narr
        typed_lines = wrap(probe, msg, typed_font, W - m - tx, 6 if vert else 5)
        chips = [x["title"][:22].upper() for x in nodes][:3] if v.get("items") else []
    nwords = sum(len(l.split()) for l in typed_lines) or 1
    if typed_lines:
        typed_dur = min(max(1.0, duration * 0.6 - start), nwords * 0.13)

    anim_end = start + {
        "flow": n * step + 0.4, "timeline": n * step + 0.6, "comparison": 1.5, "bullets": n * 0.5 + 0.7,
        "stat": 2.4, "impacto": n_groups * 0.6 + 1.0, "quote": typed_dur + 0.7,
        "headline": typed_dur + 0.4 + len(chips) * 0.25 + 0.5,
        "definition": typed_dur + 0.4 + len(chips) * 0.25 + 0.5,
        "chart": {"bars": 0.3 * len(pairs) + 1.2, "donut": 1.0 + 0.2 * len(pairs) + 0.6, "line": 2.3}[style],
    }.get(kind, 3.0)

    # ---- layout fluxo (icone -> seta -> icone)
    if vert:
        slot = (bottom - top) / max(1, n)
        r = int(min(85, slot * 0.34))
        pos = [(m + r + 10, int(top + (i + .5) * slot)) for i in range(n)]
    else:
        slot = (W - 2 * m) / max(1, n)
        r = int(min(115, (bottom - top) * 0.24, slot / 2 - 40))
        pos = [(int(m + (i + .5) * slot), top + r + 20) for i in range(n)]

    def lay_flow(layer, d, t):
        for i, nd in enumerate(nodes):
            appear = start + i * step
            cx, cy = pos[i]
            if i < n - 1:
                nx, ny = pos[i + 1]
                p0, p1 = ((cx, cy + r + 12), (nx, ny - r - 12)) if vert else ((cx + r + 14, cy), (nx - r - 14, ny))
                arrow(d, p0, p1, (t - appear - 0.35) / max(0.2, step - 0.4), GOLD)
            if t <= appear:
                continue
            paste_icon(layer, nd["icon"], cx, cy, r, (t - appear) / 0.45, accent)
            a = ease((t - appear - 0.2) / 0.4)
            if a <= 0:
                continue
            al, off = int(255 * a), 20 * (1 - a)
            if vert:
                x, y, mw = cx + r + 30, cy - r + off, W - m - (cx + r + 30)
                if nd["value"]:
                    y = text_block(d, x, y, [nd["value"][:20]], F(34, True), GOLD + (al,))
                y = text_block(d, x, y, wrap(d, nd["title"], F(32, True), mw, 2), F(32, True), accent + (al,))
                text_block(d, x, y + 4, wrap(d, nd["body"], F(25), mw, 3), F(25), LIGHT + (al,))
            else:
                y, mw = cy + r + 24 + off, slot - 30
                if nd["value"]:
                    y = text_block(d, cx, y, [nd["value"][:20]], F(36, True), GOLD + (al,), center=True)
                y = text_block(d, cx, y, wrap(d, nd["title"], F(32, True), mw, 2), F(32, True), accent + (al,), center=True)
                text_block(d, cx, y + 6, wrap(d, nd["body"], F(24), mw, 3), F(24), LIGHT + (al,), center=True)

    # ---- lista de cartoes deslizando (bullets)
    def lay_list(layer, d, t):
        gap = 18
        rh = int(min(260 if vert else 190, (bottom - top - gap * (n - 1)) / max(1, n)))
        for i, nd in enumerate(nodes):
            a = ease((t - start - i * 0.5) / 0.5)
            if a <= 0:
                continue
            y, x = top + i * (rh + gap), int(m - 80 * (1 - a))
            d.rounded_rectangle((x, y, x + W - 2 * m, y + rh), radius=18, fill=NAVY + (int(215 * a),),
                                outline=CYAN + (int(255 * a),), width=2)
            d.rectangle((x, y + 12, x + 8, y + rh - 12), fill=GOLD + (int(255 * a),))
            ir = int(rh * 0.32)
            paste_icon(layer, nd["icon"], x + 40 + ir, y + rh // 2, ir, (t - start - i * 0.5 - 0.1) / 0.45, CYAN)
            lx, mw = x + 80 + 2 * ir, W - m - (x + 80 + 2 * ir) - 30
            tl = wrap(d, nd["title"], F(32, True), mw, 1)
            bl = wrap(d, nd["body"], F(24), mw, 2 if not vert else 3)
            yy = y + (rh - (len(tl) * 50 + len(bl) * 40)) // 2
            yy = text_block(d, lx, yy, tl, F(32, True), WHITE + (int(255 * a),))
            text_block(d, lx, yy, bl, F(24), LIGHT + (int(255 * a),))

    # ---- comparacao com paineis e "VS"
    def lay_compare(layer, d, t):
        pair = (nodes + nodes)[:2]
        gap = 110 if not vert else 90
        if vert:
            pw = W - 2 * m
            ph = int(min((bottom - top - gap) / 2, 2 * min(70, 200) + 80 + 2 * 56 + 3 * 46 + 60))
        else:
            pw, ph = int((W - 2 * m - gap) / 2), bottom - top
        for i, (nd, col) in enumerate(zip(pair, (CYAN, RED))):
            a = ease((t - start - i * 0.35) / 0.5)
            if a <= 0:
                continue
            if vert:
                x0, y0 = m, int(top + i * (ph + gap) + 40 * (1 - a))
            else:
                x0, y0 = int(m + i * (pw + gap) + (-80 if i == 0 else 80) * (1 - a)), top
            d.rounded_rectangle((x0, y0, x0 + pw, y0 + ph), radius=22, fill=NAVY + (int(220 * a),),
                                outline=col + (int(255 * a),), width=3)
            ir = int(min(70, ph * 0.17))
            cx = x0 + pw // 2
            paste_icon(layer, nd["icon"], cx, y0 + ir + 28, ir, (t - start - i * 0.35 - 0.15) / 0.45, col)
            y = y0 + 2 * ir + 50
            al = int(255 * a)
            if nd["value"]:
                y = text_block(d, cx, y, [nd["value"][:18]], F(44, True), GOLD + (al,), center=True)
            y = text_block(d, cx, y, wrap(d, nd["title"], F(34, True), pw - 60, 2), F(34, True), col + (al,), center=True)
            text_block(d, cx, y + 8, wrap(d, nd["body"], F(26), pw - 60, 4 if not vert else 3), F(26), LIGHT + (al,), center=True)
        p = (t - start - 0.8) / 0.4
        if p > 0:
            rr = int(46 * back(p))
            cx, cy = (W // 2, top + ph + gap // 2) if vert else (m + pw + gap // 2, top + ph // 2)
            d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), fill=GOLD + (255,))
            d.text((cx, cy), "VS", font=F(max(10, int(rr * 0.8)), True), fill=NAVY + (255,), anchor="mm")

    # ---- linha do tempo
    def lay_timeline(layer, d, t):
        p = clamp((t - start) / (n * step))
        for i, nd in enumerate(nodes):
            q = (t - start - (i + .5) * step) / 0.4
            date = nd["date"] or nd["title"]
            label = nd["title"] if nd["title"] != date else ""
            if not vert:
                ly, slot2 = top + int((bottom - top) * 0.36), (W - 2 * m) / n
                if i == 0:
                    d.line((m, ly, m + (W - 2 * m) * p, ly), fill=WHITE + (210,), width=6)
                if q <= 0:
                    continue
                cx, a = int(m + (i + .5) * slot2), int(255 * ease(q))
                rr = int(22 * back(q))
                d.ellipse((cx - rr, ly - rr, cx + rr, ly + rr), fill=RED + (255,), outline=WHITE + (255,), width=4)
                text_block(d, cx, ly - 95, wrap(d, date, F(40, True), slot2 - 20, 1), F(40, True), GOLD + (a,), center=True)
                y = ly + 45
                if label:
                    y = text_block(d, cx, y, wrap(d, label, F(30, True), slot2 - 30, 2), F(30, True), WHITE + (a,), center=True)
                text_block(d, cx, y + 6, wrap(d, nd["body"], F(23), slot2 - 30, 3), F(23), LIGHT + (a,), center=True)
            else:
                lx, slot2 = m + 30, (bottom - top) / n
                if i == 0:
                    d.line((lx, top, lx, top + (bottom - top) * p), fill=WHITE + (210,), width=6)
                if q <= 0:
                    continue
                cy, a = int(top + (i + .5) * slot2), int(255 * ease(q))
                rr = int(20 * back(q))
                d.ellipse((lx - rr, cy - rr, lx + rr, cy + rr), fill=RED + (255,), outline=WHITE + (255,), width=4)
                x, mw = lx + 50, W - m - lx - 50
                y = text_block(d, x, cy - 50, [date[:24]], F(38, True), GOLD + (a,))
                if label:
                    y = text_block(d, x, y, wrap(d, label, F(30, True), mw, 2), F(30, True), WHITE + (a,))
                text_block(d, x, y + 4, wrap(d, nd["body"], F(24), mw, 2), F(24), LIGHT + (a,))

    # ---- texto digitado (manchete, definicao, citacao)
    def typed(d, x, y, t, fill, gap=10):
        k = int(nwords * clamp((t - start) / max(0.1, typed_dur)))
        used = 0
        for ln in typed_lines:
            ws = ln.split()
            show = ws[:max(0, k - used)]
            used += len(ws)
            if show:
                d.text((x, y), " ".join(show), font=typed_font, fill=fill)
            y += typed_font.size + gap
        return y

    def lay_headline(layer, d, t):
        ic = pick_icon(title + " " + narr, 0)
        cx, cy = (m + hr + 10, top + hr + 10) if not vert else (W // 2, top + hr)
        paste_icon(layer, ic, cx, cy, hr, (t - start + 0.3) / 0.5, CYAN)
        y = typed(d, tx, ty0, t, WHITE + (255,))
        cx2 = tx
        for i, chip in enumerate(chips):
            p = (t - start - typed_dur - 0.3 - i * 0.25) / 0.35
            if p <= 0:
                continue
            w = d.textlength(chip, font=F(24, True)) + 36
            s = back(p)
            d.rounded_rectangle((cx2, y + 30, cx2 + w * s, y + 30 + 50 * s), radius=12, fill=RED + (int(255 * ease(p)),))
            if p >= 1:
                d.text((cx2 + 18, y + 42), chip, font=F(24, True), fill=WHITE + (255,))
            cx2 += w + 16

    def lay_quote(layer, d, t):
        d.text((m, top - 30), "“", font=F(140, True), fill=GOLD + (int(255 * ease((t - start + .4) / .4)),))
        y = typed(d, m + 60, top + 60, t, WHITE + (255,), gap=12)
        att = str(v.get("attribution") or "")
        if att and t > start + typed_dur:
            d.text((m + 60, y + 20), "— " + att[:60], font=F(28),
                   fill=CYAN + (int(255 * ease((t - start - typed_dur) / .4)),))

    # ---- numero em destaque (com anel se for %)
    def lay_stat(layer, d, t):
        ic = pick_icon(str(v.get("value_label", "")) + " " + title, 0)
        rr = 110 if vert else 130
        cx, cy = (W // 2, top + rr + 30) if vert else (m + rr + 30, (top + bottom) // 2 - 40)
        paste_icon(layer, ic, cx, cy, rr, (t - start) / 0.5, CYAN)
        p = ease((t - start - 0.2) / 1.6)
        if stat:
            pre, num, dec, suf = stat
            txt = f"{pre}{fmt_br(num * p, dec)}{suf}"
            if "%" in suf and 0 < num <= 100 and p > 0:
                d.arc((cx - rr - 20, cy - rr - 20, cx + rr + 20, cy + rr + 20), -90, -90 + 360 * num / 100 * p,
                      fill=GOLD + (255,), width=14)
        else:
            txt = str(v.get("value") or "DADO")[:24]
        vf = F(110 if vert else 140, True)
        a = int(255 * ease((t - start) / 0.4))
        la = WHITE + (int(255 * ease((t - start - 1) / 0.5)),)
        if vert:
            y = text_block(d, W // 2, cy + rr + 50, [txt], vf, GOLD + (a,), center=True)
            text_block(d, W // 2, y + 20, wrap(d, v.get("value_label", ""), F(36, True), W - 2 * m, 3), F(36, True), la, center=True)
        else:
            x = cx + rr + 80
            d.text((x, cy - vf.size // 2 - 20), txt, font=vf, fill=GOLD + (a,))
            text_block(d, x, cy + vf.size // 2, wrap(d, v.get("value_label", ""), F(38, True), W - m - x, 3), F(38, True), la)

    # ---- graficos: barras, pizza/rosca e linha
    def lay_bars(layer, d, t):
        mx = max(max(abs(x) for _, x in pairs), 1)
        gap = 22
        bh = int(min(90, (bottom - top - 40 - gap * (len(pairs) - 1)) / len(pairs)))
        lw = int((W - 2 * m) * (0.32 if vert else 0.26))
        bw = W - 2 * m - lw - 170
        for i, (lb, val) in enumerate(pairs):
            p = ease((t - start - i * 0.3) / 0.8)
            if p <= 0:
                continue
            y, a = top + i * (bh + gap), int(255 * min(1, p * 2))
            text_block(d, m, y + 6, wrap(d, lb, F(24, True), lw - 16, 2), F(24, True), LIGHT + (a,))
            bx = m + lw
            d.rounded_rectangle((bx, y, bx + bw, y + bh - 6), radius=(bh - 6) // 2, fill=(18, 59, 88, int(a * .85)))
            fw = max(bh, int(bw * abs(val) / mx * p))
            d.rounded_rectangle((bx, y, bx + fw, y + bh - 6), radius=(bh - 6) // 2, fill=PALETTE[i % 6] + (255,))
            d.text((bx + bw + 16, y + bh // 2 - 18), f"{val * p:g}", font=F(30, True), fill=GOLD + (a,))
        if unit:
            d.text((m, bottom - 36), unit, font=F(22), fill=LIGHT + (int(255 * ease((t - start) / .5)),))

    def lay_donut(layer, d, t):
        if vert:
            R = int(min((W - 2 * m) * 0.38, (bottom - top) * 0.28))
            cx, cy = W // 2, top + R + 20
        else:
            R = int(min((bottom - top) * 0.42, (W - 2 * m) * 0.25))
            cx, cy = m + R + 20, (top + bottom) // 2
        p, tot, ang = ease((t - start) / 1.4), sum(v2 for _, v2 in pairs) or 1, -90.0
        for i, (_, val) in enumerate(pairs):
            sweep = 360 * val / tot
            end = min(ang + sweep, -90 + 360 * p)
            if end > ang:
                d.pieslice((cx - R, cy - R, cx + R, cy + R), ang, end, fill=PALETTE[i % 6] + (255,))
            ang += sweep
        ir = int(R * 0.58)
        if p > 0:
            d.ellipse((cx - ir, cy - ir, cx + ir, cy + ir), fill=NAVY + (255,))
        x, y = (cx + R + 80, cy - len(pairs) * 32) if not vert else (m, cy + R + 50)
        for i, (lb, val) in enumerate(pairs):
            a = int(255 * ease((t - start - 1.0 - 0.2 * i) / 0.4))
            if a <= 0:
                continue
            d.rounded_rectangle((x, y + 8, x + 30, y + 38), radius=6, fill=PALETTE[i % 6] + (a,))
            d.text((x + 48, y), f"{lb[:28]}  ", font=F(30, True), fill=WHITE + (a,))
            d.text((x + 48 + d.textlength(f"{lb[:28]}  ", font=F(30, True)), y), f"{val:g}{unit if '%' in unit else ''}",
                   font=F(30, True), fill=GOLD + (a,))
            y += 64

    def lay_line(layer, d, t):
        x0, x1, y0, y1 = m + 90, W - m - 40, top + 30, bottom - 70
        a0 = int(255 * ease((t - start) / 0.5))
        d.line((x0, y0, x0, y1, x1, y1), fill=LIGHT + (a0,), width=4)
        vals = [v2 for _, v2 in pairs]
        mn, mx = min(0, min(vals)), max(vals)
        span = (mx - mn) or 1
        N = len(pairs)
        pts = [(x0 + 30 + (x1 - x0 - 60) * (i / (N - 1) if N > 1 else .5), y1 - (y1 - y0) * (v2 - mn) / span) for i, v2 in enumerate(vals)]
        for i, (lb, _) in enumerate(pairs):
            text_block(d, pts[i][0], y1 + 14, [lb[:12]], F(24, True), LIGHT + (a0,), center=True)
        seg = clamp((t - start - 0.3) / 1.8) * (N - 1)
        for i in range(N - 1):
            if seg <= i:
                break
            f = min(1.0, seg - i)
            (ax, ay), (bx, by) = pts[i], pts[i + 1]
            d.line((ax, ay, ax + (bx - ax) * f, ay + (by - ay) * f), fill=CYAN + (255,), width=8)
        for i, (px, py) in enumerate(pts):
            if seg + 0.001 >= i and t > start + 0.3:
                d.ellipse((px - 12, py - 12, px + 12, py + 12), fill=GOLD + (255,), outline=WHITE + (255,), width=3)
                text_block(d, px, py - 52, [f"{vals[i]:g}"], F(28, True), WHITE + (255,), center=True)
        if unit:
            d.text((m, y0 - 40), unit, font=F(22), fill=LIGHT + (a0,))

    # ---- impacto (frases grandes com destaque)
    def lay_impact(layer, d, t):
        big = F(100 if vert else 108, True)
        hl = {norm(w).strip(".,!?:;\"'") for w in str(v.get("destaque", "")).split()}
        lh = big.size + 22
        y = (hh + bottom) // 2 - len(imp_rows) * lh // 2
        sp = d.textlength(" ", font=big)
        for gi, row in imp_rows:
            a = ease((t - start - gi * 0.6) / 0.35)
            if a > 0:
                words = row.split()
                ws = [d.textlength(w, font=big) for w in words]
                x = W / 2 - (sum(ws) + sp * (len(words) - 1)) / 2
                off, al = 30 * (1 - a), int(255 * a)
                for w, ww in zip(words, ws):
                    hit = norm(w).strip(".,!?:;\"'") in hl
                    d.text((x, y + off), w, font=big, fill=(RED if hit else WHITE) + (al,),
                           stroke_width=5, stroke_fill=(0, 0, 0, int(210 * a)))
                    if hit:
                        u = ease((t - start - gi * 0.6 - 0.35) / 0.4)
                        if u > 0:
                            d.rectangle((x, y + big.size + 10, x + ww * u, y + big.size + 22), fill=RED + (255,))
                    x += ww + sp
            y += lh

    layouts = {"flow": lay_flow, "impacto": lay_impact, "timeline": lay_timeline, "comparison": lay_compare,
               "bullets": lay_list, "headline": lay_headline, "definition": lay_headline, "quote": lay_quote,
               "stat": lay_stat, "chart": {"bars": lay_bars, "donut": lay_donut, "line": lay_line}[style]}
    draw_main = layouts.get(kind, lay_list)

    def frame_at(t):
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        a = ease(t / 0.45)
        kx = m - 60 * (1 - a)
        kw = d.textlength(kicker, font=kf) + 30
        d.rounded_rectangle((kx, ky, kx + kw, ky + 42), radius=9, fill=RED + (int(255 * a),))
        d.text((kx + 15, ky + 9), kicker, font=kf, fill=(255, 255, 255, int(255 * a)))
        a2 = ease((t - 0.25) / 0.6)
        text_block(d, m, title_y + 25 * (1 - a2), tlines, tf, WHITE + (int(255 * a2),), gap=8)
        text_block(d, m, sub_y, slines, sf, (180, 215, 236, int(255 * ease((t - 0.5) / 0.5))))
        draw_main(layer, d, t)
        frame = chrome.copy()
        frame.alpha_composite(layer)
        return frame

    frames = max(1, round(duration * FPS))
    partial = dest.with_name(dest.stem + ".parcial.mp4")
    proc = subprocess.Popen(ffmpeg_cmd(W, H, frames, partial, media), stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    static = None
    try:
        for f in range(frames):
            t = f / FPS
            if t >= anim_end and static is not None:
                buf = static
            else:
                buf = frame_at(t).tobytes()
                if t >= anim_end:
                    static = buf
            proc.stdin.write(buf)
    except BrokenPipeError:
        pass
    finally:
        try:
            proc.stdin.close()
        except OSError:
            pass
        err = proc.stderr.read().decode("utf-8", "replace")
        proc.wait()
    if proc.returncode != 0:
        raise bn.BroadcastError("FFmpeg falhou na cena animada: " + err[-900:])
    partial.replace(dest)


# ------------------------------------------------------------------ montagem
def render_format(script, durations, narration, project_dir, fmt, channel, category):
    out_dir = project_dir / "saida"
    out_dir.mkdir(parents=True, exist_ok=True)
    final = out_dir / f"{bn.slug(script['titulo'])}_{fmt}.mp4"
    if final.exists() and final.stat().st_size > 20_000:
        bn.info(f"   [{fmt}] arquivo final ja existe; reaproveitando.")
        return final
    work = project_dir / "motion_assets" / fmt
    clips_dir = work / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    name = str(channel.get("nome", "Canal"))
    total = len(script["cenas"])
    clips = []
    for i, (scene, dur) in enumerate(zip(script["cenas"], durations), 1):
        clip = clips_dir / f"cena_{i:03d}.mp4"
        if not (clip.exists() and clip.stat().st_size > 10_000):
            media = bn.find_scene_media(project_dir, i)
            bn.info(f"   [{fmt}] animando cena {i}/{total}" + (f" sobre {media.name}" if media else ""))
            render_motion_clip(scene, i, total, name, category, fmt, dur, clip, media)
        clips.append(clip)
    (clips_dir / "concat.txt").write_text("\n".join(f"file '{p.name}'" for p in clips) + "\n", encoding="utf-8")
    silent = work / "video_sem_audio.mp4"
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
                        "-i", "concat.txt", "-c", "copy", str(silent)], cwd=clips_dir,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise bn.BroadcastError("Nao foi possivel unir as cenas: " + (r.stderr or "")[-900:])
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(silent), "-i", str(narration),
                        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                        "-shortest", "-movflags", "+faststart", str(final)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise bn.BroadcastError("Nao foi possivel adicionar a narracao: " + (r.stderr or "")[-900:])
    return final


# ------------------------------------------------------------------ roteiro
_orig_prompt = bn.make_research_prompt
_orig_sim = bn.simulated_script


ESTILOS = {
    "economia": """
ESTILO (Economia para o povo - TikTok/Reels):
- Tema: assunto ATUAL que mexe no bolso do brasileiro comum (dolar, INSS, inflacao, bets, Pix, impostos, juros, salario).
- Titulo: pergunta simples. Ex: "Como a alta do dolar afeta voce?", "O que e Split Payment?".
- Gancho (1a cena): pergunta curiosa + retencao ("Aposto que voce nao sabia dessa").
- Texto: frases curtas, linguagem do dia a dia, zero jargao.
- Final: pergunta de debate ou relato pessoal. Ex: "Ja teve compra taxada? Me conta aqui." Proibido final generico.""",
    "humor": """
ESTILO (Humor acido):
- Situacoes do cotidiano brasileiro com ironia, sarcasmo inteligente e duplo sentido, sem ofender grupos.
- Gancho: frase provocativa ou absurda.
- Final: pergunta de duplo sentido ou provocacao leve.""",
    "curiosidade": """
ESTILO (Curiosidades):
- Fatos surpreendentes que a maioria nao conhece.
- Gancho: "Aposto que voce nao sabia dessa..." + pergunta intrigante.
- Final: pergunta para contar se sabia ou marcar alguem.""",
}
ESTILO_PADRAO = """
ESTILO (rede social): tema atual e popular, titulo em pergunta simples, gancho curioso com frase de retencao, frases curtas, final com pergunta de debate ou relato pessoal."""


def make_research_prompt(channel, topic, duration, category):
    base = _orig_prompt(channel, topic, duration, category)
    cat = norm(category)
    estilo = next((txt for k, txt in ESTILOS.items() if k in cat), ESTILO_PADRAO)
    return base + MOTION_RULES + estilo


def simulated_script(topic):
    s = _orig_sim(topic)
    demo = "Valor ficticio, apenas para testar a animacao"
    s["cenas"] = s["cenas"][:2] + [
        {"narracao": "Este numero em destaque e ficticio e serve so para testar o contador animado.",
         "visual": {"type": "stat", "kicker": "DADO · DEMONSTRACAO", "headline": "Contador animado", "value": "75%", "value_label": demo}},
        {"narracao": "Aqui as barras crescem uma a uma, comparando tres itens ficticios.",
         "visual": {"type": "chart", "kicker": "GRAFICO · DEMONSTRACAO", "headline": "Barras crescendo",
                    "chart": {"labels": ["Item A", "Item B", "Item C"], "values": [12, 30, 21], "unit": "pontos (ficticio)", "style": "barras"}}},
        {"narracao": "Uma linha do tempo mostra as fases em sequencia, com datas surgindo no ritmo da narracao.",
         "visual": {"type": "timeline", "kicker": "LINHA DO TEMPO", "headline": "Fases do processo",
                    "events": [{"date": "Fase 1", "title": "Origem", "detail": "Ponto de partida", "icone": "relogio"},
                               {"date": "Fase 2", "title": "Mudanca", "detail": "A virada", "icone": "documento"},
                               {"date": "Fase 3", "title": "Hoje", "detail": "O resultado", "icone": "alvo"}]}},
        {"narracao": "O grafico de linha mostra uma evolucao ficticia ao longo dos anos.",
         "visual": {"type": "chart", "kicker": "EVOLUCAO · DEMONSTRACAO", "headline": "Grafico de linha",
                    "chart": {"labels": ["2019", "2020", "2021", "2022", "2023"], "values": [10, 14, 9, 18, 24], "unit": "indice ficticio", "style": "linha"}}},
        {"narracao": "E a rosca divide um todo em partes, tambem com valores ficticios.",
         "visual": {"type": "chart", "kicker": "PARTES DO TODO · DEMONSTRACAO", "headline": "Grafico de rosca",
                    "chart": {"labels": ["Grupo A", "Grupo B", "Grupo C"], "values": [50, 30, 20], "unit": "%", "style": "pizza"}}},
        {"narracao": "E o impacto mostra frases grandes com a palavra principal em destaque.",
         "visual": {"type": "impacto", "linhas": ["Produto chega do exterior", "E TAXADO"], "destaque": "TAXADO"}},
    ] + s["cenas"][2:]
    return s


bn.make_research_prompt = make_research_prompt
bn.simulated_script = simulated_script
bn.render_format = render_format

if __name__ == "__main__":
    if not hasattr(bn, "main"):
        print("ERRO: broadcast_news.py nao possui main().")
        sys.exit(1)
    bn.main()