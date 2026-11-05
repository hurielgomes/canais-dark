"""
criar_video.py - Pipeline completo: tema -> video pronto (16:9 e 9:16).

Um comando faz tudo:
    python criar_video.py exemplo "Tema do video"

Etapas (cada uma salva seu resultado e pula o que ja existe, entao
se algo falhar voce roda o MESMO comando de novo e ele continua de onde parou):
    1. roteiro   -> IA (Gemini, plano gratuito) escreve roteiro, prompts de imagem e metadados
                    (ou voce usa o roteiro feito no My Hub: veja --so-prompt e --roteiro)
    2. voz       -> narracao de cada cena com Kokoro (gratuito, roda no seu PC)
    3. imagens   -> Gemini (Nano Banana) ou, se falhar, banco gratuito Pexels
    4. legendas  -> geradas do proprio roteiro (sem Whisper)
    5. montagem  -> FFmpeg: zoom, legendas, fade, musica opcional, 2 formatos
    6. publicacao.txt com titulo, descricao e tags

Opcoes:
    --duracao N        duracao alvo da narracao em segundos
    --roteiro ARQ      usa um roteiro JSON pronto (por exemplo, escrito no My Hub)
    --so-prompt        so gera o texto do pedido para colar no My Hub e sai
    --revisar          para depois do roteiro, para voce ler/editar antes de continuar
    --simular          teste sem internet e sem chaves (vozes e imagens falsas)
    --formatos 16x9    gera so um formato (padrao: 16x9,9x16)
    --ideias N         pede N ideias de temas ao Gemini e salva em canais/<canal>/temas.txt
    --lote ARQ         cria um video para cada tema do arquivo (um por linha; # = comentario)

Cenas podem usar imagem (.png/.jpg) ou video (.mp4): coloque o arquivo na pasta 'imagens' do projeto
com o numero da cena (ex.: 03.mp4) e ele sera usado no lugar do automatico.
"""

import argparse
import base64
import json
from editorial_rules import get_category, ensure_closing_question
import math
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import wave
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
FPS = 30
ESCALA_INTERNA = 1.5       # resolucao interna do zoom (maior = mais suave, mais lento)
# (zoom_ini, zoom_fim, pan_x_ini, pan_x_fim, pan_y_ini, pan_y_fim)
PRESETS = [
    (1.00, 1.30, 0.5, 0.5, 0.5, 0.5),    # aproxima no centro
    (1.25, 1.25, 0.15, 0.85, 0.5, 0.5),  # desliza esquerda -> direita
    (1.35, 1.00, 0.5, 0.5, 0.5, 0.5),    # afasta
    (1.25, 1.25, 0.85, 0.15, 0.5, 0.5),  # desliza direita -> esquerda
    (1.25, 1.25, 0.5, 0.5, 0.9, 0.1),    # sobe
    (1.00, 1.35, 0.5, 0.3, 0.5, 0.4),    # aproxima desviando
    (1.30, 1.30, 0.5, 0.5, 0.1, 0.9),    # desce
]
# onde recortar a imagem (0 a 1) para cada plano: da "angulos" diferentes da mesma imagem
ENQUADRES = [(0.5, 0.5), (0.2, 0.35), (0.8, 0.65), (0.35, 0.72), (0.65, 0.28), (0.5, 0.2), (0.5, 0.8)]
FADE = 0.6
PAUSA_GANCHO = 0.8          # silencio depois da pergunta de abertura (segundos)
PAUSA_CENA = 0.35          # silencio ao fim de cada cena (segundos)
PALAVRAS_POR_SEGUNDO = 2.5
EXT_VIDEO = (".mp4", ".mov", ".webm", ".mkv")
EXT_AUDIO = (".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac")
FORMATOS = {"16x9": (1920, 1080), "9x16": (1080, 1920)}
KOKORO_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"

PADROES = {
    "gemini_api_key": "",
    "pexels_api_key": "",
    "pixabay_api_key": "",
    "cloudflare_account_id": "",
    "cloudflare_api_token": "",
    "modelo_cloudflare": "@cf/black-forest-labs/flux-1-schnell",
    "cloudflare_steps": 4,
    "provedores_imagem": ["cloudflare", "gemini", "pixabay", "pexels"],
    "modelo_texto": "gemini-3.8-flash",
    "modelos_texto_fallback": ["gemini-3.6-flash", "gemini-3.5-flash-lite"],
    "modelo_imagem": "gemini-3.1-flash-lite-image",
    "imagem_ia": False,          # True = tenta gerar imagens com o Gemini (pode exigir plano pago)
    "pausa_entre_imagens": 4,
}


# ---------------------------------------------------------------- utilidades

def erro(msg):
    print(f"\nERRO: {msg}\n")
    sys.exit(1)


def info(msg):
    print(msg, flush=True)


def rodar(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-1800:])
        erro("o FFmpeg falhou (veja a mensagem acima).")
    return r.stdout


def duracao_arquivo(caminho):
    saida = rodar(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                   "-of", "default=noprint_wrappers=1:nokey=1", str(caminho)])
    return float(saida.strip())


def slug(texto):
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower()
    return t[:50] or "video"


def ler_json(caminho):
    return json.loads(Path(caminho).read_text(encoding="utf-8"))


def salvar_json(caminho, dados):
    Path(caminho).write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def baixar(url, destino, cabecalhos=None):
    destino = Path(destino)
    req = urllib.request.Request(url, headers=cabecalhos or {"User-Agent": "criar-video/1.0"})
    parcial = destino.with_name(destino.name + ".part")
    with urllib.request.urlopen(req, timeout=120) as r, open(parcial, "wb") as f:
        shutil.copyfileobj(r, f)
    parcial.replace(destino)


