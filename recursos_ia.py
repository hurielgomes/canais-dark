"""recursos_ia.py - CRIA recursos novos da biblioteca M1 (SVG/JSON) a partir de um pedido do roteiro.

Fluxo de um recurso novo:   spec {id, tipo, nome, tags, descricao, clima}
    1. IA (opcional) escreve um SVG seguindo as regras do importador  ->  validado e testado num quadro de prova
    2. se a IA nao existir/falhar, um gerador procedural (icones, cidades, interiores, natureza) cria o recurso
    3. animacoes prontas (parado, balancar, pulsar, piscar, flutuar, tremer) sao geradas por JSON para qualquer SVG
    4. o recurso e registrado e aprovado na biblioteca  ->  passa a poder ser reutilizado por qualquer video

Nada e executado: SVG/JSON passam pelo mesmo validador do M1.
"""
import hashlib
import json
import random
import re
import tempfile
import unicodedata
from pathlib import Path

import recursos_ativos as A
from estudio.cenas2d.recursos.biblioteca import Biblioteca
from estudio.cenas2d.recursos.svg import importar_svg
from estudio.cenas2d.recursos.validar import RecursoInvalido, validar_recurso

# ------------------------------------------------------------------ util
CLIMAS = {  # nome -> (ceu_topo, ceu_base, luz_janela_acesa, fracao_janelas_acesas, ambiente_cor, ambiente_forca)
    "noite": ("#070b24", "#1b2a5c", "#ffd37a", 0.55, "#0a1030", 0.22),
    "dia": ("#4a90e2", "#bfe3ff", "#fff3c4", 0.05, "#fff0c0", 0.06),
    "entardecer": ("#2a1650", "#ff9a5a", "#ffd37a", 0.35, "#40102a", 0.14),
    "alerta": ("#1a0508", "#7a1a22", "#ff6a5a", 0.25, "#500a0a", 0.22),
    "apagado": ("#03040c", "#0d1228", "#2a3350", 0.04, "#02030a", 0.34),
}


def slug(txt):
    t = unicodedata.normalize("NFKD", str(txt or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "_", t).strip("_")[:48] or "recurso"


def _rng(chave):
    return random.Random(int(hashlib.sha1(str(chave).encode()).hexdigest()[:8], 16))


def _grad(i, a, b):
    return (f'<linearGradient id="{i}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{a}"/>'
            f'<stop offset="1" stop-color="{b}"/></linearGradient>')


def _glow(cx, cy, r, cor, a=0.22, n=4):
    return "".join(f'<circle cx="{cx}" cy="{cy}" r="{r * (1 + k * 0.45):.0f}" fill="{cor}" opacity="{a / (k + 1):.3f}"/>' for k in range(n))


def _svg(vb, corpo, defs=""):
    w, h = vb
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}"><defs>{defs}</defs>{corpo}</svg>'


# ------------------------------------------------------------------ icones procedurais (objetos), viewBox 200x200
def _ic(corpo, brilho_cor="#ffd37a"):
    return _svg((200, 200), f'<g id="brilho">{_glow(100, 100, 70, brilho_cor)}</g><g id="corpo">{corpo}</g>')


