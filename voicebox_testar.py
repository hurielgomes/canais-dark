"""Diagnostico do Voicebox para a Fabrica.

Uso:   python voicebox_testar.py [canal]        (padrao: exemplo)
Faz: health check, lista perfis, mostra os campos da API (/openapi.json), gera 2 frases (normal e pergunta),
mede a VELOCIDADE (quantos segundos de processamento por segundo de audio) e salva os WAVs em voicebox_teste/.
Se algo falhar, copie TODA a saida e envie para ajustar a integracao.
"""
import json
import sys
import time
from pathlib import Path

import tts_voicebox as T

RAIZ = Path(__file__).resolve().parent
FRASES = ["Se o mundo inteiro ficasse setenta e duas horas sem energia eletrica, o que realmente aconteceria?",
          "Nas primeiras horas, os celulares perdem sinal, os semaforos apagam e os hospitais dependem de geradores."]


def carregar_canal(nome):
    arq = RAIZ / "canais" / nome / "canal.json"
    return json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else {}


def main():
    canal = carregar_canal(sys.argv[1] if len(sys.argv) > 1 else "exemplo")
    if not (canal.get("tts") or {}).get("motor"):
        canal["tts"] = {"motor": "voicebox", "engine": "qwen", "idioma": "pt"}
        print("(canal sem bloco 'tts': usando engine=qwen, idioma=pt, primeiro perfil do Voicebox)")
    cfg = T._cfg(canal)
    print("configuracao:", json.dumps({k: v for k, v in cfg.items()}, ensure_ascii=False))
    T.garantir_servidor(cfg)
    print("[ok] servidor respondeu em", cfg["url"])
    code, _, corpo = T._req(cfg["url"] + "/health", timeout=10)
    print("health:", corpo[:300].decode("utf-8", "ignore"))
    code, _, corpo = T._req(cfg["url"] + "/openapi.json", timeout=15)
    if code == 200:
        try:
            api = json.loads(corpo)
            esq = api.get("components", {}).get("schemas", {})
            for nome in ("GenerationRequest", "GenerationResponse"):
                if nome in esq:
                    print(f"{nome}:", json.dumps(esq[nome].get("properties", {}) and {k: v.get("type", v.get("anyOf", "?")) for k, v in esq[nome]["properties"].items()}, ensure_ascii=False)[:900])
        except ValueError:
            pass
    perfis = T._lista_perfis(cfg)
    print("perfis:", [p.get("name") for p in perfis])
    pid = T.achar_perfil(cfg)
    print("perfil escolhido:", pid)
    saida = RAIZ / "voicebox_teste"
    saida.mkdir(exist_ok=True)
    for n, frase in enumerate(FRASES, 1):
        t0 = time.time()
        wav = T.gerar_wav_bytes(frase, cfg, pid, T.instruct_para(frase, cfg))
        dt = time.time() - t0
        dados, taxa = T._ler_audio(wav)
        dur = len(dados) / taxa
        (saida / f"teste_{n}.wav").write_bytes(wav)
        print(f"[ok] frase {n}: {dur:.1f}s de audio em {dt:.1f}s -> {dt / max(dur, 0.1):.2f}x (menor que 1,0 = mais rapido que o audio)")
        if n == 1:
            rtf = dt / max(dur, 0.1)
    print(f"\nEstimativa para uma narracao de 60 s: ~{rtf * 60 / 60:.1f} min de processamento (so da voz).")
    print("Ouca os arquivos em", saida)


if __name__ == "__main__":
    try:
        main()
    except T.VoiceboxErro as e:
        print("[ERRO]", e)
        sys.exit(1)
