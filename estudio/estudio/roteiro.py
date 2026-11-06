"""roteiro.py - le um roteiro em JSON e renderiza o video no estilo escolhido."""
import json
from pathlib import Path

from .nucleo import Tela, renderizar
from .estilos import telejornal, whiteboard

ESTILOS = {"telejornal": telejornal.Estilo, "whiteboard": whiteboard.Estilo}
FORMATOS = {"16x9": (1920, 1080), "9x16": (1080, 1920)}


def carregar(caminho):
    return json.loads(Path(caminho).read_text(encoding="utf-8"))


def renderizar_roteiro(roteiro, saida, formato="16x9", fps=30, so_segundos=None, S=2, audio=None, callback=None):
    w, h = FORMATOS[formato]
    estilo = ESTILOS[roteiro["estilo"]](w, h)
    cenas = roteiro["cenas"]
    inicios, acum = [], 0.0
    for c in cenas:
        inicios.append(acum)
        acum += float(c["duracao"])
    total = acum if so_segundos is None else min(acum, so_segundos)
    canal = roteiro.get("canal", "SEU CANAL")

    def quadro(tela, t):
        i = max(k for k, ini in enumerate(inicios) if ini <= t + 1e-9)
        estilo.quadro(tela, t - inicios[i], cenas[i], canal)

    renderizar(quadro, saida, w, h, fps, total, S=S, fn_fundo=estilo.fundo, audio=audio, callback=callback)
    return total


def quadro_unico(roteiro, indice_cena, t, formato="16x9", S=2):
    """desenha um unico quadro (usado para a miniatura)"""
    from .nucleo import Tela
    w, h = FORMATOS[formato]
    estilo = ESTILOS[roteiro["estilo"]](w, h)
    tf = Tela(w, h, S)
    estilo.fundo(tf)
    tela = Tela(w, h, S, base=tf.img)
    estilo.quadro(tela, t, roteiro["cenas"][indice_cena], roteiro.get("canal", "SEU CANAL"))
    return tela.finalizar()