ICONES = {
    "lampada": lambda c: _ic(f'<circle cx="100" cy="82" r="46" fill="{c}"/><path d="M80 120 L120 120 L116 150 L84 150 Z" fill="#8a8f9c"/>'
                             '<rect x="82" y="150" width="36" height="12" rx="4" fill="#5b6070"/><path d="M88 60 Q100 44 112 60" stroke="#fff" stroke-width="6" fill="none" opacity="0.7"/>', c),
    "raio": lambda c: _ic(f'<path d="M115 20 L55 112 L96 112 L80 182 L148 84 L106 84 Z" fill="{c}" stroke="#fff6c8" stroke-width="4"/>', c),
    "celular": lambda c: _ic('<rect x="58" y="16" width="84" height="168" rx="16" fill="#1c2030" stroke="#8a93b0" stroke-width="4"/>'
                             f'<rect x="66" y="34" width="68" height="124" rx="6" fill="{c}" opacity="0.85"/><circle cx="100" cy="171" r="6" fill="#8a93b0"/>', c),
    "cruz": lambda c: _ic('<rect x="36" y="36" width="128" height="128" rx="22" fill="#f4f6fa"/>'
                          f'<path d="M84 56 H116 V84 H144 V116 H116 V144 H84 V116 H56 V84 H84 Z" fill="{c}"/>', c),
    "casa": lambda c: _ic(f'<path d="M24 98 L100 30 L176 98 Z" fill="#b5452f"/><rect x="42" y="98" width="116" height="78" fill="#d9c6a0"/>'
                          f'<rect x="88" y="128" width="26" height="48" fill="#6a4a30"/><rect x="54" y="112" width="24" height="24" fill="{c}"/>', c),
    "predio": lambda c: _ic('<rect x="52" y="24" width="96" height="156" fill="#3a4262"/>' + "".join(
        f'<rect x="{64 + 28 * i}" y="{38 + 30 * j}" width="16" height="18" fill="{c}" opacity="{0.9 if (i + j) % 2 == 0 else 0.25}"/>'
        for i in range(3) for j in range(5)), c),
    "bateria": lambda c: _ic('<rect x="30" y="62" width="130" height="76" rx="10" fill="#2a2f40" stroke="#aab2cc" stroke-width="5"/><rect x="160" y="84" width="14" height="32" rx="3" fill="#aab2cc"/>'
                             f'<rect x="38" y="70" width="40" height="60" rx="5" fill="{c}"/><rect x="82" y="70" width="22" height="60" rx="5" fill="{c}" opacity="0.35"/>', c),
    "gota": lambda c: _ic(f'<path d="M100 22 C140 78 156 104 156 128 C156 160 130 180 100 180 C70 180 44 160 44 128 C44 104 60 78 100 22 Z" fill="{c}"/>'
                          '<path d="M76 130 Q78 154 98 160" stroke="#fff" stroke-width="7" fill="none" opacity="0.55"/>', c),
    "carro": lambda c: _ic(f'<path d="M22 126 L40 90 Q48 76 66 76 H134 Q152 76 162 92 L180 126 V146 H22 Z" fill="{c}"/>'
                           '<rect x="56" y="84" width="40" height="26" fill="#cfe6ff" opacity="0.8"/><rect x="104" y="84" width="34" height="26" fill="#cfe6ff" opacity="0.8"/>'
                           '<circle cx="58" cy="148" r="17" fill="#15171f"/><circle cx="146" cy="148" r="17" fill="#15171f"/>', c),
    "relogio": lambda c: _ic(f'<circle cx="100" cy="100" r="70" fill="#f3f1ea" stroke="{c}" stroke-width="9"/><path d="M100 100 V56 M100 100 L130 116" stroke="#2a2f40" stroke-width="8" stroke-linecap="round" fill="none"/>', c),
    "cadeado": lambda c: _ic(f'<path d="M66 90 V66 Q66 30 100 30 Q134 30 134 66 V90" stroke="#aab2cc" stroke-width="14" fill="none"/><rect x="48" y="88" width="104" height="82" rx="12" fill="{c}"/><circle cx="100" cy="124" r="10" fill="#222"/>', c),
    "sinal": lambda c: _ic(f'<path d="M30 78 Q100 14 170 78" stroke="{c}" stroke-width="12" fill="none" stroke-linecap="round"/><path d="M52 104 Q100 62 148 104" stroke="{c}" stroke-width="12" fill="none" stroke-linecap="round"/>'
                           f'<path d="M74 128 Q100 108 126 128" stroke="{c}" stroke-width="12" fill="none" stroke-linecap="round"/><circle cx="100" cy="152" r="9" fill="{c}"/>', c),
    "engrenagem": lambda c: _ic(f'<circle cx="100" cy="100" r="52" fill="{c}"/>' + "".join(
        f'<rect x="90" y="26" width="20" height="30" rx="4" fill="{c}" transform="rotate({a} 100 100)"/>' for a in range(0, 360, 45)) + '<circle cx="100" cy="100" r="20" fill="#20232e"/>', c),
    "pessoa": lambda c: _ic(f'<circle cx="100" cy="52" r="26" fill="#f0c9a0"/><path d="M52 176 Q52 100 100 100 Q148 100 148 176 Z" fill="{c}"/>', c),
    "cesta": lambda c: _ic(f'<path d="M30 84 H170 L150 168 H50 Z" fill="{c}"/><path d="M62 84 Q100 20 138 84" stroke="#8a6a3a" stroke-width="9" fill="none"/>', c),
    "estrela": lambda c: _ic(f'<path d="M100 22 L122 76 L180 80 L136 118 L150 176 L100 146 L50 176 L64 118 L20 80 L78 76 Z" fill="{c}"/>', c),
    "semaforo": lambda c: _ic('<rect x="68" y="16" width="64" height="168" rx="14" fill="#1b1e28"/>' + "".join(
        f'<circle cx="100" cy="{50 + 50 * k}" r="19" fill="{col}" opacity="{o}"/>' for k, (col, o) in enumerate((("#ff4a4a", 0.35), ("#ffd84a", 0.3), (c, 0.9)))), c),
}
# palavra (sem acento, prefixo) -> (icone, cor, nome)
CHAVES_ICONE = {
    "lampada": ("lampada", "#ffd37a", "Lampada"), "luz": ("lampada", "#ffd37a", "Lampada"), "ilumin": ("lampada", "#ffd37a", "Lampada"),
    "energia": ("raio", "#ffd23a", "Energia"), "eletric": ("raio", "#ffd23a", "Energia"), "apag": ("raio", "#ffd23a", "Energia"),
    "raio": ("raio", "#ffd23a", "Raio"), "tensao": ("raio", "#ffd23a", "Energia"), "gerador": ("engrenagem", "#9aa6c4", "Gerador"),
    "celular": ("celular", "#4aa8ff", "Celular"), "telefon": ("celular", "#4aa8ff", "Celular"), "smartphone": ("celular", "#4aa8ff", "Celular"),
    "hospital": ("cruz", "#e8353d", "Hospital"), "saude": ("cruz", "#e8353d", "Saude"), "medic": ("cruz", "#e8353d", "Saude"), "paciente": ("cruz", "#e8353d", "Saude"),
    "casa": ("casa", "#ffd37a", "Casa"), "moradia": ("casa", "#ffd37a", "Casa"),
    "predio": ("predio", "#ffd37a", "Predio"), "cidade": ("predio", "#ffd37a", "Predio"), "edific": ("predio", "#ffd37a", "Predio"),
    "bateria": ("bateria", "#6ee07a", "Bateria"), "carga": ("bateria", "#6ee07a", "Bateria"),
    "agua": ("gota", "#4aa8ff", "Agua"), "chuva": ("gota", "#4aa8ff", "Agua"), "bebida": ("gota", "#4aa8ff", "Agua"),
    "carro": ("carro", "#d9453a", "Carro"), "veicul": ("carro", "#d9453a", "Carro"), "transporte": ("carro", "#d9453a", "Carro"), "trafego": ("semaforo", "#6ee07a", "Semaforo"), "semaforo": ("semaforo", "#6ee07a", "Semaforo"),
    "cronometro": ("relogio", "#e8c14a", "Relogio"), "relogio": ("relogio", "#e8c14a", "Relogio"),
    "seguranca": ("cadeado", "#d9a02e", "Cadeado"), "banco": ("cadeado", "#d9a02e", "Cadeado"), "dinheiro": ("cadeado", "#d9a02e", "Cadeado"),
    "internet": ("sinal", "#4aa8ff", "Sinal"), "comunicac": ("sinal", "#4aa8ff", "Sinal"), "rede": ("sinal", "#4aa8ff", "Sinal"), "wifi": ("sinal", "#4aa8ff", "Sinal"),
    "industria": ("engrenagem", "#9aa6c4", "Engrenagem"), "fabrica": ("engrenagem", "#9aa6c4", "Engrenagem"), "maquina": ("engrenagem", "#9aa6c4", "Engrenagem"),
    "comida": ("cesta", "#c98a3a", "Cesta"), "aliment": ("cesta", "#c98a3a", "Cesta"), "mercado": ("cesta", "#c98a3a", "Cesta"), "supermercado": ("cesta", "#c98a3a", "Cesta"),
    "pessoa": ("pessoa", "#4a78d8", "Pessoa"), "popula": ("pessoa", "#4a78d8", "Pessoa"), "gente": ("pessoa", "#4a78d8", "Pessoa"), "humano": ("pessoa", "#4a78d8", "Pessoa"), "famil": ("pessoa", "#4a78d8", "Pessoa"),
}
CHAVES_CENARIO = {  # palavra -> tipo de cenario procedural
    "cidade": "cidade", "mundo": "cidade", "pais": "cidade", "rua": "cidade", "urban": "cidade", "predio": "cidade", "apag": "cidade", "energia": "cidade",
    "casa": "interior", "sala": "interior", "quarto": "interior", "hospital": "interior", "escritorio": "interior", "cozinha": "interior", "loja": "interior",
    "floresta": "natureza", "campo": "natureza", "natureza": "natureza", "animal": "natureza", "mar": "natureza", "oceano": "natureza", "montanha": "natureza", "savana": "natureza",
    "guerra": "guerra", "batalha": "guerra", "conflito": "guerra", "combate": "guerra", "militar": "guerra", "invasao": "guerra", "bombard": "guerra",
    "espaco": "espaco", "planeta": "espaco", "estrela": "espaco", "galaxia": "espaco", "universo": "espaco",
}


