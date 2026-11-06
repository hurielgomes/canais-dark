"""
nucleo.py - pecas comuns a todos os estilos: tela com suavizacao, texto, easing, legenda palavra a palavra e render.

Regra de ouro: cada estilo desenha o quadro como funcao do tempo t (sem guardar estado entre quadros).
O fundo estatico e desenhado uma vez e copiado a cada quadro (rapido).
"""
import math
import re
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

AQUI = Path(__file__).resolve().parent
FONTES = {
    "cond": AQUI / "fonts" / "DejaVuSansCondensed-Bold.ttf",
    "bold": AQUI / "fonts" / "DejaVuSans-Bold.ttf",
    "sans": AQUI / "fonts" / "DejaVuSans.ttf",
    "mono": AQUI / "fonts" / "DejaVuSansMono-Bold.ttf",
}
_cache_fontes = {}


def fonte(nome, tam):
    k = (nome, int(tam))
    if k not in _cache_fontes:
        _cache_fontes[k] = ImageFont.truetype(str(FONTES[nome]), int(tam))
    return _cache_fontes[k]


# ------------------------------------------------------------------ matematica
def clamp(v, a=0.0, b=1.0):
    return max(a, min(b, v))


def lerp(a, b, u):
    return a + (b - a) * u


def ease_out(u):
    u = clamp(u)
    return 1 - (1 - u) ** 3


def ease_in_out(u):
    u = clamp(u)
    return u * u * (3 - 2 * u)


def overshoot(u, s=1.7):
    u = clamp(u)
    return 1 + (s + 1) * (u - 1) ** 3 + s * (u - 1) ** 2


def janela(t, ini, dur):
    """progresso 0..1 de uma animacao que comeca em 'ini' e dura 'dur' segundos"""
    return clamp((t - ini) / max(1e-6, dur))


