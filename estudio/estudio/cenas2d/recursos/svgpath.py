"""
svgpath.py - interpreta o atributo `d` de caminhos SVG e converte em polilinhas (listas de pontos).

Comandos: M m L l H h V v C c S s Q q T t A a Z z (absolutos e relativos). Curvas sao "achatadas" (flatten) em
segmentos retos. Nada aqui executa codigo: e um scanner de texto com limites de tamanho.
Tambem: parse de `transform` (translate/scale/rotate/matrix/skewX/skewY) como matriz afim (a,b,c,d,e,f).
"""
import math

MAX_CMDS = 20000
MAX_PONTOS = 60000


class CaminhoInvalido(ValueError):
    pass


# --------------------------------------------------------------------------- matrizes afins (a,b,c,d,e,f)
IDENT = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def mmul(m, n):
    """m * n  (aplica n primeiro, depois m)"""
    return (m[0] * n[0] + m[2] * n[1], m[1] * n[0] + m[3] * n[1],
            m[0] * n[2] + m[2] * n[3], m[1] * n[2] + m[3] * n[3],
            m[0] * n[4] + m[2] * n[5] + m[4], m[1] * n[4] + m[3] * n[5] + m[5])


def mpt(m, x, y):
    return (m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5])


def translacao(tx, ty):
    return (1.0, 0.0, 0.0, 1.0, tx, ty)


def rotacao_graus(a, cx=0.0, cy=0.0):
    r = math.radians(a)
    c, s = math.cos(r), math.sin(r)
    return mmul(translacao(cx, cy), mmul((c, s, -s, c, 0.0, 0.0), translacao(-cx, -cy)))


def escala(sx, sy, cx=0.0, cy=0.0):
    return mmul(translacao(cx, cy), mmul((sx, 0.0, 0.0, sy, 0.0, 0.0), translacao(-cx, -cy)))


def parse_transform(txt):
    """'translate(10 20) rotate(30)' -> matriz. Funcoes desconhecidas sao rejeitadas."""
    import re
    m = IDENT
    if not txt:
        return m
    for nome, args in re.findall(r"([a-zA-Z]+)\s*\(([^)]*)\)", txt):
        try:
            v = [float(x) for x in re.split(r"[\s,]+", args.strip()) if x != ""]
        except ValueError:
            raise CaminhoInvalido(f"transform invalido: {txt[:60]}")
        if nome == "translate":
            n = translacao(v[0], v[1] if len(v) > 1 else 0.0)
        elif nome == "scale":
            n = escala(v[0], v[1] if len(v) > 1 else v[0])
        elif nome == "rotate":
            n = rotacao_graus(v[0], v[1] if len(v) > 2 else 0.0, v[2] if len(v) > 2 else 0.0)
        elif nome == "matrix" and len(v) == 6:
            n = tuple(v)
        elif nome == "skewX":
            n = (1.0, 0.0, math.tan(math.radians(v[0])), 1.0, 0.0, 0.0)
        elif nome == "skewY":
            n = (1.0, math.tan(math.radians(v[0])), 0.0, 1.0, 0.0, 0.0)
        else:
            raise CaminhoInvalido(f"transform nao suportado: {nome}")
        m = mmul(m, n)
    return m


