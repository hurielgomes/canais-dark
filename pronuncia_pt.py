"""pronuncia_pt.py - prepara texto para TTS (Kokoro/Voicebox) sem silabacao automatica por padrao.

A regra e a mesma que voce usava no criar_video.py: palavra com acento grafico e 3+ silabas cujo acento NAO esta na ultima
silaba vira silabada com hifen (ex.: "medico" -> "me-di-co"). So afeta o TEXTO ENVIADO A VOZ; as legendas continuam com a fala original.
Sem o Pyphen instalado (pip install pyphen) nao faz nada. Silabacao automatica desligada por padrao. Correcoes foneticas so devem ser adicionadas manualmente no canal.json quando uma palavra apresentar erro comprovado.
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
    """Prepara exclusivamente o texto TTS: pontuacao e correcoes foneticas opcionais configuraveis. Silabacao automatica desativada por padrao."""
    cfg = (canal or {}).get("tts") or {}
    if not texto:
        return texto

    # Voiceboxes frequentemente ignoram o ponto-e-virgula; converte em pausa clara.
    texto = re.sub(r"\s*;\s*([a-zà-ÿ])", lambda m: ". " + m.group(1).upper(), texto)
    texto = re.sub(r"\s*;\s*", ". ", texto)
    texto = re.sub(r"\s*\.{3,}\s*", ". ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()

    # Correcoes especificas da voz/canal. Formato: {"palavra/frase": "forma fonetica".
    # Mantem roteiro, legenda e texto de tela intactos.
    correcoes = cfg.get("correcoes_pronuncia") or {}
    for original, substituto in correcoes.items():
        if original and substituto:
            def preservar_maiuscula(match):
                replacement = str(substituto)
                return replacement[:1].upper() + replacement[1:] if match.group(0)[:1].isupper() else replacement
            texto = re.sub(re.escape(str(original)), preservar_maiuscula, texto, flags=re.IGNORECASE)

    if cfg.get("hifenizar_proparoxitonas", False) is False:
        return texto
    return hifenizar_proparoxitonas(texto)