def com_retry(fn, tentativas=4, espera_inicial=8):
    """Retry exponencial para falhas temporarias do provedor."""
    espera = max(1, int(espera_inicial))
    for t in range(tentativas):
        try:
            return fn()
        except Exception as e:  # noqa
            msg = str(e)
            temporario = any(k in msg for k in ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE", "500", "INTERNAL"))
            if t == tentativas - 1 or not temporario:
                raise
            info(f"   limite ou instabilidade ({msg[:90]}...). Aguardando {espera}s e tentando de novo.")
            time.sleep(espera)
            espera *= 2


def _erro_indisponibilidade_modelo(exc):
    """Somente erros de indisponibilidade do servidor autorizam trocar de modelo.

    429/quota, chave inválida, permissão e modelo inexistente não são mascarados
    por fallback automático.
    """
    msg = str(exc).upper()
    return any(token in msg for token in ("503", "UNAVAILABLE", "500", "INTERNAL SERVER ERROR"))


def gerar_conteudo_texto_com_fallback(cliente, cfg, contents, generation_config, operacao="texto"):
    """Gera texto com o modelo principal e alternativas se o backend estiver indisponível.

    A ordem padrão é gemini-3.8-flash -> gemini-3.6-flash -> gemini-3.5-flash-lite.
    Só alterna após esgotar tentativas curtas do modelo atual e apenas para 5xx/UNAVAILABLE.
    """
    principal = str(cfg.get("modelo_texto") or "gemini-3.8-flash").strip()
    alternativas = cfg.get("modelos_texto_fallback", ["gemini-3.6-flash", "gemini-3.5-flash-lite"])
    if isinstance(alternativas, str):
        alternativas = [x.strip() for x in alternativas.split(",") if x.strip()]
    if not isinstance(alternativas, (list, tuple)):
        alternativas = []
    modelos = []
    for nome in [principal, *alternativas]:
        nome = str(nome or "").strip()
        if nome and nome not in modelos:
            modelos.append(nome)
    if not modelos:
        raise RuntimeError("Nenhum modelo de texto foi configurado.")

    ultimo_erro = None
    for indice, nome_modelo in enumerate(modelos):
        try:
            resposta = com_retry(
                lambda nome=nome_modelo: cliente.models.generate_content(
                    model=nome, contents=contents, config=generation_config
                ),
                tentativas=3,
                espera_inicial=6,
            )
            if indice > 0:
                info(f"   fallback concluido: {operacao} gerado com {nome_modelo} (modelo principal: {principal}).")
            return resposta
        except Exception as exc:  # noqa
            ultimo_erro = exc
            if not _erro_indisponibilidade_modelo(exc) or indice == len(modelos) - 1:
                raise
            proximo = modelos[indice + 1]
            info(f"   modelo {nome_modelo} indisponivel (5xx/UNAVAILABLE). Tentando alternativa {proximo} para {operacao}.")
    raise ultimo_erro or RuntimeError("Falha desconhecida na geração de texto.")


def carregar_env_local():
    """Carrega .env local sem sobrescrever variaveis ja definidas no Windows."""
    arq = RAIZ / ".env"
    if not arq.is_file():
        return
    try:
        linhas = arq.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return
    for linha in linhas:
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        chave = chave.strip()
        valor = valor.strip()
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in ("'", '"'):
            valor = valor[1:-1]
        if chave and chave not in os.environ:
            os.environ[chave] = valor


def carregar_config():
    carregar_env_local()
    cfg = dict(PADROES)
    arq = RAIZ / "config.json"
    if arq.exists():
        cfg.update({k: v for k, v in ler_json(arq).items() if v not in (None,)})
    cfg["gemini_api_key"] = os.environ.get("GEMINI_API_KEY") or cfg["gemini_api_key"]
    cfg["pexels_api_key"] = os.environ.get("PEXELS_API_KEY") or cfg["pexels_api_key"]
    cfg["pixabay_api_key"] = os.environ.get("PIXABAY_API_KEY") or cfg["pixabay_api_key"]
    cfg["cloudflare_account_id"] = os.environ.get("CLOUDFLARE_ACCOUNT_ID") or cfg["cloudflare_account_id"]
    cfg["cloudflare_api_token"] = os.environ.get("CLOUDFLARE_API_TOKEN") or cfg["cloudflare_api_token"]
    for k in ("gemini_api_key", "pexels_api_key", "pixabay_api_key", "cloudflare_account_id", "cloudflare_api_token"):
        if str(cfg.get(k, "")).startswith("COLE_AQUI"):
            cfg[k] = ""
    return cfg


def carregar_canal(nome):
    arq = RAIZ / "canais" / nome / "canal.json"
    if not arq.exists():
        erro(f"nao encontrei {arq}. Copie canais\\exemplo\\canal.json para uma pasta nova em canais\\.")
    c = ler_json(arq)
    c.setdefault("idioma", "portugues do Brasil")
    c.setdefault("duracao_alvo_segundos", 60)
    c.setdefault("segundos_por_imagem", 6)
    c.setdefault("voz", "pf_dora")
    c.setdefault("idioma_tts", "pt-br")
    c.setdefault("velocidade", 1.08)
    c.setdefault("pausa_entre_cenas", 0.2)
    c.setdefault("pausa_gancho", 0.8)           # silencio depois da cena 1 (a pergunta)
    c.setdefault("velocidade_gancho", 0.92)     # a pergunta de abertura e falada um pouco mais devagar
    c.setdefault("musica", "")                 # vazio = usa a pasta "musicas" do canal, se existir
    c.setdefault("volume_musica", 0.12)        # 0.05 (baixinha) a 0.25 (alta)
    c.setdefault("estilo_visual", "vibrant saturated colors, dramatic cinematic lighting, high contrast, "
                                  "ultra detailed, sharp focus, epic composition")
    c.setdefault("duracao_plano", 2.8)          # segundos entre cortes de camera
    c.setdefault("gancho_segundos", 2.6)        # tempo do texto grande de abertura
    c.setdefault("legenda_fonte", "Arial Black")
    c.setdefault("legenda_maiusculas", True)
    c.setdefault("legenda_palavras", 4)
    c.setdefault("saturacao", 1.25)
    c.setdefault("contraste", 1.08)
    c.setdefault("nitidez", 0.7)
    c.setdefault("vinheta", True)
    c.setdefault("usar_video_stock", True)     # usa clipes do banco de videos (Pixabay) quando ha chave
    c.setdefault("proporcao_video", 0.5)       # fracao das cenas que pedem video (0 a 1)
    c.setdefault("duracao_plano_video", 4.0)   # segundos entre cortes em cenas de video
    c.setdefault("escala_interna", 1.5)       # 1.0 = renderiza mais rapido; 2.0 = zoom mais suave e mais lento
    c.setdefault("identidade", {})
    identidade = c["identidade"] if isinstance(c["identidade"], dict) else {}
    identidade.setdefault("nome_exibicao", c.get("nome", nome))
    identidade.setdefault("logo_arquivo", "identidade/logo.png")
    identidade.setdefault("marca_dagua", {"ativa": True, "opacidade": 0.22, "posicao": "inferior_direita", "largura_percentual": 10})
    identidade.setdefault("intro", {"ativa": False, "arquivo": "identidade/intro.mp4"})
    identidade.setdefault("thumbnail", {"incluir_logo": True})
    c["identidade"] = identidade
    c["_pasta"] = arq.parent
    return c


# ------------------------------------------------------------------- roteiro

def aplicar_modo_tema(canal, categoria="curiosidades"):
    """modo_tema 'livre': tema, tom e estrutura vêm da categoria, não do canal.
    modo_tema 'livre' (padrão): mantém o comportamento atual."""
    if str(canal.get("modo_tema", "livre")).strip().lower() != "livre":
        return canal
    cat = get_category(categoria) or {}
    ep = cat.get("editorial_profile", {})
    c = dict(canal)
    c["nicho"] = f"{cat.get('name', categoria)}: {cat.get('description', '')}"
    c["publico"] = canal.get("publico_livre") or "adultos curiosos, público geral"
    c["tom"] = ep.get("tone", "")
    c["estrutura"] = list(ep.get("structure", []))
    c["regras"] = list(canal.get("regras_globais", []))
    return c


def titulos_anteriores(canal_nome, atual):
    base = RAIZ / "projetos" / canal_nome
    titulos = []
    if base.exists():
        for p in sorted(base.iterdir()):
            r = p / "roteiro.json"
            if p != atual and r.exists():
                try:
                    titulos.append(ler_json(r).get("titulo", ""))
                except Exception:  # noqa
                    pass
    return [t for t in titulos if t][-10:]


def montar_prompt_roteiro(canal, tema, duracao, anteriores, categoria="curiosidades"):
    canal = aplicar_modo_tema(canal, categoria)
    palavras_total = int(duracao * PALAVRAS_POR_SEGUNDO)
    palavras_cena = int(canal["segundos_por_imagem"] * PALAVRAS_POR_SEGUNDO)
    n_cenas = max(3, round(duracao / canal["segundos_por_imagem"]))
    estrutura = "\n".join(f"  {i}. {e}" for i, e in enumerate(canal.get("estrutura", []), 1)) or "  (livre, mas comece com um gancho forte)"
    regras = "\n".join(f"- {r}" for r in canal.get("regras", []))
    ant = "\n".join(f"- {t}" for t in anteriores) or "(nenhum ainda)"
    perfil_categoria = get_category(categoria).get("editorial_profile", {})
    bloco_categoria = "\n".join([
        f"OBJETIVO: {perfil_categoria.get('objective','')}",
        f"TOM: {perfil_categoria.get('tone','')}",
        "ESTRUTURA: " + "; ".join(perfil_categoria.get("structure", [])),
        f"REGRAS FACTUAIS: {perfil_categoria.get('fact_policy','')}",
        f"EVITAR: {perfil_categoria.get('avoid','')}",
        f"DIRECAO VISUAL: {perfil_categoria.get('visual_guidance','')}",
    ])
    fechamento_categoria = perfil_categoria.get("closing_question", "Encerre com uma pergunta natural e específica para convidar comentários.")
    if canal.get("_usa_video"):
        pct = int(float(canal["proporcao_video"]) * 100)
        bloco_visual = f"""
TIPO DE VISUAL DE CADA CENA (campo "visual"):
- "video": cenas de atmosfera, ação ou generalidades (paisagens, mar, deserto, cidade, multidão, natureza, céu, máquinas, mãos trabalhando). Em cenas "video", "busca_stock" deve ter 2 ou 3 palavras em inglês, genéricas e comuns (ex.: "ocean waves", "desert sunrise"), porque bancos de vídeo não têm itens muito específicos.
- "imagem": objeto, personagem, lugar ou momento específico e único, que só uma imagem gerada por IA consegue mostrar.
Cerca de {pct}% das cenas devem ser "video". Preencha SEMPRE "imagem" e "busca_stock" em todas as cenas (a imagem serve de reserva se não houver vídeo)."""
        campo_visual = ', "visual": "video ou imagem"'
    else:
        bloco_visual, campo_visual = "", ""
    return f"""Você é roteirista de um canal de YouTube do tipo "dark" (sem apresentador, só narração e imagens), especialista em retenção de audiência.
Escreva o roteiro completo de UM vídeo.

CANAL: {canal.get('nome', '')}
NICHO: {canal.get('nicho', '')}
PÚBLICO: {canal.get('publico', '')}
TOM: {canal.get('tom', '')}
IDIOMA DA NARRAÇÃO: {canal['idioma']}

TEMA DO VÍDEO: {tema}

TAMANHO: cerca de {palavras_total} palavras de narração no total, divididas em {n_cenas} cenas de aproximadamente {palavras_cena} palavras cada.

A CENA 1 É SÓ O GANCHO (regras):
- A cena 1 tem UMA frase curta (até 16 palavras) que NÃO conta a história: é apenas uma pergunta direta ou uma afirmação intrigante que gera dúvida. Prefira perguntas ("Por que...?", "O que aconteceria se...?", "Quem...?").
- A explicação só começa na cena 2, que responde ou desenvolve a pergunta da cena 1. Exemplo: cena 1: "Por que milhares de pessoas abandonaram a superfície para viver na escuridão?" / cena 2: "Isso aconteceu porque, em 1963, um homem reformava a casa e achou uma cidade inteira no subsolo."
- NUNCA coloque na cena 1 data, contexto, fato narrativo ou a resposta. A cena 1 deve fazer sentido sozinha, com uma pausa depois dela.
- PROIBIDO: "Neste vídeo", "Você sabia", "Hoje vamos falar", saudações, definições de dicionário, introduções genéricas.
- Você pode prometer um pagamento no final ("o último motivo é o mais estranho") SOMENTE se o vídeo realmente o entregar. Em temas de lista de motivos ou curiosidades, deixe o item mais surpreendente para o fim.

RITMO E RETENÇÃO:
- Frases curtas (6 a 14 palavras) e linguagem falada. Uma ideia nova por cena.
- A cada 2 ou 3 cenas, um mini-gancho que puxe para a próxima parte (varie a fórmula, não repita a mesma frase).
- Seja específico: nomes, lugares, números e datas, mas SOMENTE se tiver certeza. Se não tiver certeza de um dado, não o inclua.
- Escreva com suas palavras, com ponto de vista e explicação, não apenas uma lista de fatos. Não copie textos de terceiros.
- A última cena retoma a pergunta do início, fecha com uma ideia marcante E termina com uma pergunta específica para estimular comentários.
- PERGUNTA FINAL ADEQUADA À CATEGORIA: {fechamento_categoria}
- A pergunta deve combinar com o tom do canal e do assunto: humor para conteúdo descontraído; pergunta séria para conteúdo sério. Evite CTA genérico.
- Sem emojis nem marcações como "[cena]".

ESTRUTURA (siga a ordem):
{estrutura}

VARIE EM RELAÇÃO AOS VÍDEOS ANTERIORES DO CANAL (abertura, ritmo e fórmulas):
{ant}
{regras}

IMAGENS (o programa já acrescenta automaticamente o estilo visual do canal, então NÃO o repita):
- Cada prompt de imagem é em INGLÊS e segue o formato: [tipo de plano], [assunto concreto em ação], [ambiente], [iluminação e cores].
- Varie o tipo de plano entre as cenas (extreme close-up, low angle, aerial wide shot, over-the-shoulder, macro, silhouette, dutch angle...).
- O assunto deve PREENCHER o quadro e ficar no centro (a imagem também será recortada na vertical). Prefira cores vibrantes, alto contraste e uma única ideia visual forte por cena.
- NÃO inclua texto, letras, números, logotipos nem pessoas reais identificáveis.

{bloco_visual}

Responda SOMENTE com JSON válido, sem comentários e sem blocos de código, neste formato:
{{
  "titulo": "até 65 caracteres, específico, gera curiosidade (pergunta ou revelação) e o vídeo cumpre o que ele promete",
  "titulos_alternativos": ["2 outros títulos com abordagens diferentes, para teste A/B"],
  "gancho_texto": "versão de até 6 palavras da pergunta da cena 1, aparece em letras grandes nos 3 primeiros segundos",
  "descricao": "descrição para o YouTube, 2 a 4 frases mais uma linha de chamada",
  "tags": ["8 a 12 palavras-chave"],
  "texto_miniatura": "até 4 palavras que provocam curiosidade, sem repetir o título",
  "pergunta_final": "pergunta contextual para estimular comentários, coerente com categoria e tom",
  "prompt_miniatura": "prompt em inglês para a miniatura: um único assunto grande, expressivo e centralizado, clima de suspense ou curiosidade, cores vibrantes, alto contraste, espaço livre ao lado para texto, sem texto. NUNCA use pessoas reais, celebridades, políticos, partidos, bandeiras ou símbolos políticos",
  "cenas": [
    {{"narracao": "texto exato que será falado"{campo_visual}, "imagem": "image prompt in English", "busca_stock": "2 or 3 english words for stock search"}}
  ]
}}"""


def gerar_roteiro_gemini(canal, tema, duracao, anteriores, cfg, categoria="curiosidades"):
    if not cfg["gemini_api_key"]:
        erro("falta a chave do Gemini. Veja o passo a passo (aistudio.google.com) e coloque em config.json.")
    from google import genai
    from google.genai import types
    cliente = genai.Client(api_key=cfg["gemini_api_key"],
                       http_options=types.HttpOptions(timeout=120000))
    prompt = montar_prompt_roteiro(canal, tema, duracao, anteriores, categoria)
    info("   pedindo o roteiro ao Gemini...")
    try:
        resp = gerar_conteudo_texto_com_fallback(
            cliente, cfg, prompt,
            types.GenerateContentConfig(response_mime_type="application/json", temperature=0.9),
            operacao="roteiro",
        )
    except Exception as e:  # noqa
        msg = str(e)
        print(f"\nO Gemini recusou o pedido:\n{msg[:600]}\n")
        if "404" in msg or "NOT_FOUND" in msg or "no longer available" in msg:
            erro(f"o modelo '{cfg['modelo_texto']}' nao esta disponivel para a sua chave. "
                 "Troque 'modelo_texto' no config.json pelo nome que a mensagem acima sugere.")
        if "API key" in msg or "API_KEY" in msg or "401" in msg or "403" in msg or "PERMISSION" in msg:
            erro("problema com a chave do Gemini. Confira o config.json (sem espacos, entre aspas).")
        erro("nao foi possivel gerar o roteiro. Leia a mensagem acima e, se nao entender, me envie.")
    texto = (resp.text or "").strip()
    texto = re.sub(r"^```(?:json)?|```$", "", texto, flags=re.M).strip()
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        erro("o Gemini nao devolveu um JSON valido. Rode o mesmo comando de novo.")


def validar_roteiro(r):
    if not isinstance(r, dict) or not r.get("cenas"):
        erro("roteiro sem a lista 'cenas'.")
    for i, c in enumerate(r["cenas"], 1):
        if not c.get("narracao"):
            erro(f"cena {i} sem 'narracao'.")
        c.setdefault("imagem", r.get("titulo", "cinematic scene"))
        c.setdefault("busca_stock", "")
        c["visual"] = "video" if str(c.get("visual", "")).lower().startswith("v") else "imagem"
    r.setdefault("titulo", "video")
    r.setdefault("descricao", "")
    r.setdefault("tags", [])
    r.setdefault("gancho_texto", "")
    r.setdefault("titulos_alternativos", [])
    r.setdefault("texto_miniatura", "")
    return r


# ----------------------------------------------------------------------- voz

def wav_simulado(destino, segundos, pausa=None):
    taxa = 24000
    n = int(taxa * segundos)
    pad = int(taxa * (PAUSA_CENA if pausa is None else pausa))
    with wave.open(str(destino), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(taxa)
        quadros = bytearray()
        for i in range(n):
            v = int(6000 * math.sin(2 * math.pi * 220 * i / taxa))
            quadros += v.to_bytes(2, "little", signed=True)
        quadros += bytes(2 * pad)
        w.writeframes(bytes(quadros))


def carregar_kokoro():
    pasta = RAIZ / "modelos"
    pasta.mkdir(exist_ok=True)
    for nome in ("kokoro-v1.0.onnx", "voices-v1.0.bin"):
        if not (pasta / nome).exists():
            info(f"   baixando {nome} (so na primeira vez; o modelo tem ~300 MB)...")
            baixar(KOKORO_URL + nome, pasta / nome)
    from kokoro_onnx import Kokoro
    return Kokoro(str(pasta / "kokoro-v1.0.onnx"), str(pasta / "voices-v1.0.bin"))


def gerar_voz(roteiro, pasta, canal, simular):
    pasta_audio = pasta / "audio"
    pasta_audio.mkdir(exist_ok=True)
    kokoro = None
    wavs = []
    for i, c in enumerate(roteiro["cenas"], 1):
        wav = pasta_audio / f"{i:02d}.wav"
        wavs.append(wav)
        if wav.exists():
            continue
        info(f"   voz da cena {i}/{len(roteiro['cenas'])}")
        if simular:
            wav_simulado(wav, max(2.0, len(c["narracao"].split()) / PALAVRAS_POR_SEGUNDO),
                         PAUSA_GANCHO if i == 1 else None)
            continue
        if kokoro is None:
            kokoro = carregar_kokoro()
        import numpy as np
        import soundfile as sf
        vel = float(canal["velocidade"]) * (float(canal["velocidade_gancho"]) if i == 1 else 1.0)
        amostras, taxa = kokoro.create(c["narracao"], voice=canal["voz"], speed=vel, lang=canal["idioma_tts"])
        pad = np.zeros(int(taxa * (PAUSA_GANCHO if i == 1 else PAUSA_CENA)), dtype=amostras.dtype)
        pad_ini = np.zeros(int(taxa * 0.15), dtype=amostras.dtype)
        sf.write(str(wav), np.concatenate([pad_ini, amostras, pad]), taxa)
    narracao = pasta / "narracao.wav"
    if not narracao.exists():
        (pasta_audio / "lista.txt").write_text("\n".join(f"file '{w.name}'" for w in wavs), encoding="utf-8")
        rodar(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "lista.txt", "-c", "copy",
               str(narracao.resolve())], cwd=pasta_audio)
    return narracao, [duracao_arquivo(w) for w in wavs]


# ------------------------------------------------------------------- imagens

def achar_imagem(pasta_imgs, i):
    achadas = sorted(pasta_imgs.glob(f"{i:02d}.*"))
    return achadas[0] if achadas else None


def _requisicao(req, timeout=120):
    """Faz a requisicao e devolve os bytes; transforma erros HTTP em mensagens legiveis."""
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        corpo = ""
        try:
            corpo = e.read().decode("utf-8", "ignore")[:300]
        except Exception:  # noqa
            pass
        raise RuntimeError(f"HTTP {e.code}: {corpo}")


def _salvar_bytes_imagem(dados, destino):
    if dados[:2] == b"\xff\xd8":
        ext = ".jpg"
    elif dados[:4] == b"\x89PNG":
        ext = ".png"
    elif dados[:4] == b"RIFF":
        ext = ".webp"
    else:
        raise RuntimeError("a resposta nao parece ser uma imagem")
    caminho = destino.with_suffix(ext)
    caminho.write_bytes(dados)
    return caminho


def imagem_gemini(cliente, modelo, prompt, destino):
    from google.genai import types
    configs = []
    try:
        configs.append(types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
            image_config=types.ImageConfig(aspect_ratio="16:9")))
    except Exception:  # noqa  (versao antiga da biblioteca)
        pass
    configs.append(types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]))
    ultimo = RuntimeError("falha desconhecida")
    for cfg in configs:
        try:
            resp = com_retry(lambda: cliente.models.generate_content(model=modelo, contents=[prompt], config=cfg))
        except Exception as e:  # noqa
            ultimo = e
            continue
        for cand in (resp.candidates or []):
            partes = cand.content.parts if cand.content else []
            for parte in partes or []:
                dados = getattr(parte, "inline_data", None)
                if dados and dados.data:
                    return _salvar_bytes_imagem(dados.data, destino)
        ultimo = RuntimeError("a resposta nao trouxe imagem (possivel bloqueio de seguranca)")
    raise ultimo