def svg_icone(nome_icone, cor):
    return ICONES[nome_icone](cor)


# ------------------------------------------------------------------ cenarios procedurais, viewBox 1920x1080
def svg_cenario(tipo, clima="noite", seed="x"):
    ct, cb, luz, acesas, _, _ = CLIMAS.get(clima, CLIMAS["noite"])
    if tipo == "guerra":
        ct, cb = "#0b0710", "#7a2c1c" if clima != "apagado" else "#2a1612"
    r = _rng(f"{tipo}{clima}{seed}")
    W, H = 1920, 1080
    defs = _grad("ceu", ct, cb) + _grad("chao", "#2a2f44", "#0b0d16")
    g = [f'<g id="ceu"><rect width="{W}" height="{H}" fill="url(#ceu)"/>']
    if clima in ("noite", "apagado", "alerta", "entardecer"):
        g += [f'<circle cx="{r.randint(0, W)}" cy="{r.randint(0, 520)}" r="{r.choice((1.5, 2, 2.5))}" fill="#ffffff" opacity="{r.uniform(.3, .9):.2f}"/>' for _ in range(70)]
        g.append(f'<circle cx="{r.randint(1300, 1750)}" cy="{r.randint(110, 230)}" r="62" fill="#f2f0e0" opacity="0.92"/>' + _glow(1500, 170, 90, "#cfd8ff", 0.10, 3))
    elif clima == "dia":
        g.append(_glow(1500, 170, 70, "#fff3b0", 0.35, 4) + '<circle cx="1500" cy="170" r="62" fill="#fff6c0"/>')
    g.append("</g>")
    if tipo == "cidade":
        for nome, base, alt, larg, tom in (("predios_fundo", 760, (160, 360), (70, 120), "#141a36"), ("predios_meio", 860, (240, 520), (90, 150), "#0f1428")):
            g.append(f'<g id="{nome}">')
            x = -20
            while x < W:
                w = r.randint(*larg)
                h = r.randint(*alt)
                g.append(f'<rect x="{x}" y="{base - h}" width="{w}" height="{h + 400}" fill="{tom}"/>')
                for yy in range(base - h + 22, base - 10, 38):
                    for xx in range(x + 12, x + w - 18, 26):
                        on = r.random() < acesas
                        g.append(f'<rect x="{xx}" y="{yy}" width="12" height="20" fill="{luz if on else "#1a2038"}" opacity="{0.95 if on else 0.55}"/>')
                x += w + r.randint(0, 10)
            g.append("</g>")
        g.append(f'<g id="rua"><rect y="900" width="{W}" height="180" fill="url(#chao)"/><rect y="990" width="{W}" height="8" fill="#e8c14a" opacity="0.35"/></g>')
    elif tipo == "interior":
        g.append(f'<g id="parede"><rect width="{W}" height="760" fill="{cb}" opacity="0.9"/><rect x="1180" y="150" width="420" height="360" rx="10" fill="{ct}" stroke="#0a0c14" stroke-width="14"/>'
                 f'<rect x="1384" y="150" width="12" height="360" fill="#0a0c14"/><rect x="1180" y="324" width="420" height="12" fill="#0a0c14"/></g>'
                 f'<g id="piso"><rect y="760" width="{W}" height="320" fill="url(#chao)"/><rect y="756" width="{W}" height="10" fill="#000" opacity="0.4"/></g>' + _glow(1390, 330, 260, luz, 0.10, 3))
    elif tipo == "natureza":
        for nome, base, tom, amp in (("colinas_fundo", 700, "#2c2f5e", 110), ("colinas_meio", 800, "#1d3a3a", 90)):
            pts = f"M0 {H} L0 {base} " + " ".join(f"L{x} {base - r.randint(0, amp)}" for x in range(120, W + 120, 120)) + f" L{W} {H} Z"
            g.append(f'<g id="{nome}"><path d="{pts}" fill="{tom}"/></g>')
        g.append(f'<g id="chao"><rect y="900" width="{W}" height="180" fill="#10241c"/></g>')
    elif tipo == "guerra":
        g[0] = f'<g id="ceu"><rect width="{W}" height="{H}" fill="url(#ceu)"/>'
        g.append(f'<g id="fumaca">' + "".join(f'<ellipse cx="{r.randint(0, W)}" cy="{r.randint(80, 520)}" rx="{r.randint(260, 560)}" ry="{r.randint(50, 120)}" fill="#1b1a22" opacity="{r.uniform(.25, .55):.2f}"/>' for _ in range(9)) + '</g>')
        g.append('<g id="horizonte">' + _glow(960, 760, 460, "#ff7a2e", 0.16, 4) + "".join(
            f'<polygon points="{x},780 {x},{780 - h} {x + w * 0.35:.0f},{780 - h - r.randint(10, 60)} {x + w * 0.6:.0f},{780 - h + r.randint(0, 40)} {x + w},{780 - h * 0.6:.0f} {x + w},780" fill="#0e0c14"/>'
            for x, w, h in ((i * 150 - 20, r.randint(90, 160), r.randint(90, 330)) for i in range(15))) + '</g>')
        g.append(f'<g id="chao"><rect y="780" width="{W}" height="300" fill="url(#chao)"/>' + "".join(
            f'<ellipse cx="{r.randint(0, W)}" cy="{r.randint(840, 1040)}" rx="{r.randint(60, 150)}" ry="{r.randint(10, 26)}" fill="#07060a" opacity="0.7"/>' for _ in range(7)) + '</g>')
    elif tipo == "espaco":
        g.append(f'<g id="planeta"><circle cx="{r.randint(300, 1500)}" cy="{r.randint(500, 800)}" r="{r.randint(180, 320)}" fill="#3b4a8a"/>'
                 f'<circle cx="{r.randint(300, 1500)}" cy="{r.randint(500, 800)}" r="120" fill="#fff" opacity="0.05"/></g>')
    else:
        g.append(f'<g id="forma1"><circle cx="{r.randint(300, 1600)}" cy="{r.randint(300, 800)}" r="{r.randint(180, 340)}" fill="{luz}" opacity="0.07"/></g>')
    return _svg((W, H), "".join(g), defs)


