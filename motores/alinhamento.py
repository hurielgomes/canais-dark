"""Alinha cenas a um audio unico usando os tempos de cada palavra."""
from __future__ import annotations
import re

def _palavras(t: str) -> list[str]:
    return re.findall(r"\w+", t.lower())

def tempos_palavras(audio: str) -> list[tuple[float, float]]:
    from faster_whisper import WhisperModel
    modelo = WhisperModel("small", device="cpu", compute_type="int8")
    segs, _ = modelo.transcribe(audio, language="pt", word_timestamps=True)
    return [(w.start, w.end) for s in segs for w in s.words]

def tempos_cenas(audio: str, cenas: list[dict], duracao_total: float) -> list[tuple[float, float]]:
    """Retorna (inicio, fim) em segundos de cada cena."""
    tempos = tempos_palavras(audio)
    contagens = [len(_palavras(c["narracao"])) for c in cenas]
    total_texto = sum(contagens) or 1
    # proporção entre palavras do roteiro e palavras transcritas (tolera pequenas diferenças)
    escala = len(tempos) / total_texto
    resultado, acum, inicio = [], 0, 0.0
    for i, n in enumerate(contagens):
        acum += n
        if i == len(cenas) - 1:
            fim = duracao_total
        else:
            idx = min(int(round(acum * escala)) - 1, len(tempos) - 1)
            fim = (tempos[idx][1] + tempos[min(idx + 1, len(tempos) - 1)][0]) / 2
        resultado.append((inicio, fim))
        inicio = fim
    return resultado