# --------------------------------------------------------------------------- scanner
class _Scan:
    def __init__(self, s):
        self.s, self.i, self.n = s, 0, len(s)

    def ws(self):
        while self.i < self.n and self.s[self.i] in " \t\r\n,":
            self.i += 1

    def fim(self):
        self.ws()
        return self.i >= self.n

    def cmd(self):
        self.ws()
        if self.i < self.n and self.s[self.i].isalpha():
            c = self.s[self.i]
            self.i += 1
            return c
        return None

    def num(self):
        self.ws()
        i = self.i
        s = self.s
        if i < self.n and s[i] in "+-":
            i += 1
        dig = False
        while i < self.n and s[i].isdigit():
            i += 1
            dig = True
        if i < self.n and s[i] == ".":
            i += 1
            while i < self.n and s[i].isdigit():
                i += 1
                dig = True
        if not dig:
            raise CaminhoInvalido(f"numero esperado na posicao {self.i}")
        if i < self.n and s[i] in "eE":
            j = i + 1
            if j < self.n and s[j] in "+-":
                j += 1
            if j < self.n and s[j].isdigit():
                while j < self.n and s[j].isdigit():
                    j += 1
                i = j
        v = float(s[self.i:i])
        self.i = i
        if not math.isfinite(v) or abs(v) > 1e7:
            raise CaminhoInvalido("numero fora do intervalo")
        return v

    def flag(self):
        self.ws()
        if self.i < self.n and self.s[self.i] in "01":
            v = int(self.s[self.i])
            self.i += 1
            return v
        raise CaminhoInvalido("flag de arco esperada (0/1)")


def _bezier_n(p0, p1, p2, p3, n):
    pts = []
    for k in range(1, n + 1):
        t = k / n
        u = 1 - t
        pts.append((u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
                    u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1]))
    return pts


def _n_seg(*pts):
    comp = sum(math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) for i in range(len(pts) - 1))
    return max(6, min(30, int(comp / 5.0) + 4))


def _arco(p0, rx, ry, phi, fa, fs, p1):
    """arco elíptico SVG (parametrizacao por ponto final) -> pontos"""
    x0, y0 = p0
    x1, y1 = p1
    if (x0, y0) == (x1, y1):
        return []
    rx, ry = abs(rx), abs(ry)
    if rx < 1e-9 or ry < 1e-9:
        return [p1]
    ph = math.radians(phi)
    cp, sp = math.cos(ph), math.sin(ph)
    dx, dy = (x0 - x1) / 2, (y0 - y1) / 2
    xp, yp = cp * dx + sp * dy, -sp * dx + cp * dy
    lam = xp * xp / (rx * rx) + yp * yp / (ry * ry)
    if lam > 1:
        k = math.sqrt(lam)
        rx, ry = rx * k, ry * k
    num = rx * rx * ry * ry - rx * rx * yp * yp - ry * ry * xp * xp
    den = rx * rx * yp * yp + ry * ry * xp * xp
    co = math.sqrt(max(0.0, num / den)) * (-1 if fa == fs else 1)
    cxp, cyp = co * rx * yp / ry, -co * ry * xp / rx
    cx, cy = cp * cxp - sp * cyp + (x0 + x1) / 2, sp * cxp + cp * cyp + (y0 + y1) / 2

    def ang(ux, uy, vx, vy):
        a = math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
        return a

    t1 = ang(1, 0, (xp - cxp) / rx, (yp - cyp) / ry)
    dt = ang((xp - cxp) / rx, (yp - cyp) / ry, (-xp - cxp) / rx, (-yp - cyp) / ry)
    if not fs and dt > 0:
        dt -= 2 * math.pi
    elif fs and dt < 0:
        dt += 2 * math.pi
    n = max(8, min(48, int(abs(dt) / (math.pi / 16)) + 2))
    pts = []
    for k in range(1, n + 1):
        t = t1 + dt * k / n
        px, py = rx * math.cos(t), ry * math.sin(t)
        pts.append((cp * px - sp * py + cx, sp * px + cp * py + cy))
    return pts