# ------------------------------------------------------------------ animacoes prontas (JSON) para qualquer SVG com partes
def _faixas(partes, prop, dur, amp, fase=False, base=0.0):
    f = {}
    for i, pid in enumerate(partes):
        s = -1 if (fase and i % 2) else 1
        f[pid] = {prop: [[0, base], [round(dur / 2, 3), base + s * amp], [dur, base]]}
    return f


def animacoes_padrao(partes):
    """partes: ids das partes do recurso. Se existir 'brilho', luzes/pulsos agem so nele."""
    ids = [p for p in partes if p]
    luz = [p for p in ids if p in ("brilho", "luz", "glow")] or ids
    corpo = [p for p in ids if p not in ("brilho", "luz", "glow")] or ids
    return {
        "parado": {"dur": 4.0, "loop": True, "faixas": _faixas(corpo[:12], "sy", 4.0, 0.012, base=1.0)},
        "balancar": {"dur": 1.8, "loop": True, "faixas": _faixas(corpo[:12], "rot", 1.8, 4.0, fase=True)},
        "pulsar": {"dur": 1.2, "loop": True, "faixas": {pid: {"sx": [[0, 1], [0.6, 1.07], [1.2, 1]], "sy": [[0, 1], [0.6, 1.07], [1.2, 1]]} for pid in corpo[:12]}},
        "piscar": {"dur": 1.0, "loop": True, "faixas": {pid: {"op": [[0, 1], [0.35, 1], [0.5, 0.2], [0.65, 1], [1.0, 1]]} for pid in luz[:12]}},
        "flutuar": {"dur": 3.0, "loop": True, "faixas": _faixas(corpo[:12], "ty", 3.0, -12.0)},
        "tremer": {"dur": 0.32, "loop": True, "faixas": {pid: {"tx": [[0, 0], [0.08, 3], [0.16, -3], [0.24, 3], [0.32, 0]]} for pid in corpo[:12]}},
    }