def imagem_cloudflare(conta, token, modelo, prompt, destino, steps=4):
    """Cloudflare Workers AI (FLUX). Plano gratuito com cota diaria."""
    url = f"https://api.cloudflare.com/client/v4/accounts/{conta}/ai/run/{modelo}"
    carga = {"prompt": prompt[:1800]}
    if "flux" in modelo:
        carga["steps"] = max(1, min(8, int(steps)))
    req = urllib.request.Request(
        url, data=json.dumps(carga).encode("utf-8"), method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "criar-video/1.0"})
    dados = _requisicao(req, timeout=180)
    if dados[:2] in (b"\xff\xd8",) or dados[:4] == b"\x89PNG":
        return _salvar_bytes_imagem(dados, destino)
    resp = json.loads(dados.decode("utf-8"))
    if not resp.get("success", True):
        raise RuntimeError(f"Cloudflare: {str(resp.get('errors'))[:250]}")
    b64 = (resp.get("result") or {}).get("image")
    if not b64:
        raise RuntimeError("Cloudflare nao devolveu imagem")
    return _salvar_bytes_imagem(base64.b64decode(b64), destino)


def imagem_pixabay(chave, busca, indice, destino):
    url = "https://pixabay.com/api/?" + urllib.parse.urlencode({
        "key": chave, "q": busca[:100], "image_type": "photo", "orientation": "horizontal",
        "safesearch": "true", "per_page": 10})
    req = urllib.request.Request(url, headers={"User-Agent": "criar-video/1.0"})
    fotos = json.loads(_requisicao(req, timeout=30).decode("utf-8")).get("hits") or []
    if not fotos:
        raise RuntimeError(f"sem resultados para '{busca}'")
    foto = fotos[indice % len(fotos)]
    alvo = foto.get("largeImageURL") or foto.get("webformatURL")
    req2 = urllib.request.Request(alvo, headers={"User-Agent": "criar-video/1.0"})
    return _salvar_bytes_imagem(_requisicao(req2, timeout=120), destino)


