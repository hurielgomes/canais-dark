"""
tween.py - curvas de movimento (easing) e animacoes elementares, todas FUNCOES PURAS DE t.

Uso tipico:
    p = tw(t, ini=0.8, dur=0.6, ease="out_back")      # 0..1 com a curva escolhida
    x = lerp(x0, x1, p)
"""
import math


def clamp(v, a=0.0, b=1.0):
    return a if v < a else b if v > b else v


def lerp(a, b, u):
    return a + (b - a) * u


# ---------------------------------------------------------------- curvas (u em 0..1)
def linear(u):
    return clamp(u)


def in_out(u):                      # smootherstep: partida e chegada bem suaves
    u = clamp(u)
    return u * u * u * (u * (u * 6 - 15) + 10)


def in_out_sine(u):
    return 0.5 - 0.5 * math.cos(math.pi * clamp(u))


def out_cubic(u):
    return 1 - (1 - clamp(u)) ** 3


def out_quart(u):
    return 1 - (1 - clamp(u)) ** 4


def in_cubic(u):
    return clamp(u) ** 3


def out_expo(u):
    u = clamp(u)
    return 1.0 if u >= 1 else 1 - 2 ** (-10 * u)


def out_back(u, s=1.70158):         # passa do alvo e volta (pop com "peso")
    u = clamp(u) - 1
    return 1 + (s + 1) * u ** 3 + s * u ** 2


def out_elastic(u):
    u = clamp(u)
    if u in (0.0, 1.0):
        return u
    return 2 ** (-10 * u) * math.sin((u * 10 - 0.75) * (2 * math.pi) / 3) + 1


def out_bounce(u):
    u = clamp(u)
    n, d = 7.5625, 2.75
    if u < 1 / d:
        return n * u * u
    if u < 2 / d:
        u -= 1.5 / d
        return n * u * u + 0.75
    if u < 2.5 / d:
        u -= 2.25 / d
        return n * u * u + 0.9375
    u -= 2.625 / d
    return n * u * u + 0.984375


EASES = {"linear": linear, "in_out": in_out, "in_out_sine": in_out_sine, "out_cubic": out_cubic,
         "out_quart": out_quart, "in_cubic": in_cubic, "out_expo": out_expo, "out_back": out_back,
         "out_elastic": out_elastic, "out_bounce": out_bounce}


def tw(t, ini, dur, ease="out_cubic"):
    """progresso 0..1 de uma animacao que comeca em `ini` e dura `dur`, com a curva `ease`"""
    u = clamp((t - ini) / max(1e-6, dur))
    return EASES[ease](u) if isinstance(ease, str) else ease(u)


def janela(t, ini, fim):
    """1 enquanto ini <= t < fim, com entrada/saida suaves de 0.15 s (para mostrar/ocultar elementos)"""
    return clamp((t - ini) / 0.15) * clamp((fim - t) / 0.15)


# ---------------------------------------------------------------- movimentos continuos
def respirar(t, amp=1.0, per=3.2, fase=0.0):
    return amp * math.sin(2 * math.pi * t / per + fase)


def pulso(t, per=1.0, fase=0.0):
    """0..1 em forma de batida (sobe rapido, desce devagar)"""
    u = ((t / per) + fase) % 1.0
    return math.exp(-5.0 * u)


def tremor(t, amp=1.0, freq=18.0, sem=0):
    """ruido suave deterministico (soma de senos incomensuraveis)"""
    return amp * (math.sin(t * freq + sem * 1.7) * 0.6 + math.sin(t * freq * 1.93 + sem * 3.1) * 0.4)


def falha_luz(t, ini, fim, semente=3):
    """cintilar de lampada entre ini e fim: devolve 0..1 (1 = acesa)."""
    if t < ini:
        return 1.0
    if t >= fim:
        return 0.0
    u = (t - ini) / (fim - ini)
    ruido = math.sin(t * 47.0 + semente) * math.sin(t * 23.0 + semente * 2.0)
    base = 1 - in_out(u)
    return clamp(base * (0.55 + 0.45 * (ruido > -0.2)) + 0.12 * ruido * (1 - u), 0.0, 1.0)


def contar(valor, p, casas=0):
    """texto do contador de 0 ate `valor` com progresso p"""
    v = valor * clamp(p)
    return f"{v:.{casas}f}".replace(".", ",") if casas else f"{int(round(v))}"