# ------------------------------------------------------------------ criacao + registro
def _extrair_svg(txt):
    m = re.search(r"<svg\b.*?</svg>", txt or "", flags=re.S | re.I)
    return m.group(0) if m else None


def _sanear(rec):
    """o validador aceita gradiente so em 'fill'; contorno com gradiente vira a 1a cor do gradiente."""
    def cor_unica(g):
        try:
            return g["g"][0][1]
        except Exception:  # noqa
            return "#888888"

    def forma(f):
        if isinstance(f, dict) and isinstance(f.get("stroke"), dict):
            f["stroke"] = cor_unica(f["stroke"])
    for parte in list(rec.get("partes", [])) + list(rec.get("camadas", [])):
        for f in parte.get("formas", []):
            forma(f)
    return rec


def _sem_fundo(rec):
    """IA costuma desenhar um retangulo de fundo cobrindo o viewBox; em objeto/personagem isso vira um 'cartao' opaco."""
    x0, y0, x1, y1 = rec["caixa"]
    area = max(1.0, (x1 - x0) * (y1 - y0))

    def cobre(f):
        t = f.get("t")
        if t == "rect":
            return f["w"] * f["h"] >= 0.85 * area and not f.get("r", 0) > 0.2 * min(f["w"], f["h"])
        if t == "path":
            nums = [float(n) for n in re.findall(r"-?\d+\.?\d*", f.get("d", ""))]
            if 6 <= len(nums) <= 12:
                xs, ys = nums[0::2], nums[1::2]
                return (max(xs) - min(xs)) * (max(ys) - min(ys)) >= 0.85 * area
        return False
    for parte in rec.get("partes", []):
        parte["formas"] = [f for f in parte.get("formas", []) if not cobre(f)]
    rec["partes"] = [pt for pt in rec.get("partes", []) if pt.get("formas")]
    return rec


def _ids_do_svg(svg, tipo):
    rec, _ = importar_svg(svg, "tmp", tipo, None)
    return {pt["id"] for pt in rec.get("partes", [])}


def _podar_sidecar(svg, tipo, side):
    """remove do JSON da IA tudo que cita partes que nao existem (em vez de descartar o JSON inteiro)"""
    if not isinstance(side, dict):
        return None
    ids = _ids_do_svg(svg, tipo)
    out = dict(side)
    if isinstance(out.get("partes"), dict):
        out["partes"] = {k: v for k, v in out["partes"].items() if k in ids}
    if isinstance(out.get("pose_base"), dict):
        out["pose_base"] = {k: v for k, v in out["pose_base"].items() if k in ids}
    anims = {}
    for nome, a in (out.get("animacoes") or {}).items():
        if not isinstance(a, dict) or not isinstance(a.get("faixas"), dict):
            continue
        fx = {k: v for k, v in a["faixas"].items() if k in ids}
        if fx:
            anims[nome] = dict(a, faixas=fx)
    out["animacoes"] = anims
    return out