def imagem_pexels(chave, busca, indice, destino):
    url = "https://api.pexels.com/v1/search?" + urllib.parse.urlencode(
        {"query": busca, "orientation": "landscape", "per_page": 8})
    req = urllib.request.Request(url, headers={"Authorization": chave, "User-Agent": "criar-video/1.0"})
    fotos = json.loads(_requisicao(req, timeout=30).decode("utf-8")).get("photos") or []
    if not fotos:
        raise RuntimeError(f"sem resultados para '{busca}'")
    foto = fotos[indice % len(fotos)]
    alvo = foto["src"].get("large2x") or foto["src"]["original"]
    req2 = urllib.request.Request(alvo, headers={"User-Agent": "criar-video/1.0"})
    return _salvar_bytes_imagem(_requisicao(req2, timeout=120), destino)


def video_pixabay(chave, busca, indice, destino):
    url = "https://pixabay.com/api/videos/?" + urllib.parse.urlencode({
        "key": chave, "q": busca[:100], "per_page": 15, "safesearch": "true"})
    req = urllib.request.Request(url, headers={"User-Agent": "criar-video/1.0"})
    hits = json.loads(_requisicao(req, timeout=30).decode("utf-8")).get("hits") or []
    candidatos = []
    for h in hits:
        v = h.get("videos") or {}
        for tam in ("large", "medium"):
            if (v.get(tam) or {}).get("url"):
                candidatos.append((v[tam]["url"], h.get("duration", 0)))
                break
    if not candidatos:
        raise RuntimeError(f"sem videos para '{busca}'")
    longos = [c for c in candidatos if c[1] >= 4] or candidatos
    alvo = longos[indice % len(longos)][0]
    caminho = destino.with_suffix(".mp4")
    baixar(alvo, caminho)
    return caminho


def video_simulado(destino):
    caminho = destino.with_suffix(".mp4")
    rodar(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30", "-t", "6",
           "-pix_fmt", "yuv420p", str(caminho)])
    return caminho


CORES_SIM = ["0x1b2a49", "0x4a1b2a", "0x1b4a2f", "0x4a3d1b", "0x2f1b4a", "0x1b4a4a"]


def imagem_placeholder(destino, indice):
    caminho = destino.with_suffix(".png")
    rodar(["ffmpeg", "-y", "-f", "lavfi", "-i",
           f"color=c={CORES_SIM[indice % len(CORES_SIM)]}:s=1920x1080:d=1",
           "-frames:v", "1", str(caminho)])
    return caminho


ERROS_FATAIS = ("401", "402", "403", "404", "429", "NOT_FOUND", "PERMISSION", "billing", "quota",
                "limit", "neurons", "no longer available", "Unauthorized", "Forbidden", "api key")
IA = ("cloudflare", "gemini")


class FontesDeImagem:
    """Tenta, em ordem, os provedores de imagem que estao configurados."""

    def __init__(self, cfg, estilo=""):
        self.cfg = cfg
        self.estilo = estilo
        ordem = cfg.get("provedores_imagem") or ["cloudflare", "gemini", "pixabay", "pexels"]
        self.ativos = []
        for nome in ordem:
            if nome == "cloudflare" and cfg.get("cloudflare_account_id") and cfg.get("cloudflare_api_token"):
                self.ativos.append(nome)
            elif nome == "gemini" and cfg.get("imagem_ia") and cfg.get("gemini_api_key"):
                self.ativos.append(nome)
            elif nome == "pixabay" and cfg.get("pixabay_api_key"):
                self.ativos.append(nome)
            elif nome == "pexels" and cfg.get("pexels_api_key"):
                self.ativos.append(nome)
        self._gemini = None
        self.video_ativo = bool(cfg.get("pixabay_api_key"))

    def gerar_video(self, cena, indice, destino):
        busca = cena.get("busca_stock") or ""
        if not (self.video_ativo and busca):
            return None
        try:
            return video_pixabay(self.cfg["pixabay_api_key"], busca, indice, destino)
        except Exception as e:  # noqa
            msg = str(e)
            info(f"   [video] nao achei video para a cena {indice}: {msg[:140]}")
            if any(k.lower() in msg.lower() for k in ERROS_FATAIS):
                info("   [video] desativado nesta execucao (limite ou chave).")
                self.video_ativo = False
            return None

    def tem_alguma(self):
        return bool(self.ativos)

    def gerar(self, cena, indice, destino, so_ia=False):
        prompt = cena.get("imagem") or ""
        if prompt and self.estilo:
            prompt = f"{prompt}, {self.estilo}, no text, no watermark"
        busca = cena.get("busca_stock") or ""
        for nome in list(self.ativos):
            if so_ia and nome not in IA:
                continue
            if nome in IA and not prompt:
                continue
            if nome not in IA and not busca:
                continue
            try:
                if nome == "cloudflare":
                    caminho = imagem_cloudflare(self.cfg["cloudflare_account_id"], self.cfg["cloudflare_api_token"],
                                                self.cfg["modelo_cloudflare"], prompt, destino,
                                                self.cfg.get("cloudflare_steps", 4))
                elif nome == "gemini":
                    if self._gemini is None:
                        from google import genai
                        self._gemini = genai.Client(api_key=self.cfg["gemini_api_key"])
                    caminho = imagem_gemini(self._gemini, self.cfg["modelo_imagem"], prompt, destino)
                elif nome == "pixabay":
                    caminho = imagem_pixabay(self.cfg["pixabay_api_key"], busca, indice, destino)
                else:
                    caminho = imagem_pexels(self.cfg["pexels_api_key"], busca, indice, destino)
                if nome in IA:
                    time.sleep(float(self.cfg["pausa_entre_imagens"]))
                return caminho
            except Exception as e:  # noqa
                msg = str(e)
                info(f"   [{nome}] nao gerou a imagem {indice}: {msg[:160]}")
                if any(k.lower() in msg.lower() for k in ERROS_FATAIS):
                    info(f"   [{nome}] desativado nesta execucao (limite, chave ou plano). "
                         "Rode o mesmo comando mais tarde para completar as cenas que faltarem.")
                    self.ativos.remove(nome)
        return None


def gerar_imagens(roteiro, pasta, cfg, simular, estilo="", usar_video=False):
    pasta_imgs = pasta / "imagens"
    pasta_imgs.mkdir(exist_ok=True)
    fontes = None if simular else FontesDeImagem(cfg, estilo)
    caminhos, faltando = [], []
    for i, c in enumerate(roteiro["cenas"], 1):
        existente = achar_imagem(pasta_imgs, i)
        if existente:
            caminhos.append(existente)
            continue
        quer_video = usar_video and c.get("visual") == "video"
        info(f"   {'video' if quer_video else 'imagem'} da cena {i}/{len(roteiro['cenas'])}")
        destino = pasta_imgs / f"{i:02d}"
        caminho = None
        if simular:
            caminho = video_simulado(destino) if quer_video else imagem_placeholder(destino, i)
        else:
            if quer_video:
                caminho = fontes.gerar_video(c, i, destino)
            if caminho is None:
                caminho = fontes.gerar(c, i, destino)
        if caminho is None:
            faltando.append(i)
            caminho = pasta_imgs / f"pendente_{i:02d}.png"   # reserva temporaria, nao conta como pronta
            imagem_placeholder(pasta_imgs / f"pendente_{i:02d}", i)
        caminhos.append(caminho)
    if faltando:
        info(f"\n   ATENCAO: sem imagem real nas cenas {faltando}. Elas ficaram com um fundo liso.\n"
             f"   Rode o mesmo comando mais tarde (ex.: amanha, quando a cota diaria renovar) ou troque os "
             f"arquivos em {pasta_imgs} (pode ser .png, .jpg ou .mp4 com o mesmo numero).")
    return caminhos


