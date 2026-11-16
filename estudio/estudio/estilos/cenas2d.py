"""
cenas2d.py - estilo 'cenas2d' (motor M1 - Cenas 2D em Camadas). Prototipo da Fase 4.1: preset `alerta_noturno`.

Segue o contrato dos estilos do `estudio`:
    Estilo(w, h).fundo(tela)  /  Estilo(w, h).quadro(tela, t, cena, canal)     (funcao pura de t)
A cena escolhe o modelo com  cena["modelo"]  (vocabulario fechado, veja MODELOS) e traz:
    duracao, legenda[{ini,fim,texto}], destaques[...], hora/dia (HUD), e campos proprios de cada modelo.
Internamente o quadro e composto em RGB (w x h) com supersampling nas formas; o `Tela` do nucleo recebe o
resultado pronto (use S=1 em nucleo.renderizar).
"""
from ..cenas2d.cena_generica import CenaGenerica
from ..cenas2d.cenas import CenaNivel, CenaNumero, CenaObjetoHeroi, CenaPessoaTela

MODELOS = {"objeto_heroi": CenaObjetoHeroi, "nivel": CenaNivel, "pessoa_tela": CenaPessoaTela, "numero": CenaNumero, "generica": CenaGenerica}
PRESETS = ["alerta_noturno"]


def validar_cena(c):
    erros = []
    if c.get("modelo", "objeto_heroi") not in MODELOS:
        erros.append(f"modelo '{c.get('modelo')}' nao existe (use: {', '.join(MODELOS)})")
    if float(c.get("duracao", 0)) <= 0:
        erros.append("duracao deve ser > 0")
    return erros


def normalizar(c):
    """corrige pequenos erros de vocabulario (a IA pode errar sem quebrar o video); devolve (cena, avisos)"""
    c, avisos = dict(c), []
    if c.get("modelo", "objeto_heroi") not in MODELOS:
        avisos.append(f"modelo '{c.get('modelo')}' trocado por 'objeto_heroi'")
        c["modelo"] = "objeto_heroi"
    c.setdefault("legenda", [])
    c.setdefault("destaques", [])
    return c, avisos


class Estilo:
    nome = "cenas2d"

    def __init__(self, w, h, preset="alerta_noturno", biblioteca=None):
        self.w, self.h, self.preset, self.bib = w, h, preset, biblioteca
        self.formato = "9x16" if h > w else "16x9"
        self._cenas = {}

    def fundo(self, tela):
        pass

    def _cena(self, cena):
        k = id(cena)
        if k not in self._cenas:
            cls = MODELOS[cena.get("modelo", "objeto_heroi")]
            self._cenas[k] = cls(cena, self.w, self.h, self.formato, bib=self.bib) if getattr(cls, "USA_BIB", False) else cls(cena, self.w, self.h, self.formato)
        return self._cenas[k]

    def quadro(self, tela, t, cena, canal):
        tela.img.paste(self._cena(cena).quadro(t))