def _recurso_de_svg(svg_txt, spec, animar=True, sidecar=None):
    rid, tipo = spec["id"], spec["tipo"]
    rec, avisos = importar_svg(svg_txt, rid, tipo, sidecar or spec.get("sidecar"))
    rec["nome"] = spec.get("nome") or rid
    rec["tags"] = list(dict.fromkeys(spec.get("tags") or [rid]))
    rec.setdefault("frente", "direita")
    _sanear(rec)
    if tipo != "cenario":
        _sem_fundo(rec)
    if tipo == "cenario":      # cenario = camadas com parallax (k cresce do fundo para a frente)
        pts = [x for x in rec.get("partes", []) if x.get("formas")]
        n = max(1, len(pts) - 1)
        rec["camadas"] = [{"id": x["id"], "k": round(0.05 + 0.65 * i / n, 3), "formas": x["formas"]} for i, x in enumerate(pts)]
        rec.pop("partes", None)
        rec.pop("animacoes", None)
    else:
        x0, y0, x1, y1 = rec["caixa"]
        rec.setdefault("base", [(x0 + x1) / 2, y1])
        if "sombra" not in rec and tipo == "objeto":
            rec["sombra"] = {"rx": (x1 - x0) * 0.32, "ry": 10, "y": y1, "x": (x0 + x1) / 2, "a": 0.4}
        if tipo == "objeto":
            com_pivo = {k for k, v in ((sidecar or spec.get("sidecar") or {}).get("partes") or {}).items() if isinstance(v, dict) and "pivo" in v}
            for pt in rec.get("partes", []):      # objeto rigido: partes sem pivo proprio giram/escalam em torno da base
                if pt["id"] not in com_pivo:
                    pt["pivo"] = [(x0 + x1) / 2, y1]
    if animar and tipo != "cenario":
        padrao = animacoes_padrao([pt["id"] for pt in rec.get("partes", [])])
        mapa = ANIMS_PERSONAGEM(rec) if tipo == "personagem" else {}
        rec["animacoes"] = {**padrao, **mapa, **(rec.get("animacoes") or {})}
    rec["origem"] = spec.get("origem", "ia")
    return rec, avisos


def ANIMS_PERSONAGEM(rec):
    """se o personagem tem partes com nomes de membros, gera caminhar/correr por JSON"""
    ids = {p["id"] for p in rec.get("partes", [])}
    pernas = [i for i in ids if i.startswith("perna")]
    bracos = [i for i in ids if i.startswith("braco")]
    if not pernas:
        return {}
    f = {}
    for k, i in enumerate(sorted(pernas)):
        f[i] = {"rot": [[0, -26 if k % 2 == 0 else 26], [0.4, 26 if k % 2 == 0 else -26], [0.8, -26 if k % 2 == 0 else 26]]}
    for k, i in enumerate(sorted(bracos)):
        f[i] = {"rot": [[0, 22 if k % 2 == 0 else -22], [0.4, -22 if k % 2 == 0 else 22], [0.8, 22 if k % 2 == 0 else -22]]}
    for i in ("tronco", "cabeca"):
        if i in ids:
            f[i] = {"ty": [[0, 0], [0.2, -5], [0.4, 0], [0.6, -5], [0.8, 0]]}
    return {"caminhar": {"dur": 0.8, "loop": True, "faixas": f}}


def _quadro_de_prova(rec, tipo):
    """registra num diretorio temporario e desenha 1 quadro: garante que o recurso renderiza."""
    from estudio.estilos.cenas2d import Estilo
    from estudio.nucleo import Tela
    with tempfile.TemporaryDirectory() as tmp:
        b = Biblioteca(tmp, aprovacao="auto")
        r = b.registrar(dict(rec))
        if tipo == "cenario":
            cena = {"modelo": "generica", "duracao": 2.0, "cenario": {"ref": r.id}, "elementos": []}
        else:
            cena = {"modelo": "generica", "duracao": 2.0, "elementos": [
                {"id": r.id, "ref": r.id, "altura": {"16x9": 0.5, "9x16": 0.3}, "pos": {"16x9": [0.5, 0.8], "9x16": [0.5, 0.7]}}]}
        est, tela = Estilo(320, 180, "alerta_noturno", b), Tela(320, 180, 1)
        for t in (0.0, 0.7):
            est.quadro(tela, t, cena, {})
        return list(b.problemas)