def gerar_miniatura(roteiro, pasta, cfg, canal, simular, imagens, formato="16x9"):
    saida = pasta / "miniatura.jpg"
    if saida.exists():
        # A miniatura ja existe. Nao reaplique a logo em cima da mesma imagem a cada retomada.
        marcador = pasta / ".miniatura_logo_aplicada"
        identidade, logo_cfg = _identidade_canal(canal)
        thumb_cfg = identidade.get("thumbnail") if isinstance(identidade.get("thumbnail"), dict) else {}
        logo_habilitada = logo_cfg.is_file() and thumb_cfg.get("incluir_logo", True)
        logo_ja_processada = (logo_habilitada and marcador.exists()
                              and marcador.read_text(encoding="utf-8").strip() == str(logo_cfg.stat().st_mtime_ns))
        if not logo_ja_processada:
            original = pasta / "miniatura_sem_logo.jpg"
            if not original.exists():
                shutil.copy2(saida, original)
            else:
                shutil.copy2(original, saida)
            aplicar_logo_miniatura(saida, canal)
            if logo_habilitada:
                marcador.write_text(str(logo_cfg.stat().st_mtime_ns), encoding="utf-8")
            else:
                marcador.unlink(missing_ok=True)
        return saida
    origem = None
    if not simular and roteiro.get("prompt_miniatura"):
        fontes = FontesDeImagem(cfg, canal["estilo_visual"])
        achada = fontes.gerar({"imagem": roteiro["prompt_miniatura"] + ", ultra high contrast, eye-catching"},
                              0, pasta / "miniatura_base", so_ia=True)
        if achada:
            origem = achada
        else:
            info("   miniatura por IA indisponivel; usando a imagem da primeira cena.")
    if origem is None:
        origem = imagens[0]
    if Path(origem).suffix.lower() in EXT_VIDEO:
        quadro = pasta / "miniatura_quadro.png"
        rodar(["ffmpeg", "-y", "-ss", "1", "-i", str(origem), "-frames:v", "1", str(quadro)])
        origem = quadro
    texto = (roteiro.get("texto_miniatura") or "").strip()
    tw, th = (1280, 720) if formato == "16x9" else (1080, 1920)
    vf = (f"scale={tw}:{th}:force_original_aspect_ratio=increase:flags=lanczos,crop={tw}:{th},"
          "eq=saturation=1.3:contrast=1.12")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        if texto:
            (tmp / "t.ass").write_text(criar_ass_miniatura(texto, canal, tw, th), encoding="utf-8")
            vf += ",ass=t.ass"
        rodar(["ffmpeg", "-y", "-i", str(Path(origem).resolve()), "-vf", vf, "-frames:v", "1", "-q:v", "2",
               str(saida.resolve())], cwd=tmp)
    # Preserva a miniatura limpa para futuras atualizacoes de logo, sem sobrepor varias vezes.
    identidade, logo_cfg = _identidade_canal(canal)
    thumb_cfg = identidade.get("thumbnail") if isinstance(identidade.get("thumbnail"), dict) else {}
    if logo_cfg.is_file() and thumb_cfg.get("incluir_logo", True):
        base_clean = pasta / "miniatura_sem_logo.jpg"
        if not base_clean.exists():
            shutil.copy2(saida, base_clean)
    aplicar_logo_miniatura(saida, canal)
    if logo_cfg.is_file() and thumb_cfg.get("incluir_logo", True):
        (pasta / ".miniatura_logo_aplicada").write_text(str(logo_cfg.stat().st_mtime_ns), encoding="utf-8")
    return saida


# ------------------------------------------------------------------ legendas

def tempo_ass(s):
    cs = int(round(s * 100))
    h, resto = divmod(cs, 360000)
    m, resto = divmod(resto, 6000)
    seg, cent = divmod(resto, 100)
    return f"{h}:{m:02d}:{seg:02d}.{cent:02d}"


def dividir_em_trechos(texto, max_palavras=4):
    palavras = texto.split()
    trechos, atual = [], []
    for p in palavras:
        atual.append(p)
        if len(atual) >= max_palavras or re.search(r"[.!?;:,]$", p):
            trechos.append(" ".join(atual))
            atual = []
    if atual:
        if trechos and len(atual) == 1:
            trechos[-1] += " " + atual[0]      # evita trecho de uma palavra so no fim
        else:
            trechos.append(" ".join(atual))
    return trechos


POP_LEGENDA = r"{\fad(40,0)\t(0,90,\fscx108\fscy108)\t(90,190,\fscx100\fscy100)}"
POP_GANCHO = r"{\fad(80,250)\t(0,160,\fscx118\fscy118)\t(160,320,\fscx100\fscy100)}"


def criar_ass(roteiro, duracoes, w, h, canal):
    vertical = h > w
    fonte = canal["legenda_fonte"]
    f_leg, mv_leg, ml = (92, 430, 80) if vertical else (76, 80, 160)
    f_gan, mv_gan = (118, 380) if vertical else (100, 110)
    cab = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{fonte},{f_leg},&H00FFFFFF,&H000000FF,&H00000000,&H96000000,-1,0,0,0,100,100,1,0,1,6,2,2,{ml},{ml},{mv_leg},1
Style: Gancho,{fonte},{f_gan},&H0000D2FF,&H000000FF,&H00000000,&H96000000,-1,0,0,0,100,100,2,0,1,8,3,8,{ml},{ml},{mv_gan},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    maiusc = bool(canal["legenda_maiusculas"])
    linhas = []
    gancho = (roteiro.get("gancho_texto") or "").strip()
    if gancho:
        g = gancho.upper() if maiusc else gancho
        fim_g = float(canal["gancho_segundos"])
        linhas.append(f"Dialogue: 1,{tempo_ass(0.15)},{tempo_ass(fim_g)},Gancho,,0,0,0,,{POP_GANCHO}{g}")
    t0 = 0.0
    for idx, (cena, dur) in enumerate(zip(roteiro["cenas"], duracoes)):
        util = max(0.5, dur - (PAUSA_GANCHO if idx == 0 else PAUSA_CENA))
        trechos = dividir_em_trechos(cena["narracao"], int(canal["legenda_palavras"]))
        total_car = sum(len(x) for x in trechos) or 1
        t = t0
        for x in trechos:
            d = util * len(x) / total_car
            texto = (x.upper() if maiusc else x).replace("{", "(").replace("}", ")")
            linhas.append(f"Dialogue: 0,{tempo_ass(t)},{tempo_ass(t + d)},Default,,0,0,0,,{POP_LEGENDA}{texto}")
            t += d
        t0 += dur
    return cab + "\n".join(linhas) + "\n"


