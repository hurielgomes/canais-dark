"""pronuncia_pt.py - ajuda o TTS (Kokoro/Voicebox) com palavras acentuadas, separando as silabas por hifen (Pyphen, opcional).

A regra e a mesma que voce usava no criar_video.py: palavra com acento grafico e 3+ silabas cujo acento NAO esta na ultima
silaba vira silabada com hifen (ex.: "medico" -> "me-di-co"). So afeta o TEXTO ENVIADO A VOZ; as legendas continuam com a fala original.
Sem o Pyphen instalado (pip install pyphen) nao faz nada. Desligar: canal.json -> "tts": {"hifenizar_proparoxitonas": false}.
"""
import re

_ACENTOS = re.compile(r"[áéíóúâêôÁÉÍÓÚÂÊÔ]")
_ACENTO_FINAL = re.compile(r"[áéíóúâêô]", re.IGNORECASE)
_PALAVRA = re.compile(r"\b[a-zA-ZÀ-ÿ]+\b")
_dic = None
_tentou = False


def _dicionario():
    global _dic, _tentou
    if not _tentou:
        _tentou = True
        try:
            import pyphen
            _dic = pyphen.Pyphen(lang="pt_BR")
        except Exception:  # noqa  (Pyphen nao instalado)
            _dic = None
    return _dic


def definir_dicionario(dic):
    """testes: injeta um dicionario com .inserted(palavra, hyphen='-')"""
    global _dic, _tentou
    _dic, _tentou = dic, True


def hifenizar_proparoxitonas(texto: str) -> str:
    dic = _dicionario()
    if dic is None or not texto:
        return texto

    def processar(m):
        palavra = m.group(0)
        if _ACENTOS.search(palavra):
            silabada = dic.inserted(palavra, hyphen="-")
            silabas = silabada.split("-")
            if len(silabas) >= 3 and not _ACENTO_FINAL.search(silabas[-1]):
                return silabada
        return palavra
    return _PALAVRA.sub(processar, texto)


def preparar_para_voz(texto: str, canal=None) -> str:
    cfg = (canal or {}).get("tts") or {}
    if cfg.get("hifenizar_proparoxitonas", True) is False:
        return texto
    return hifenizar_proparoxitonas(texto)