def _prompt_svg(spec):
    tipo = spec["tipo"]
    if tipo == "cenario":
        forma = ('viewBox="0 0 1920 1080". Camadas do fundo para a frente, cada uma um <g id="..."> filho direto da raiz '
                 "(ex.: ceu, astros, horizonte, predios_fundo, predios_meio, elementos_do_lugar, chao). Preencha toda a tela com atmosfera e PROFUNDIDADE "
                 "(neblina translucida entre camadas, luzes, janelas acesas ou apagadas, objetos do lugar). Sem personagens. "
                 "Deixe o terco inferior mais escuro/limpo (a legenda fica ali).")
        extra = f"\nClima: {spec.get('clima', 'noite')}."
        sidecar = ""
    elif tipo == "personagem":
        forma = ('viewBox="0 0 300 500", corpo inteiro em pe, olhando para a DIREITA, pes em y=490. Cada parte e um <g id="..."> direto na raiz, '
                 "com estes ids: cabeca, tronco, braco_e, braco_d, perna_e, perna_d (e, se houver, arma, mochila, capa). "
                 "Detalhe roupas, equipamentos, rosto, sombras e luz de contorno.")
        extra = ""
        sidecar = ('\nDEPOIS do </svg>, em uma segunda linha, escreva um JSON (sem cercas) com pivos e animacoes: '
                   '{"partes":{"perna_e":{"pivo":[x,y do quadril]},"braco_e":{"pivo":[x,y do ombro]},"cabeca":{"pivo":[x,y do pescoco]}},'
                   '"animacoes":{"parado":{"dur":4,"loop":true,"faixas":{"tronco":{"sy":[[0,1],[2,1.012],[4,1]]}}}}} . '
                   "Propriedades de faixa: rot (graus), tx, ty, sx, sy, op; cada keyframe e [tempo, valor]. Crie animacoes uteis ao personagem "
                   "(ex.: parado, caminhar, apontar, assustado) usando SOMENTE ids de partes existentes.")
    else:
        forma = ('viewBox com proporcao adequada ao objeto (ex.: 0 0 400 300), objeto isolado, centralizado, base apoiada na borda inferior. '
                 'Cada componente que deva se mover e um <g id="..."> direto na raiz (ex.: porta, canhao, helice, ponteiro, chama, tela). '
                 'Se emitir luz, inclua <g id="brilho"> com circulos concentricos translucidos.')
        extra = ""
        sidecar = ('\nDEPOIS do </svg>, em uma segunda linha, escreva um JSON (sem cercas) com pivos e animacoes especificas do objeto: '
                   '{"partes":{"porta":{"pivo":[x,y da dobradica]}},"animacoes":{"abrir":{"dur":1.2,"loop":false,"faixas":{"porta":{"sx":[[0,1],[1.2,0.15,"out_cubic"]]}}}}} . '
                   "Propriedades de faixa: rot (graus), tx, ty, sx, sy, op; cada keyframe e [tempo, valor]. Use SOMENTE ids de partes existentes; "
                   "se nada tiver movimento proprio, omita o JSON.")
    return ("Voce e um ilustrador vetorial senior de motion graphics (estilo infografico cinematografico, noturno, com luz de contorno). "
            "Escreva UM arquivo SVG, somente o codigo, sem explicacao nem cercas de markdown.\n"
            f"DESENHE: {spec.get('nome', spec['id'])}. {spec.get('descricao', '')}{extra}\n"
            f"FORMATO: {forma}\n"
            "NIVEL DE DETALHE (obrigatorio): objeto RICO e reconhecivel, nao um icone: 40 a 250 formas; volumes com gradientes lineares (claro->escuro), "
            "reflexos e brilhos como formas translucidas, sombras proprias, partes pequenas que contam a historia (pecas, painéis, parafusos, "
            "janelas, luzes, marcas, rachaduras, camuflagem, conforme o assunto). Paleta coesa: tons escuros azulados/neutros com UM acento de cor "
            "forte (vermelho, ambar ou ciano) e luzes quentes/frias.\n"
            "SEM RETANGULO/CARTAO DE FUNDO (o objeto fica solto sobre o cenario, fundo transparente), exceto se for cenario. "
            "O desenho deve ser um objeto CONCRETO e reconhecivel no mundo real em 1 segundo (nao abstrato nem decorativo).\n"
            "REGRAS TECNICAS: apenas path, rect, circle, ellipse, line, polyline, polygon, g, defs, linearGradient (gradiente SOMENTE em fill; "
            "contornos stroke sempre em cor solida #hex). PROIBIDO: text, image, use, filter, mask, clipPath, pattern, style, script, animate, "
            "radialGradient, href. Cores em #hex. Coordenadas dentro do viewBox." + sidecar)


def _separar_resposta(txt):
    """(svg, sidecar_dict|None) a partir da resposta da IA"""
    svg = _extrair_svg(txt)
    side = None
    if svg:
        resto = txt[txt.lower().rfind("</svg>") + 6:]
        m = re.search(r"\{.*\}", resto, flags=re.S)
        if m:
            try:
                side = json.loads(m.group(0))
                if not isinstance(side, dict):
                    side = None
            except Exception:  # noqa
                side = None
    return svg, side


def _gerar_por_ia(spec, llm, log, tentativas=3):
    erros = ""
    for k in range(tentativas):
        try:
            txt = llm(_prompt_svg(spec) + (f"\nA tentativa anterior falhou: {erros}. Corrija e envie novamente." if erros else ""), False)
            svg, side = _separar_resposta(txt)
            if not svg:
                raise RecursoInvalido("a resposta nao trouxe um <svg>")
            if side:
                try:
                    side = _podar_sidecar(svg, spec["tipo"], side)
                except Exception:  # noqa
                    side = None
            rec = None
            for sc in ([side, None] if side else [None]):      # sidecar invalido nao derruba o desenho
                try:
                    rec, _ = _recurso_de_svg(svg, spec, sidecar=sc)
                    n_formas = sum(len(pt.get("formas", [])) for pt in (rec.get("partes", []) + rec.get("camadas", [])))
                    if n_formas < 15:
                        raise RecursoInvalido(f"desenho simples demais ({n_formas} formas; faca 40 ou mais, com detalhes)")
                    validar_recurso(rec)
                    _quadro_de_prova(rec, spec["tipo"])
                    break
                except Exception as e:  # noqa
                    if sc is None:
                        raise
                    log(f"      animacoes/pivos da IA descartados em '{spec['id']}': {str(e)[:120]}")
                    rec = None
            return rec
        except Exception as e:  # noqa
            erros = str(e)[:240]
            log(f"      tentativa {k + 1} de '{spec['id']}' falhou: {erros}")
    return None


