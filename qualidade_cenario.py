"""
qualidade_cenario.py - detecta cenarios "lisos" (uma parede/ceu de uma cor so, sem objetos do lugar), que deixam personagem e
objetos soltos no quadro. Renderiza o cenario sozinho em baixa resolucao (9:16, como vai ao ar) e mede quanto do quadro e ocupado
pelas 3 cores mais comuns. Calibrado (sem vinheta): lisos 0.86-0.95; cenarios de lugar 0.43-0.61; cenarios reais da IA ate ~0.78. Limite 0.80.
"""
import tempfile

import numpy as np

LIMITE_TOP3 = 0.80
_cache = {}


def medir(img):
    a = np.asarray(img.convert("RGB").resize((135, 240)), dtype=np.int32) >> 5      # 3 bits por canal = 512 cores
    chave = a[..., 0] * 64 + a[..., 1] * 8 + a[..., 2]
    cnt = np.bincount(chave.ravel(), minlength=512)
    return float(np.sort(cnt)[-3:].sum() / chave.size)


def _quadro(bib, ref, clima="noite"):
    from estudio.estilos.cenas2d import Estilo
    from estudio.nucleo import Tela
    # sem vinheta/bloom/tint (eles espalham as cores e escondem o "liso")
    cena = {"modelo": "generica", "duracao": 3.0, "cenario": {"ref": ref}, "elementos": [], "clima": clima,
            "tema": {"vinheta": 0, "bloom_ganho": 0, "contraste": 1.0, "tint": [0, 0, 0], "faixa": {"forca": 0.0}}}
    tela = Tela(270, 480, 1)
    Estilo(270, 480, "alerta_noturno", bib).quadro(tela, 1.5, cena, {})
    return tela.img


def liso_na_biblioteca(bib, ref):
    """True se o cenario `ref` da biblioteca e liso demais. Resultado em cache por processo."""
    if ref not in _cache:
        try:
            _cache[ref] = medir(_quadro(bib, ref)) >= LIMITE_TOP3
        except Exception:  # noqa  - se nao der para medir, nao mexe no cenario
            _cache[ref] = False
    return _cache[ref]


def liso_rec(rec):
    """True se o recurso de cenario (dict ainda nao registrado) e liso demais."""
    from estudio.cenas2d.recursos.biblioteca import Biblioteca
    try:
        with tempfile.TemporaryDirectory() as tmp:
            b = Biblioteca(tmp, aprovacao="auto")
            r = b.registrar(dict(rec))
            return medir(_quadro(b, r.id)) >= LIMITE_TOP3
    except Exception:  # noqa
        return False