def criar_ass_miniatura(texto, canal, width=1280, height=720):
    linhas, pals = [], texto.upper().split()
    for i in range(0, len(pals), 2):
        linhas.append(" ".join(pals[i:i + 2]))
    corpo = r"\N".join(linhas)
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{canal['legenda_fonte']},{max(86, int(width * (0.103 if width > height else 0.085)))},&H0000D2FF,&H000000FF,&H00000000,&H96000000,-1,0,0,0,100,100,2,0,1,10,4,1,{int(width*0.04)},{int(width*0.04)},{int(height*0.06)},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:05.00,Default,,0,0,0,,{corpo}
"""


# ----------------------------------------------------------------- montagem

def planejar_planos(duracoes, canal, eh_video=None):
    """Divide cada cena em 'planos' curtos (cortes) e reparte os quadros sem acumular erro."""
    brutos = []
    for i, dur in enumerate(duracoes):
        alvo = float(canal["duracao_plano_video"] if eh_video and eh_video[i] else canal["duracao_plano"])
        if i == 0:
            alvo = min(alvo, 2.2)          # abertura mais rapida
        n = max(1, round(dur / alvo))
        brutos += [(i, dur / n)] * n
    planos, acumulado, quadros_ant = [], 0.0, 0
    for cena, d in brutos:
        acumulado += d
        fim = round(acumulado * FPS)
        planos.append((cena, max(2, fim - quadros_ant)))
        quadros_ant = fim
    return planos


def renderizar_plano(img, quadros, g, w, h, canal, destino):
    z0, z1, px0, px1, py0, py1 = PRESETS[g % len(PRESETS)]
    ex, ey = (0.5, 0.5) if g == 0 else ENQUADRES[g % len(ENQUADRES)]
    esc = max(1.0, float(canal["escala_interna"]))
    w2 = int(w * esc) // 2 * 2
    h2 = int(h * esc) // 2 * 2
    q = quadros
    filtros = [
        f"scale={w2}:{h2}:force_original_aspect_ratio=increase:flags=lanczos",
        f"crop={w2}:{h2}:(in_w-out_w)*{ex}:(in_h-out_h)*{ey}",
        (f"zoompan=z='{z0}+({z1}-{z0})*on/{q}'"
         f":x='(iw-iw/zoom)*({px0}+({px1}-{px0})*on/{q})'"
         f":y='(ih-ih/zoom)*({py0}+({py1}-{py0})*on/{q})'"
         f":d={q}:s={w}x{h}:fps={FPS}"),
        f"eq=saturation={canal['saturacao']}:contrast={canal['contraste']}",
    ]
    if float(canal["nitidez"]) > 0:
        filtros.append(f"unsharp=5:5:{canal['nitidez']}:5:5:0")
    if canal["vinheta"]:
        filtros.append("vignette=PI/5")
    filtros.append("format=yuv420p")
    rodar(["ffmpeg", "-y", "-i", str(img), "-vf", ",".join(filtros), "-c:v", "libx264",
           "-preset", "veryfast", "-crf", "16", "-r", str(FPS), str(destino)])


def renderizar_plano_video(clipe_orig, quadros, deslocamento, g, w, h, canal, destino):
    dur_clip = max(0.5, duracao_arquivo(clipe_orig))
    ss = deslocamento % max(dur_clip - 0.2, 0.3)
    ex = ENQUADRES[g % len(ENQUADRES)][0]
    filtros = [
        f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos",
        f"crop={w}:{h}:(in_w-out_w)*{ex}:(in_h-out_h)*0.5",
        f"fps={FPS}",
        f"eq=saturation={canal['saturacao']}:contrast={canal['contraste']}",
    ]
    if canal["vinheta"]:
        filtros.append("vignette=PI/5")
    filtros.append("format=yuv420p")
    rodar(["ffmpeg", "-y", "-stream_loop", "-1", "-ss", f"{ss:.2f}", "-i", str(clipe_orig), "-an",
           "-vf", ",".join(filtros), "-frames:v", str(quadros), "-c:v", "libx264", "-preset", "veryfast",
           "-crf", "16", "-r", str(FPS), str(destino)])


def escolher_musica(canal, pasta):
    """Trilha de fundo: reaproveita a ja sorteada neste projeto ou sorteia uma da pasta do canal."""
    registro = pasta / "musica.txt"
    if registro.exists():
        antiga = Path(registro.read_text(encoding="utf-8").strip())
        if antiga.exists():
            return str(antiga)
    alvo = canal.get("musica") or ""
    base = canal["_pasta"]
    if alvo:
        origem = Path(alvo) if Path(alvo).is_absolute() else base / alvo
    else:
        origem = base / "musicas"
    candidatas = []
    if origem.is_file():
        candidatas = [origem]
    elif origem.is_dir():
        candidatas = sorted(p for p in origem.iterdir() if p.suffix.lower() in EXT_AUDIO)
    elif alvo:
        info(f"   musica nao encontrada ({origem}); seguindo sem musica.")
    if not candidatas:
        return ""
    if len(candidatas) > 1:   # evita repetir a mesma trilha do video anterior
        outros = [p for p in pasta.parent.glob("*/musica.txt") if p.parent != pasta]
        if outros:
            ultimo = Path(max(outros, key=lambda p: p.stat().st_mtime).read_text(encoding="utf-8").strip())
            restantes = [c for c in candidatas if c.resolve() != ultimo.resolve()]
            candidatas = restantes or candidatas
    escolhida = random.choice(candidatas)
    registro.write_text(str(escolhida.resolve()), encoding="utf-8")
    info(f"   musica de fundo: {escolhida.name}")
    return str(escolhida)


def montar_formato(nome, w, h, roteiro, imagens, duracoes, narracao, musica, pasta, titulo_arq, canal):
    saida = pasta / "saida"
    saida.mkdir(exist_ok=True)
    destino = saida / f"{titulo_arq}_{nome}.mp4"
    parcial = saida / f"{titulo_arq}_{nome}.parcial.mp4"   # so vira o arquivo final se terminar sem erro
    if destino.exists():
        info(f"   [{nome}] ja existe, pulando.")
        return destino
    if parcial.exists():
        parcial.unlink()
    total = sum(duracoes)
    eh_video = [Path(p).suffix.lower() in EXT_VIDEO for p in imagens]
    planos = planejar_planos(duracoes, canal, eh_video)
    usado = {}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        lista = []
        for g, (cena, quadros) in enumerate(planos):
            clipe = tmp / f"clipe_{g:03d}.mp4"
            if g % 5 == 0:
                info(f"   [{nome}] plano {g+1}/{len(planos)}")
            if eh_video[cena]:
                renderizar_plano_video(imagens[cena], quadros, usado.get(cena, 0.0), g, w, h, canal, clipe)
                usado[cena] = usado.get(cena, 0.0) + quadros / FPS
            else:
                renderizar_plano(imagens[cena], quadros, g, w, h, canal, clipe)
            lista.append(f"file '{clipe.name}'")
        (tmp / "lista.txt").write_text("\n".join(lista), encoding="utf-8")
        (tmp / "legenda.ass").write_text(criar_ass(roteiro, duracoes, w, h, canal), encoding="utf-8")
        fim = f"{max(0, total - FADE):.2f}"
        video = f"[0:v]ass=legenda.ass,fade=t=in:st=0:d={FADE},fade=t=out:st={fim}:d={FADE}[v]"
        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "lista.txt", "-i", str(narracao.resolve())]
        if musica:
            cmd += ["-stream_loop", "-1", "-i", str(Path(musica).resolve())]
            audio = (f"[1:a]afade=t=in:st=0:d={FADE},afade=t=out:st={fim}:d={FADE}[n];"
                     f"[2:a]volume={float(canal['volume_musica'])},afade=t=in:st=0:d=1.5,afade=t=out:st={fim}:d={FADE}[m];"
                     f"[n][m]amix=inputs=2:duration=first:dropout_transition=0,volume=2,alimiter=limit=0.95[a]")
        else:
            audio = f"[1:a]afade=t=in:st=0:d={FADE},afade=t=out:st={fim}:d={FADE}[a]"
        cmd += ["-filter_complex", f"{video};{audio}", "-map", "[v]", "-map", "[a]",
                "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-c:a", "aac", "-b:a", "192k",
                "-t", f"{total:.2f}", "-movflags", "+faststart", str(parcial.resolve())]
        rodar(cmd, cwd=tmp)
    parcial.replace(destino)
    info(f"   pronto: {destino}")
    return destino



def _identidade_canal(canal):
    identidade = canal.get("identidade") if isinstance(canal.get("identidade"), dict) else {}
    pasta = Path(canal.get("_pasta", RAIZ))
    logo_rel = str(identidade.get("logo_arquivo") or "identidade/logo.png")
    logo = Path(logo_rel)
    if not logo.is_absolute():
        logo = pasta / logo
    return identidade, logo


def aplicar_branding_video(video_path, canal, formato="16x9"):
    """Aplica intro opcional e marca d'agua da marca do canal sem alterar o original ate concluir."""
    video_path = Path(video_path)
    identidade, logo = _identidade_canal(canal)
    marca = identidade.get("marca_dagua") if isinstance(identidade.get("marca_dagua"), dict) else {}
    intro_cfg = identidade.get("intro") if isinstance(identidade.get("intro"), dict) else {}
    watermark = bool(marca.get("ativa", False)) and logo.is_file()
    intro_file = Path(str(intro_cfg.get("arquivo") or "")) if intro_cfg.get("arquivo") else None
    if intro_file and not intro_file.is_absolute():
        intro_file = Path(canal.get("_pasta", RAIZ)) / intro_file
    use_intro = bool(intro_cfg.get("ativa", False)) and intro_file and intro_file.is_file()
    if bool(marca.get("ativa", False)) and not logo.is_file():
        info(f"   identidade: logo nao encontrada ({logo}); marca d'agua ignorada.")
    if bool(intro_cfg.get("ativa", False)) and not use_intro:
        info(f"   identidade: intro ativada, mas arquivo nao encontrado ({intro_file}); intro ignorada.")
    if not watermark and not use_intro:
        return video_path
    width, height = FORMATOS.get(formato, FORMATOS["16x9"])
    opacity = min(1.0, max(0.05, float(marca.get("opacidade", 0.22))))
    pct = min(0.25, max(0.04, float(marca.get("largura_percentual", 10)) / 100.0))
    pos = str(marca.get("posicao", "inferior_direita"))
    margin = max(18, int(min(width, height) * 0.025))
    logo_w = max(64, int(width * pct))
    if pos == "inferior_esquerda": x, y = str(margin), f"H-h-{margin}"
    elif pos == "superior_direita": x, y = f"W-w-{margin}", str(margin)
    elif pos == "superior_esquerda": x, y = str(margin), str(margin)
    else: x, y = f"W-w-{margin}", f"H-h-{margin}"
    tmp = video_path.with_name(video_path.stem + ".branding.tmp.mp4")
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    if use_intro:
        cmd += ["-i", str(intro_file), "-i", str(video_path)]
        logo_idx = 2
    else:
        cmd += ["-i", str(video_path)]
        logo_idx = 1
    if watermark:
        cmd += ["-i", str(logo)]
    if use_intro:
        filters = [
            f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},fps=30,setsar=1,format=yuv420p,setpts=PTS-STARTPTS[intro]",
            f"[1:v]scale={width}:{height},fps=30,setsar=1,format=yuv420p,setpts=PTS-STARTPTS[main]",
            "[intro][main]concat=n=2:v=1:a=0[base]",
        ]
        base_label = "base"
        # Preserva a narracao principal e a inicia somente depois da vinheta.
        has_audio = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", str(video_path)], capture_output=True, text=True).stdout.strip()
        if has_audio:
            intro_duration = max(0, int(round(duracao_arquivo(intro_file) * 1000)))
            filters.append(f"[1:a]adelay={intro_duration}|{intro_duration}[audio]")
    else:
        filters = ["[0:v]null[base]"]
        base_label = "base"
        has_audio = True
    if watermark:
        filters.append(f"[{logo_idx}:v]scale={logo_w}:-1,format=rgba,colorchannelmixer=aa={opacity:.3f}[wm]")
        filters.append(f"[{base_label}][wm]overlay=x={x}:y={y}:eof_action=repeat[vout]")
        video_label = "vout"
    else:
        video_label = "base"
    cmd += ["-filter_complex", ";".join(filters), "-map", f"[{video_label}]"]
    if use_intro and has_audio:
        cmd += ["-map", "[audio]"]
    else:
        cmd += ["-map", "1:a?" if use_intro else "0:a?"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(tmp)]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        tmp.unlink(missing_ok=True)
        raise RuntimeError("Falha ao aplicar identidade do canal: " + (result.stderr or "")[-700:])
    tmp.replace(video_path)
    info("   identidade do canal aplicada: " + ("intro e " if use_intro else "") + ("marca d'agua" if watermark else "intro"))
    return video_path