def hex2(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def com_alpha(cor, a):
    return (cor[0], cor[1], cor[2], int(255 * clamp(a)))


# ------------------------------------------------------------------------ tela
class Tela:
    def __init__(self, w, h, S=2, base=None, fundo=(0, 0, 0)):
        self.w, self.h, self.S = w, h, S
        self.img = base.copy() if base is not None else Image.new("RGB", (w * S, h * S), fundo)
        self.d = ImageDraw.Draw(self.img, "RGBA")

    def P(self, x, y):
        return (x * self.S, y * self.S)

    def pts(self, lst):
        return [(x * self.S, y * self.S) for x, y in lst]

    def poly(self, lst, fill=None, outline=None, w=0):
        P = self.pts(lst)
        if fill is not None:
            self.d.polygon(P, fill=fill)
        if outline is not None and w:
            self.d.line(P + [P[0]], fill=outline, width=max(1, int(w * self.S)), joint="curve")

    def linha(self, lst, cor, w=3, cap=True):
        P = self.pts(lst)
        self.d.line(P, fill=cor, width=max(1, int(w * self.S)), joint="curve")
        if cap:
            r = w * self.S / 2
            for x, y in (P[0], P[-1]):
                self.d.ellipse([x - r, y - r, x + r, y + r], fill=cor)

    def rect(self, x0, y0, x1, y1, fill=None, outline=None, w=0, r=0):
        a, b = self.P(x0, y0), self.P(x1, y1)
        if r:
            self.d.rounded_rectangle([a, b], radius=r * self.S, fill=fill, outline=outline, width=int(w * self.S))
        else:
            self.d.rectangle([a, b], fill=fill, outline=outline, width=int(w * self.S))

    def elipse(self, cx, cy, rx, ry=None, fill=None, outline=None, w=0):
        ry = rx if ry is None else ry
        self.d.ellipse([self.P(cx - rx, cy - ry), self.P(cx + rx, cy + ry)], fill=fill, outline=outline, width=int(w * self.S))

    def texto(self, x, y, s, nome, tam, cor, anchor="la", stroke=0, stroke_fill=None):
        self.d.text(self.P(x, y), s, font=fonte(nome, tam * self.S), fill=cor, anchor=anchor,
                    stroke_width=int(stroke * self.S), stroke_fill=stroke_fill)

    def largura_texto(self, s, nome, tam):
        return self.d.textlength(s, font=fonte(nome, tam * self.S)) / self.S

    def texto_revelado(self, x, y, s, nome, tam, cor, prog, anchor="lm"):
        """mostra o texto aos poucos, da esquerda para a direita (efeito de 'varredura')"""
        if prog <= 0:
            return
        f = fonte(nome, tam * self.S)
        bb = self.d.textbbox((0, 0), s, font=f, anchor=anchor)
        w, h = bb[2] - bb[0] + 8, bb[3] - bb[1] + 8
        cam = Image.new("RGBA", (int(w), int(h)), (0, 0, 0, 0))
        ImageDraw.Draw(cam).text((-bb[0] + 4, -bb[1] + 4), s, font=f, fill=cor, anchor=anchor)
        corte = max(1, int(w * clamp(prog)))
        cam = cam.crop((0, 0, corte, int(h)))
        px, py = self.P(x, y)
        self.img.paste(cam, (int(px + bb[0] - 4), int(py + bb[1] - 4)), cam)

    def finalizar(self):
        return self.img.resize((self.w, self.h), Image.LANCZOS)


def degrade_vertical(tela, c0, c1):
    for y in range(tela.h * tela.S):
        tela.d.line([(0, y), (tela.w * tela.S, y)], fill=mix(c0, c1, y / (tela.h * tela.S)))


# --------------------------------------------------------------- numero animado
def contar(texto, p):
    """Anima o primeiro numero do texto de 0 ate o valor final: '+2,31%' em p=0.5 -> '+1,16%'"""
    m = re.search(r"\d+(?:[.,]\d+)?", texto)
    if not m:
        return texto
    bruto = m.group(0)
    sep = "," if "," in bruto else "."
    casas = len(bruto.split(sep)[1]) if sep in bruto else 0
    valor = float(bruto.replace(",", "."))
    atual = valor * clamp(p)
    novo = f"{atual:.{casas}f}".replace(".", sep) if casas else f"{int(round(atual))}"
    return texto[:m.start()] + novo + texto[m.end():]


# ---------------------------------------------------------- legenda palavra a palavra
def legenda_palavras(tela, t, trechos, y, tam=36, largura_max=1000, cor_destaque=(255, 214, 64), fundo=(0, 0, 0, 150), nome="bold"):
    atual = None
    for tr in trechos:
        if tr["ini"] <= t < tr["fim"]:
            atual = tr
            break
    if not atual:
        return
    palavras = atual["texto"].upper().split()
    pesos = [len(p) + 2 for p in palavras]
    total = float(sum(pesos))
    u = (t - atual["ini"]) / max(1e-6, atual["fim"] - atual["ini"])
    acum, ativa = 0.0, len(palavras) - 1
    for i, pw in enumerate(pesos):
        acum += pw / total
        if u < acum:
            ativa = i
            break
    esp = tela.largura_texto(" ", nome, tam)
    linhas, cur, larg = [], [], 0.0
    for i, p in enumerate(palavras):
        w = tela.largura_texto(p, nome, tam)
        if cur and larg + esp + w > largura_max:
            linhas.append(cur)
            cur, larg = [], 0.0
        cur.append((i, p, w))
        larg += (esp if len(cur) > 1 else 0) + w
    if cur:
        linhas.append(cur)
    alt = tam * 1.3
    topo = y - len(linhas) * alt / 2
    maior = max(sum(w for _, _, w in l) + esp * (len(l) - 1) for l in linhas)
    cx = tela.w / 2
    tela.rect(cx - maior / 2 - 26, topo - 8, cx + maior / 2 + 26, topo + len(linhas) * alt + 4, fill=fundo, r=14)
    for li, l in enumerate(linhas):
        larg = sum(w for _, _, w in l) + esp * (len(l) - 1)
        x = cx - larg / 2
        yy = topo + li * alt + alt / 2
        for i, p, w in l:
            tela.texto(x, yy, p, nome, tam, cor_destaque if i == ativa else (255, 255, 255), anchor="lm")
            x += w + esp


# ------------------------------------------------------------------- renderizar
def renderizar(fn_quadro, saida, w, h, fps, duracao, S=2, fn_fundo=None, audio=None, mostrar=True, callback=None):
    if shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg nao encontrado. Instale o FFmpeg e abra um novo terminal.")
    base = None
    if fn_fundo is not None:
        tf = Tela(w, h, S)
        fn_fundo(tf)
        base = tf.img
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-"]
    if audio:
        cmd += ["-i", str(audio)]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p"]
    if audio:
        cmd += ["-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += ["-movflags", "+faststart", str(saida)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = int(round(duracao * fps))
    try:
        for i in range(n):
            t = i / fps
            tela = Tela(w, h, S, base=base)
            fn_quadro(tela, t)
            proc.stdin.write(tela.finalizar().tobytes())
            if callback is not None:
                callback(i, n)
            elif mostrar and i % (fps * 2) == 0:
                print(f"  quadro {i}/{n}", flush=True)
    finally:
        proc.stdin.close()
        proc.wait()