def _procedural(spec):
    nomes = palavras_chave(" ".join([spec["id"], spec.get("nome", ""), " ".join(spec.get("tags") or []), spec.get("descricao", "")]))
    spec = dict(spec, origem="procedural")
    if spec["tipo"] != "cenario":
        chave = next((A.CHAVES_ATIVO[k] for w in nomes for k in A.CHAVES_ATIVO if w == k or (len(k) >= 4 and w.startswith(k))), None)
        if chave:
            svg, side, tipo, nome, tags = A.ATIVOS[chave]()
            spec = dict(spec, tipo=tipo, nome=spec.get("nome") or nome, tags=list(dict.fromkeys(list(spec.get("tags") or []) + tags)))
            rec, _ = _recurso_de_svg(svg, spec, sidecar=side)
            return rec
    if spec["tipo"] == "cenario":
        tipo = next((CHAVES_CENARIO[k] for w in nomes for k in CHAVES_CENARIO if w == k or (len(k) >= 4 and w.startswith(k))), "cidade")
        svg = svg_cenario(tipo, spec.get("clima") or "noite", spec["id"])
    else:
        ic = next((CHAVES_ICONE[k] for w in nomes for k in CHAVES_ICONE if w == k or (len(k) >= 4 and w.startswith(k))), None)
        ic = ic or (("pessoa", "#4a78d8", "Pessoa") if spec["tipo"] == "personagem" else ("estrela", "#e8c14a", "Simbolo"))
        svg = svg_icone(ic[0], ic[1])
    rec, _ = _recurso_de_svg(svg, spec)
    return rec


def palavras_chave(txt):
    t = unicodedata.normalize("NFKD", str(txt or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return [w for w in re.findall(r"[a-z0-9]+", t) if len(w) >= 3]


def criar_recurso(spec, bib, llm=None, log=print):
    """cria (se ainda nao existir) e devolve o id aprovado na biblioteca. Nunca falha: cai no gerador procedural."""
    spec = dict(spec)
    spec["id"] = slug(spec.get("id") or spec.get("nome"))
    spec.setdefault("tipo", "objeto")
    if spec["tipo"] not in ("personagem", "objeto", "cenario"):
        spec["tipo"] = "objeto"
    spec["tags"] = list(dict.fromkeys(list(spec.get("tags") or []) + palavras_chave(spec.get("nome", ""))[:2]))
    e = bib.idx["recursos"].get(spec["id"])
    if e and e.get("status") not in ("rejeitado",):
        # reserva procedural + IA disponivel: tenta substituir por um desenho de IA (nova versao do mesmo id)
        if not (llm and e.get("origem") == "procedural"):
            if e["status"] != "aprovado":
                bib.aprovar(spec["id"])
            return spec["id"]
    rec = _gerar_por_ia(spec, llm, log) if llm else None
    if rec is None and e and e.get("status") not in ("rejeitado",):
        return spec["id"]
    origem = "ia"
    if rec is None:
        rec, origem = _procedural(spec), "procedural"
    res = bib.registrar(rec)
    if getattr(res, "status", "") != "aprovado":
        bib.aprovar(res.id)
    bib.idx["recursos"][res.id]["origem"] = origem
    bib._salvar_index()
    log(f"   recurso novo: {res.id} ({spec['tipo']}, {origem})")
    return res.id


def garantir_kit(bib, log=print):
    """instala (idempotente) o kit didatico: objetos cujo estado muda (termometro sobe, barras crescem, relogio passa...).
    Entram como 'curado': a IA os enxerga e pode reutiliza-los."""
    novos = []
    for rid, fn in A.KIT.items():
        e = bib.idx["recursos"].get(rid)
        if e and e.get("origem") == "curado":
            continue
        svg, side, tipo, nome, tags = fn()
        spec = {"id": rid, "tipo": tipo, "nome": nome, "tags": tags, "origem": "curado"}
        rec, _ = _recurso_de_svg(svg, spec, sidecar=side)
        res = bib.registrar(rec)
        if getattr(res, "status", "") != "aprovado":
            bib.aprovar(res.id)
        bib.idx["recursos"][res.id]["origem"] = "curado"
        novos.append(res.id)
    if novos:
        bib._salvar_index()
        log(f"   kit didatico instalado: {', '.join(novos)}")
    return novos