def aplicar_logo_miniatura(image_path, canal):
    identidade, logo = _identidade_canal(canal)
    thumb = identidade.get("thumbnail") if isinstance(identidade.get("thumbnail"), dict) else {}
    if not thumb.get("incluir_logo", True) or not logo.is_file():
        return image_path
    width = int(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width", "-of", "csv=p=0", str(image_path)], capture_output=True, text=True).stdout.strip() or 1280)
    logo_w = max(80, int(width * min(0.22, max(0.06, float(thumb.get("largura_percentual", 10))/100))))
    margin = max(18, int(width * 0.025))
    tmp = Path(image_path).with_name(Path(image_path).stem + ".logo.tmp.jpg")
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(image_path), "-i", str(logo), "-filter_complex",
           f"[1:v]scale={logo_w}:-1[logo];[0:v][logo]overlay=W-w-{margin}:H-h-{margin}[v]", "-map", "[v]", "-frames:v", "1", "-q:v", "2", str(tmp)]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode == 0 and tmp.exists():
        tmp.replace(image_path)
    else:
        tmp.unlink(missing_ok=True)
        info("   identidade: nao foi possivel aplicar logo na miniatura; arquivo original preservado.")
    return image_path

def salvar_publicacao(roteiro, pasta):
    tags = ", ".join(roteiro.get("tags", []))
    alt = roteiro.get("titulos_alternativos") or []
    alt_txt = ("TITULOS ALTERNATIVOS (teste A/B):\n" + "\n".join(f"- {t}" for t in alt) + "\n\n") if alt else ""
    texto = (f"TITULO:\n{roteiro['titulo']}\n\n{alt_txt}DESCRICAO:\n{roteiro['descricao']}\n\n"
             f"TAGS:\n{tags}\n\nMINIATURA: miniatura.jpg\n\n"
             "ANTES DE PUBLICAR: assista ao video inteiro, confira os fatos, os direitos das imagens/musica "
             "e, se houver conteudo sintetico realista, marque o rotulo de IA no YouTube.\n")
    reg = pasta / "musica.txt"
    if reg.exists():
        nome = Path(reg.read_text(encoding="utf-8").strip()).name
        texto += (f"\nMUSICA DE FUNDO: {nome}\n(confira a licenca da faixa; se ela exigir atribuicao, "
                  "cole o texto exigido na descricao do video)\n")
    (pasta / "publicacao.txt").write_text(texto, encoding="utf-8")


# ------------------------------------------------------- ideias e lote de videos

def texto_via_fallback(prompt, cfg, temperatura=1.0):
    """Tenta provedores compativeis com OpenAI, em ordem. Retorna (texto, nome)."""
    import urllib.request
    falhas = []
    for p in cfg.get("fallback_texto", []):
        chave = (p.get("api_key") or "").strip()
        if not chave or chave.startswith("SUA_"):
            continue
        try:
            corpo = json.dumps({
                "model": p["modelo"],
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperatura,
                "response_format": {"type": "json_object"},
            }).encode("utf-8")
            req = urllib.request.Request(p["url"], data=corpo, headers={
                "Authorization": f"Bearer {chave}",
                "Content-Type": "application/json",
            })
            with urllib.request.urlopen(req, timeout=60) as r:
                dados = json.loads(r.read().decode("utf-8"))
            texto = dados["choices"][0]["message"]["content"]
            if texto and texto.strip():
                return texto, p.get("nome", p["url"])
        except Exception as e:  # noqa
            falhas.append(f"{p.get('nome')}: {str(e)[:120]}")
    raise RuntimeError("todos os provedores falharam: " + " | ".join(falhas))


def _parse_ideias(texto):
    texto = re.sub(r"^```(?:json)?|```$", "", (texto or "").strip(), flags=re.M).strip()
    return [str(x).strip() for x in json.loads(texto).get("ideias", []) if str(x).strip()]


def sugerir_ideias(canal, nome_canal, n, cfg, categoria=None, motor="classico"):
    """Pede ao Gemini temas respeitando a categoria editorial e o motor visual."""
    ant = "\n".join(f"- {t}" for t in titulos_anteriores(nome_canal, RAIZ)) or "(nenhum ainda)"
    categoria_nome = (categoria or {}).get("name", "Curiosidades")
    categoria_id = (categoria or {}).get("id", "curiosidades")
    categoria_profile = (categoria or {}).get("editorial_profile") or get_category(categoria_id).get("editorial_profile", {})
    categoria_detail = "\n".join([
        f"Objetivo: {categoria_profile.get('objective','')}",
        f"Tom: {categoria_profile.get('tone','')}",
        f"Estrutura: {'; '.join(categoria_profile.get('structure', []))}",
        f"Regra factual: {categoria_profile.get('fact_policy','')}",
        f"Evitar: {categoria_profile.get('avoid','')}",
    ])
    if categoria_id in ("noticias", "economia", "politica_institucional", "documentario"):
        regras_categoria = "- Priorize fatos consolidados, conceitos, mecanismos e acontecimentos históricos bem documentados.\n- Nao exija Google Search nem suponha acesso a fontes ao vivo. Nao apresente como atuais aliquotas, leis, calendarios, cargos, resultados ou desdobramentos que possam ter mudado; prefira explicar o funcionamento geral e sinalize que dados atuais exigem conferencia manual.\n- Em politica institucional, explique regras e funcionamento com neutralidade, sem propaganda partidaria.\n- Em economia, nao de recomendacoes financeiras; explique conceitos e impactos sem inventar numeros."
    elif categoria_id in ("engenharia", "tecnologia", "como_funciona"):
        regras_categoria = "- Priorize mecanismos, etapas, componentes, comparações e explicações de funcionamento.\n- Os temas devem permitir demonstração visual concreta, não apenas definições abstratas."
    elif categoria_id in ("what_if", "humor"):
        regras_categoria = "- Priorize hipóteses interessantes, consequências progressivas, conflito e viradas narrativas.\n- Diferencie claramente ciência conhecida de especulação hipotética."
    elif categoria_id == "esportes":
        regras_categoria = "- Priorize regras, táticas, recordes, histórias e fatos esportivos verificáveis.\n- Evite alegações não comprovadas sobre atletas."
    else:
        regras_categoria = "- Priorize fatos verificáveis, ângulos pouco conhecidos e perguntas específicas.\n- Evite sensacionalismo falso, discurso de ódio e conselhos de saúde, direito ou finanças."
    regras_motor = ""
    if motor == "broadcast_news":
        regras_motor = "\nMOTOR BROADCAST NEWS (SEM GOOGLE SEARCH): sugira assuntos explicaveis com conhecimento consolidado, mecanismos estaveis, fatos historicos bem documentados ou conceitos estabelecidos. Nao dependa de manchetes do dia, cotacoes, aliquotas vigentes, resultados recentes ou cargos atuais. Nao exija token, cota ou ferramenta de Google Search. Se o tema tiver algum detalhe que possa mudar, formule o tema para explicar o conceito geral e indique conferencia manual antes da publicacao."
    prompt = f"""Você é estrategista de conteúdo de um canal de YouTube sem apresentador, focado em curiosidade, clareza e engajamento.
CANAL: {canal.get('nome', '')}
NICHO: {canal.get('nicho', '')}
CATEGORIA EDITORIAL: {categoria_nome}
MOTOR VISUAL: {motor}
DIRETRIZES ESPECIFICAS DA CATEGORIA:
{categoria_detail}{regras_motor}
PÚBLICO: {canal.get('publico', '')}
TOM: {canal.get('tom', '')}
IDIOMA: {canal['idioma']}

Sugira {n} temas de vídeo para este canal, exclusivamente dentro da categoria editorial selecionada.
Cada tema deve ser escrito como um TÍTULO que desperta curiosidade ou gera debate: uma pergunta ("Por que...?", "O que realmente aconteceu com...?") ou uma promessa de revelação, curto e específico, pronto para virar título.
Critérios:
- Específicos e concretos (nada de temas genéricos como "história do Egito").
- O vídeo precisa conseguir cumprir a promessa do título com fatos verificáveis. Não prometa o que o vídeo não pode entregar.
- {regras_categoria}
- Varie os ângulos e evite repetir a mesma estrutura de título.
- Diferentes dos vídeos que o canal já fez:
{ant}

Responda SOMENTE com JSON válido neste formato: {{"ideias": ["tema 1", "tema 2"]}}"""
    erro_gemini = "sem chave"
    if cfg.get("gemini_api_key"):
        try:
            from google import genai
            from google.genai import types
            cliente = genai.Client(api_key=cfg["gemini_api_key"],
                                   http_options=types.HttpOptions(timeout=60000))
            resp = gerar_conteudo_texto_com_fallback(
                cliente, cfg, prompt,
                types.GenerateContentConfig(response_mime_type="application/json", temperature=1.0),
                operacao="sugestoes de temas",
            )
            ideias = _parse_ideias(resp.text)
            if ideias:
                return ideias
            erro_gemini = "resposta vazia"
        except Exception as e:  # noqa
            erro_gemini = str(e)[:150]
    info(f"   Gemini indisponivel ({erro_gemini}); tentando outros provedores...")
    try:
        texto, provedor = texto_via_fallback(prompt, cfg)
        ideias = _parse_ideias(texto)
        info(f"   ideias geradas via {provedor}")
        return ideias
    except Exception as e:  # noqa
        erro(f"nao consegui gerar ideias: Gemini ({erro_gemini}) / fallback ({str(e)[:300]})")



def gerar_ideias(canal, nome_canal, n, cfg):
    info("   pedindo ideias ao Gemini...")
    ideias = sugerir_ideias(canal, nome_canal, n, cfg)
    arq = canal["_pasta"] / "temas.txt"
    novo = f"\n# ideias geradas em {date.today().isoformat()} (apague as que nao quiser; linhas com # sao ignoradas)\n"
    novo += "\n".join(ideias) + "\n"
    with open(arq, "a", encoding="utf-8") as f:
        f.write(novo)
    info(f"\n{len(ideias)} ideias salvas em {arq}:\n")
    for i in ideias:
        info(f"  - {i}")
    info(f"\nRevise o arquivo e depois crie os videos com:\n  python criar_video.py {nome_canal} --lote canais\\{nome_canal}\\temas.txt")