def parse(d, matriz=IDENT):
    """d -> [(pontos[(x,y)...], fechado:boolean), ...]  (aplica `matriz` aos pontos)"""
    if len(d) > 400000:
        raise CaminhoInvalido("caminho grande demais")
    sc = _Scan(d)
    subs, cur = [], []
    x = y = sx = sy = 0.0
    ult_c = None   # ultimo ponto de controle (para S/T)
    ult_q = None
    cmd = None
    ncmd = 0
    total = 0

    def fecha(fechado):
        nonlocal cur
        if len(cur) >= 2:
            subs.append((cur, fechado))
        cur = []

    while not sc.fim():
        c = sc.cmd()
        if c is not None:
            cmd = c
            if c in "Zz":
                if cur:
                    cur.append((sx, sy))
                    fecha(True)
                x, y = sx, sy
                ult_c = ult_q = None
                continue
        elif cmd is None or cmd in "Zz":
            raise CaminhoInvalido("comando esperado")
        ncmd += 1
        antes = len(cur)
        if ncmd > MAX_CMDS:
            raise CaminhoInvalido("comandos demais no caminho")
        rel = cmd.islower()
        C = cmd.upper()
        ox, oy = (x, y) if rel else (0.0, 0.0)
        if C == "M":
            fecha(False)
            x, y = sc.num() + ox, sc.num() + oy
            sx, sy = x, y
            cur = [(x, y)]
            cmd = "l" if rel else "L"
            ult_c = ult_q = None
            continue
        if not cur:
            cur = [(x, y)]
        if C == "L":
            x, y = sc.num() + ox, sc.num() + oy
            cur.append((x, y)); ult_c = ult_q = None
        elif C == "H":
            x = sc.num() + (x if rel else 0.0)
            cur.append((x, y)); ult_c = ult_q = None
        elif C == "V":
            y = sc.num() + (y if rel else 0.0)
            cur.append((x, y)); ult_c = ult_q = None
        elif C == "C":
            p1 = (sc.num() + ox, sc.num() + oy)
            p2 = (sc.num() + ox, sc.num() + oy)
            p3 = (sc.num() + ox, sc.num() + oy)
            cur += _bezier_n((x, y), p1, p2, p3, _n_seg((x, y), p1, p2, p3))
            x, y = p3; ult_c, ult_q = p2, None
        elif C == "S":
            p1 = (2 * x - ult_c[0], 2 * y - ult_c[1]) if ult_c else (x, y)
            p2 = (sc.num() + ox, sc.num() + oy)
            p3 = (sc.num() + ox, sc.num() + oy)
            cur += _bezier_n((x, y), p1, p2, p3, _n_seg((x, y), p1, p2, p3))
            x, y = p3; ult_c, ult_q = p2, None
        elif C == "Q":
            q = (sc.num() + ox, sc.num() + oy)
            p3 = (sc.num() + ox, sc.num() + oy)
            p1 = (x + 2 / 3 * (q[0] - x), y + 2 / 3 * (q[1] - y))
            p2 = (p3[0] + 2 / 3 * (q[0] - p3[0]), p3[1] + 2 / 3 * (q[1] - p3[1]))
            cur += _bezier_n((x, y), p1, p2, p3, _n_seg((x, y), p1, p2, p3))
            x, y = p3; ult_q, ult_c = q, None
        elif C == "T":
            q = (2 * x - ult_q[0], 2 * y - ult_q[1]) if ult_q else (x, y)
            p3 = (sc.num() + ox, sc.num() + oy)
            p1 = (x + 2 / 3 * (q[0] - x), y + 2 / 3 * (q[1] - y))
            p2 = (p3[0] + 2 / 3 * (q[0] - p3[0]), p3[1] + 2 / 3 * (q[1] - p3[1]))
            cur += _bezier_n((x, y), p1, p2, p3, _n_seg((x, y), p1, p2, p3))
            x, y = p3; ult_q, ult_c = q, None
        elif C == "A":
            rx, ry, phi = sc.num(), sc.num(), sc.num()
            fa, fs = sc.flag(), sc.flag()
            p1 = (sc.num() + ox, sc.num() + oy)
            cur += _arco((x, y), rx, ry, phi, fa, fs, p1) or [p1]
            x, y = p1; ult_c = ult_q = None
        else:
            raise CaminhoInvalido(f"comando '{cmd}' nao suportado")
        total += max(1, len(cur) - antes)
        if total > MAX_PONTOS:
            raise CaminhoInvalido("pontos demais no caminho")
    fecha(False)
    if matriz != IDENT:
        subs = [([mpt(matriz, px, py) for px, py in pts], f) for pts, f in subs]
    return subs