def piloto_automatico(a, canal, cfg):
    """Busca N ideias e ja cria um video para cada, sem parar no meio."""
    info(f"\nPILOTO AUTOMATICO: buscando {a.auto} ideias e criando os videos...")
    cat = get_category(a.categoria) if getattr(a, "categoria", None) else None
    motor = getattr(a, "motor", None) or "classico"
    ideias = sugerir_ideias(canal, a.canal, a.auto, cfg, categoria=cat, motor=motor)


def rodar_lote(a, canal):
    arq = Path(a.lote)
    if not arq.exists():
        arq = RAIZ / a.lote
    if not arq.exists():
        erro(f"arquivo de temas nao encontrado: {a.lote}")
    linhas = arq.read_text(encoding="utf-8").splitlines()
    pendentes = [(i, l.strip()) for i, l in enumerate(linhas) if l.strip() and not l.strip().startswith("#")]
    if not pendentes:
        erro("nao ha temas pendentes no arquivo (linhas com # sao ignoradas).")
    extra = ["--formatos", a.formatos, "--categoria", a.categoria]
    if a.duracao:
        extra += ["--duracao", str(a.duracao)]
    if a.simular:
        extra.append("--simular")
    if a.revisar:
        extra.append("--revisar")
    ok, falhas = [], []
    for n, (i, tema) in enumerate(pendentes, 1):
        info(f"\n=========== VIDEO {n}/{len(pendentes)}: {tema} ===========")
        r = subprocess.run([sys.executable, str(Path(__file__).resolve()), a.canal, tema] + extra)
        if r.returncode == 0:
            ok.append(tema)
            if not a.revisar:
                linhas[i] = "# FEITO: " + tema
                arq.write_text("\n".join(linhas) + "\n", encoding="utf-8")
        else:
            falhas.append(tema)
    info(f"\n=========== RESUMO DO LOTE ===========\nconcluidos: {len(ok)}   com problema: {len(falhas)}")
    for t in falhas:
        info(f"  falhou: {t}")
    if falhas:
        info("Rode o mesmo comando de novo para tentar apenas os temas pendentes.")


# ---------------------------------------------------------------------- main

def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa
        pass
    ap = argparse.ArgumentParser(description="Cria um video completo a partir de um tema.")
    ap.add_argument("canal", help="nome da pasta do canal dentro de 'canais'")
    ap.add_argument("tema", nargs="?", default="", help="tema do video (entre aspas)")
    ap.add_argument("--duracao", type=int, help="duracao alvo da narracao em segundos")
    ap.add_argument("--categoria", default="curiosidades", help="categoria editorial selecionada")
    ap.add_argument("--entrega-format", choices=["16x9", "9x16"], help="formato desta entrega independente")
    ap.add_argument("--roteiro", help="usar um roteiro JSON pronto")
    ap.add_argument("--projeto", help="retomar um projeto existente dentro de projetos/<canal>/")
    ap.add_argument("--so-prompt", action="store_true", help="so gera o pedido para colar no My Hub")
    ap.add_argument("--revisar", action="store_true", help="parar apos o roteiro")
    ap.add_argument("--simular", action="store_true", help="teste sem internet (vozes e imagens falsas)")
    ap.add_argument("--formatos", default="16x9,9x16")
    ap.add_argument("--ideias", type=int, help="pede N ideias de temas ao Gemini e salva em canais/<canal>/temas.txt")
    ap.add_argument("--auto", type=int, help="piloto automatico: busca N ideias e cria um video para cada")
    ap.add_argument("--lote", help="arquivo de texto com um tema por linha; cria um video para cada")
    a = ap.parse_args()

    for prog in ("ffmpeg", "ffprobe"):
        if shutil.which(prog) is None:
            erro(f"'{prog}' nao foi encontrado. Instale o FFmpeg e abra um novo terminal.")

    global PAUSA_CENA, PAUSA_GANCHO
    cfg = carregar_config()
    canal = carregar_canal(a.canal)
    PAUSA_CENA = float(canal["pausa_entre_cenas"])
    PAUSA_GANCHO = float(canal["pausa_gancho"])
    duracao = a.duracao or int(canal["duracao_alvo_segundos"])
    formatos = [f.strip() for f in a.formatos.split(",") if f.strip() in FORMATOS]
    if not formatos:
        erro("--formatos deve ser 16x9, 9x16 ou os dois separados por virgula.")

    usar_video = bool(canal["usar_video_stock"]) and (a.simular or bool(cfg["pixabay_api_key"]))
    canal["_usa_video"] = usar_video

    if a.ideias:
        gerar_ideias(canal, a.canal, a.ideias, cfg)
        return
    if a.auto:
        piloto_automatico(a, canal, cfg)
        return
    if a.lote:
        rodar_lote(a, canal)
        return

    # pasta do projeto: pode ser nova ou uma pasta explicita para retomada.
    if a.roteiro:
        base_nome = ler_json(a.roteiro).get("titulo", a.tema or "video")
    else:
        if not a.tema:
            erro('informe o tema entre aspas. Exemplo: python criar_video.py exemplo "Tema do video"')
        base_nome = a.tema
    if a.projeto:
        pasta = Path(a.projeto).expanduser()
        if not pasta.is_absolute():
            pasta = RAIZ / pasta
        pasta = pasta.resolve()
        raiz_canal = (RAIZ / "projetos" / a.canal).resolve()
        if pasta.parent != raiz_canal or not pasta.is_dir():
            erro("--projeto deve apontar para uma pasta existente diretamente dentro de projetos/<canal>/.")
    else:
        sufixo = f"_{a.entrega_format}" if a.entrega_format else ""
        pasta = RAIZ / "projetos" / a.canal / f"{date.today().isoformat()}_{slug(base_nome)}{sufixo}"

    if a.so_prompt:
        pasta.mkdir(parents=True, exist_ok=True)
        prompt = montar_prompt_roteiro(canal, a.tema or base_nome, duracao, titulos_anteriores(a.canal, pasta), a.categoria)
        (pasta / "prompt_roteiro.txt").write_text(prompt, encoding="utf-8")
        print(prompt)
        info(f"\n(Salvo em {pasta / 'prompt_roteiro.txt'}.)\nCole no Claude do My Hub, salve a resposta "
             f"como roteiro.json e rode:\n  python criar_video.py {a.canal} --roteiro roteiro.json")
        return

    pasta.mkdir(parents=True, exist_ok=True)
    info(f"\nProjeto: {pasta}")

    # 1. roteiro
    arq_roteiro = pasta / "roteiro.json"
    info("\n[1/5] Roteiro")
    if a.roteiro and not arq_roteiro.exists():
        shutil.copy(a.roteiro, arq_roteiro)
    if not arq_roteiro.exists():
        if a.simular:
            falso = {"titulo": f"Teste: {a.tema}", "descricao": "Descricao de teste.", "tags": ["teste"],
                     "gancho_texto": "Ninguem explica isso", "texto_miniatura": "O segredo",
                     "prompt_miniatura": "", "cenas": [
                         {"narracao": f"Esta e a primeira cena do video de teste sobre {a.tema}. Ela serve para checar a legenda.",
                          "imagem": "x", "busca_stock": "x"},
                         {"narracao": "Aqui vem a segunda cena, um pouco mais longa, para ver como as legendas quebram em trechos curtos e acompanham a fala.",
                          "visual": "video", "imagem": "x", "busca_stock": "x"},
                         {"narracao": "E esta e a cena final. Fim do teste.", "imagem": "x", "busca_stock": "x"}]}
            salvar_json(arq_roteiro, falso)
        else:
            roteiro = gerar_roteiro_gemini(canal, a.tema, duracao, titulos_anteriores(a.canal, pasta), cfg, a.categoria)
            salvar_json(arq_roteiro, validar_roteiro(roteiro))
    else:
        info("   roteiro.json ja existe, usando.")
    roteiro = validar_roteiro(ler_json(arq_roteiro))
    roteiro = ensure_closing_question(roteiro, a.categoria, a.tema, canal.get("tom", ""))
    salvar_json(arq_roteiro, roteiro)
    info(f"   titulo: {roteiro['titulo']} ({len(roteiro['cenas'])} cenas)")
    if a.revisar:
        info(f"\nRevise e edite {arq_roteiro}. Depois rode o mesmo comando (sem --revisar) para continuar.")
        return

    if not a.simular and not FontesDeImagem(cfg, canal["estilo_visual"]).tem_alguma():
        erro("nenhuma fonte de imagens configurada. No config.json, preencha pelo menos uma: "
             "'pixabay_api_key' (banco de fotos gratuito) ou 'cloudflare_account_id' + 'cloudflare_api_token' "
             "(imagens por IA gratuitas). O roteiro ja foi salvo; depois rode o mesmo comando.")

    # 2. voz
    info("\n[2/5] Voz")
    narracao, duracoes = gerar_voz(roteiro, pasta, canal, a.simular)

    # 3. imagens
    info("\n[3/5] Imagens")
    imagens = gerar_imagens(roteiro, pasta, cfg, a.simular, canal["estilo_visual"], usar_video)
    gerar_miniatura(roteiro, pasta, cfg, canal, a.simular, imagens, formatos[0])

    # 4. e 5. legendas + montagem
    info("\n[4/5] Legendas e montagem")
    musica = escolher_musica(canal, pasta)
    titulo_arq = slug(roteiro["titulo"])
    for nome in formatos:
        w, h = FORMATOS[nome]
        video_final = montar_formato(nome, w, h, roteiro, imagens, duracoes, narracao, musica, pasta, titulo_arq, canal)
        aplicar_branding_video(video_final, canal, nome)

    info("\n[5/5] Publicacao")
    salvar_publicacao(roteiro, pasta)
    info(f"\nPRONTO. Veja a pasta: {pasta}\\saida\n(Revise o video e o arquivo publicacao.txt antes de publicar.)")


if __name__ == "__main__":
    main()
