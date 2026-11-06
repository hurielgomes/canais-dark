"""
criar_animado.py - videos animados por estilo (whiteboard, telejornal): tema -> roteiro -> voz -> animacao -> mp4.

Uso:
    python criar_animado.py exemplo "Tema do video" --estilo whiteboard
    python criar_animado.py exemplo "Tema" --estilo telejornal --duracao 120 --formatos 16x9,9x16 --categoria economia

Opcoes:
    --estilo ESTILO    whiteboard (educativo) ou telejornal (economia, jornalistico)
    --categoria ID     categoria editorial (motores/categorias.json). Padrao: curiosidades
    --duracao N        duracao alvo da narracao em segundos
    --roteiro ARQ      usa um roteiro JSON pronto (ex.: escrito no My Hub; veja --so-prompt)
    --so-prompt        so gera o pedido para colar no My Hub e sai
    --revisar          para depois do roteiro, para voce ler/editar
    --simular          teste sem internet (roteiro e voz falsos)
    --formatos 16x9    gera so um formato (padrao: 16x9,9x16)
    --fps 24           quadros por segundo     --rapido  menos suavizacao (mais veloz)
"""
import argparse
import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))
import criar_video as cv  # noqa: E402

try:
    from editorial_rules import get_category, ensure_closing_question  # noqa: E402
except Exception:  # noqa
    get_category, ensure_closing_question = (lambda _c: {}), None

# o motor de estilos (pasta 'estudio'); aceita a pasta duplicada que o ZIP cria (estudio/estudio)
for cand in (RAIZ / "estudio", RAIZ):
    if (cand / "estudio" / "nucleo.py").exists():
        sys.path.insert(0, str(cand))
        break
try:
    from estudio.roteiro import FORMATOS, quadro_unico, renderizar_roteiro  # noqa: E402
except Exception as e:  # noqa
    cv.erro(f"nao encontrei o motor de estilos (pasta 'estudio'): {e}")

INFO_ESTILOS = {
    "whiteboard": {
        "nome": "Whiteboard Explainer (quadro branco, educativo)",
        "primeira": "titulo",
        "tipos": """- "titulo": {"titulo": "ate 10 palavras", "subtitulo": "opcional, ate 8 palavras"}
- "passos": {"titulo": "ate 6 palavras", "passos": ["2 a 4 passos curtos, ate 9 palavras cada"]}
- "lista": {"titulo": "ate 6 palavras", "itens": ["2 a 4 itens curtos, ate 9 palavras cada"]}
- "destaque": {"frase": "uma ideia central, ate 14 palavras"}""",
        "extra": "A cena 1 e sempre do tipo \"titulo\" e traz a pergunta de abertura. A ultima cena e do tipo \"destaque\" com a ideia final.",
    },
    "telejornal": {
        "nome": "Telejornal Animado (economia, documentario)",
        "primeira": "manchete",
        "tipos": """- "manchete": {"secao": "EDITORIA EM MAIUSCULAS, ex.: ECONOMIA", "assunto": "ate 5 palavras em maiusculas", "titulo": "ate 16 palavras", "subtitulo": "opcional, ate 14 palavras", "faixa": "opcional, manchete curta de ate 10 palavras"}
- "lista": {"secao": "...", "assunto": "...", "titulo": "PONTOS-CHAVE", "itens": ["3 a 4 itens, ate 12 palavras cada"]}
- "destaque": {"secao": "...", "assunto": "...", "titulo": "rotulo curto", "numero": "numero com unidade, ex.: 12,4%", "rotulo": "o que o numero mede", "nota": "fonte ou observacao"}""",
        "extra": ("A cena 1 e sempre do tipo \"manchete\" e traz a pergunta de abertura. "
                  "Use \"destaque\" SOMENTE com um numero que voce tenha certeza que e verdadeiro e verificavel; se nao tiver certeza, use \"manchete\" ou \"lista\". NUNCA invente estatisticas, valores ou datas."),
    },
}

TIPOS_PERMITIDOS = {"whiteboard": {"titulo", "passos", "lista", "destaque"},
                    "telejornal": {"manchete", "lista", "destaque"}}
CAMPOS_OBRIGATORIOS = {("whiteboard", "titulo"): ["titulo"], ("whiteboard", "passos"): ["titulo", "passos"],
                       ("whiteboard", "lista"): ["titulo", "itens"], ("whiteboard", "destaque"): ["frase"],
                       ("telejornal", "manchete"): ["titulo"], ("telejornal", "lista"): ["itens"],
                       ("telejornal", "destaque"): ["numero"]}


# --------------------------------------------------------------------- categoria
def perfil_categoria(categoria):
    try:
        return (get_category(categoria) or {}).get("editorial_profile", {}) or {}
    except Exception:  # noqa
        return {}


def bloco_categoria(categoria):
    p = perfil_categoria(categoria)
    if not p:
        return ""
    return "\n".join([
        "PERFIL EDITORIAL DA CATEGORIA:",
        f"OBJETIVO: {p.get('objective', '')}",
        f"TOM: {p.get('tone', '')}",
        "ESTRUTURA: " + "; ".join(p.get("structure", [])),
        f"REGRAS FACTUAIS: {p.get('fact_policy', '')}",
        f"EVITAR: {p.get('avoid', '')}",
    ])


# --------------------------------------------------------------------- roteiro
def montar_prompt(canal, tema, duracao, estilo, anteriores, categoria="curiosidades"):
    canal = cv.aplicar_modo_tema(canal, categoria) if hasattr(cv, "aplicar_modo_tema") else canal
    info = INFO_ESTILOS[estilo]
    n_cenas = max(4, round(duracao / 9))
    ant = "\n".join(f"- {t}" for t in anteriores) or "(nenhum ainda)"
    regras = "\n".join(f"- {r}" for r in canal.get("regras", []))
    fechamento = perfil_categoria(categoria).get(
        "closing_question", "Encerre com uma pergunta natural e específica para convidar comentários.")
    return f"""Você é roteirista de vídeos animados explicativos para um canal do YouTube sem apresentador, especialista em retenção de audiência.
Escreva o roteiro completo de UM vídeo, dividido em cenas. Cada cena tem a narração (voz) e o que aparece na tela.

CANAL: {canal.get('nome', '')}
NICHO: {canal.get('nicho', '')}
PÚBLICO: {canal.get('publico', '')}
TOM: {canal.get('tom', '')}
IDIOMA DA NARRAÇÃO: {canal['idioma']}

TEMA: {tema}
ESTILO VISUAL: {info['nome']}

{bloco_categoria(categoria)}

TAMANHO: cerca de {int(duracao * 2.5)} palavras de narração no total, em {n_cenas} cenas de 15 a 35 palavras cada.

TIPOS DE CENA DISPONÍVEIS (o programa posiciona tudo sozinho; escreva só o conteúdo):
{info['tipos']}
{info['extra']}

REGRAS DA NARRAÇÃO:
- A cena 1 é só o gancho: UMA frase curta (até 16 palavras), uma pergunta direta ou afirmação intrigante que NÃO conta a história. A explicação começa na cena 2 e responde à pergunta. Proibido: "Neste vídeo", "Você sabia", "Hoje vamos falar".
- Frases curtas e linguagem falada. Uma ideia nova por cena; a cada 2 ou 3 cenas, um mini-gancho que puxe para a próxima.
- Use apenas fatos verdadeiros e verificáveis. Se não tiver certeza de um dado, não o inclua. Explique com suas palavras, sem copiar textos de terceiros.
- A última cena retoma a pergunta do início, fecha com uma ideia marcante E termina com uma pergunta específica para estimular comentários.
- PERGUNTA FINAL ADEQUADA À CATEGORIA: {fechamento}
- Evite CTA genérico ("curta e inscreva-se").
- O texto da tela resume a narração (não é cópia dela). Sem emojis.
- Varie em relação aos vídeos anteriores do canal:
{ant}
{regras}

Responda SOMENTE com JSON válido, sem comentários e sem blocos de código, neste formato:
{{
  "titulo": "até 65 caracteres, desperta curiosidade e o vídeo cumpre o que promete",
  "titulos_alternativos": ["2 outros títulos para teste A/B"],
  "descricao": "descrição para o YouTube, 2 a 4 frases",
  "tags": ["8 a 12 palavras-chave"],
  "pergunta_final": "pergunta contextual para estimular comentários, coerente com categoria e tom",
  "cenas": [
    {{"tipo": "um dos tipos acima", "narracao": "texto exato que será falado", ...campos do tipo...}}
  ]
}}"""


def gerar_roteiro_gemini(canal, tema, duracao, estilo, anteriores, cfg, categoria="curiosidades"):
    if not cfg["gemini_api_key"]:
        cv.erro("falta a chave do Gemini no config.json ou no .env.")
    from google import genai
    from google.genai import types
    cliente = genai.Client(api_key=cfg["gemini_api_key"], http_options=types.HttpOptions(timeout=120000))
    prompt = montar_prompt(canal, tema, duracao, estilo, anteriores, categoria)
    gen_cfg = types.GenerateContentConfig(response_mime_type="application/json", temperature=0.9)
    cv.info("   pedindo o roteiro ao Gemini...")
    try:
        if hasattr(cv, "gerar_conteudo_texto_com_fallback"):
            resp = cv.gerar_conteudo_texto_com_fallback(cliente, cfg, prompt, gen_cfg, operacao="roteiro animado")
        else:
            resp = cv.com_retry(lambda: cliente.models.generate_content(
                model=cfg["modelo_texto"], contents=prompt, config=gen_cfg))
    except Exception as e:  # noqa
        msg = str(e)
        print(f"\nO Gemini recusou o pedido:\n{msg[:600]}\n")
        if "404" in msg or "NOT_FOUND" in msg or "no longer available" in msg:
            cv.erro(f"o modelo '{cfg.get('modelo_texto')}' nao esta disponivel para a sua chave. Ajuste 'modelo_texto' no config.json.")
        if "API key" in msg or "API_KEY" in msg or "401" in msg or "403" in msg or "PERMISSION" in msg:
            cv.erro("problema com a chave do Gemini. Confira o config.json/.env.")
        cv.erro("nao foi possivel gerar o roteiro (veja a mensagem acima).")
    texto = re.sub(r"^```(?:json)?|```$", "", (resp.text or "").strip(), flags=re.M).strip()
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        cv.erro("o Gemini nao devolveu um JSON valido. Rode o mesmo comando de novo.")


def garantir_pergunta_final(r, categoria, tema=""):
    """Aplica editorial_rules.ensure_closing_question e garante '?' na ultima narracao."""
    if ensure_closing_question:
        try:
            novo = ensure_closing_question(r, categoria, tema, "")
            if isinstance(novo, dict) and novo.get("cenas"):
                r = novo
        except Exception:  # noqa
            pass
    ultima = r["cenas"][-1]
    narr = str(ultima.get("narracao", "")).strip()
    if not narr.endswith("?"):
        pergunta = str(r.get("pergunta_final") or "").strip()
        if pergunta:
            if not pergunta.endswith("?"):
                pergunta += "?"
            ultima["narracao"] = f"{narr} {pergunta}".strip()
    return r


def validar(r, estilo, categoria="curiosidades"):
    if not isinstance(r, dict) or not r.get("cenas"):
        cv.erro("roteiro sem a lista 'cenas'.")
    permitidos = TIPOS_PERMITIDOS[estilo]
    for i, c in enumerate(r["cenas"], 1):
        if not isinstance(c, dict):
            cv.erro(f"cena {i} invalida.")
        if c.get("tipo") not in permitidos:
            cv.erro(f"cena {i}: tipo '{c.get('tipo')}' nao existe no estilo {estilo}. Tipos: {sorted(permitidos)}")
        if not str(c.get("narracao", "")).strip():
            cv.erro(f"cena {i} sem 'narracao'.")
        for campo in CAMPOS_OBRIGATORIOS[(estilo, c["tipo"])]:
            if not c.get(campo):
                cv.erro(f"cena {i} ({c['tipo']}) sem o campo '{campo}'.")
    r.setdefault("titulo", "video")
    r.setdefault("descricao", "")
    r.setdefault("tags", [])
    r.setdefault("titulos_alternativos", [])
    r.setdefault("pergunta_final", "")
    r["estilo"] = estilo
    r.setdefault("categoria", categoria)
    return garantir_pergunta_final(r, r["categoria"])


def roteiro_falso(estilo, tema):
    if estilo == "whiteboard":
        cenas = [
            {"tipo": "titulo", "titulo": f"Teste: {tema}?", "subtitulo": "um exemplo rápido", "narracao": "Como funciona isso, afinal?"},
            {"tipo": "passos", "titulo": "Em três passos", "passos": ["Primeiro passo da explicação", "Segundo passo, um pouco maior", "Terceiro e último passo"],
             "narracao": "Primeiro vem o início, depois o meio, e por fim o resultado final de tudo."},
            {"tipo": "destaque", "frase": "No fim, é mais simples do que parece", "narracao": "No fim, a resposta é mais simples do que parece."},
        ]
    else:
        cenas = [
            {"tipo": "manchete", "secao": "ECONOMIA", "assunto": "EXEMPLO DE TESTE", "titulo": f"Teste: {tema}?", "subtitulo": "um exemplo rápido", "faixa": "Manchete de exemplo", "narracao": "Por que isso acontece, afinal?"},
            {"tipo": "lista", "secao": "ECONOMIA", "assunto": "TRÊS MOTIVOS", "titulo": "PONTOS-CHAVE", "itens": ["Primeiro motivo do exemplo", "Segundo motivo do exemplo", "Terceiro motivo do exemplo"],
             "narracao": "São três motivos principais, e cada um pesa de um jeito diferente."},
            {"tipo": "destaque", "secao": "ECONOMIA", "assunto": "DADO FICTÍCIO", "titulo": "EXEMPLO", "numero": "12,4%", "rotulo": "VALOR DE TESTE", "nota": "Dado fictício para teste", "narracao": "E o número final mostra o tamanho desse efeito."},
        ]
    return {"titulo": f"Teste: {tema}", "titulos_alternativos": [], "descricao": "Descrição de teste.", "tags": ["teste"],
            "pergunta_final": "E você, já tinha percebido isso?", "cenas": cenas}


# ---------------------------------------------------------------------- legenda
def legendas_da_cena(narracao, dur, pausa, palavras=4):
    trechos = cv.dividir_em_trechos(narracao, palavras)
    util = max(0.8, dur - pausa - 0.1)
    total = sum(len(x) for x in trechos) or 1
    t, saida = 0.05, []
    for x in trechos:
        d = util * len(x) / total
        saida.append({"ini": round(t, 3), "fim": round(t + d, 3), "texto": x})
        t += d
    return saida


def misturar_audio(narracao, musica, volume, total, saida):
    fim = f"{max(0, total - 0.6):.2f}"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(narracao)]
    if musica:
        cmd += ["-stream_loop", "-1", "-i", str(musica)]
        filtro = (f"[0:a]afade=t=in:st=0:d=0.4,afade=t=out:st={fim}:d=0.6[n];"
                  f"[1:a]volume={volume},afade=t=in:st=0:d=1.5,afade=t=out:st={fim}:d=0.6[m];"
                  f"[n][m]amix=inputs=2:duration=first:dropout_transition=0,volume=2,alimiter=limit=0.95[a]")
    else:
        filtro = f"[0:a]afade=t=in:st=0:d=0.4,afade=t=out:st={fim}:d=0.6[a]"
    cmd += ["-filter_complex", filtro, "-map", "[a]", "-t", f"{total:.2f}", "-c:a", "aac", "-b:a", "192k", str(saida)]
    cv.rodar(cmd)


# ------------------------------------------------------------------------- main
def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa
        pass
    ap = argparse.ArgumentParser(description="Cria um video animado a partir de um tema.")
    ap.add_argument("canal")
    ap.add_argument("tema", nargs="?", default="")
    ap.add_argument("--estilo", default="whiteboard", choices=sorted(INFO_ESTILOS))
    ap.add_argument("--categoria", default="curiosidades")
    ap.add_argument("--duracao", type=int)
    ap.add_argument("--roteiro")
    ap.add_argument("--so-prompt", action="store_true")
    ap.add_argument("--revisar", action="store_true")
    ap.add_argument("--simular", action="store_true")
    ap.add_argument("--formatos", default="16x9,9x16")
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--rapido", action="store_true")
    a = ap.parse_args()

    for prog in ("ffmpeg", "ffprobe"):
        if shutil.which(prog) is None:
            cv.erro(f"'{prog}' nao foi encontrado. Instale o FFmpeg e abra um novo terminal.")
    cfg = cv.carregar_config()
    canal = cv.carregar_canal(a.canal)
    cv.PAUSA_CENA = float(canal["pausa_entre_cenas"])
    cv.PAUSA_GANCHO = float(canal["pausa_gancho"])
    duracao = a.duracao or int(canal["duracao_alvo_segundos"])
    formatos = [f.strip() for f in a.formatos.split(",") if f.strip() in FORMATOS]
    if not formatos:
        cv.erro("--formatos deve ser 16x9, 9x16 ou os dois separados por virgula.")

    if a.roteiro:
        base_nome = cv.ler_json(a.roteiro).get("titulo", a.tema or "video")
    else:
        if not a.tema:
            cv.erro('informe o tema entre aspas.')
        base_nome = a.tema
    sufixo = f"_{formatos[0]}" if len(formatos) == 1 else ""
    pasta = RAIZ / "projetos" / a.canal / f"{date.today().isoformat()}_{cv.slug(base_nome)}{sufixo}"
    pasta.mkdir(parents=True, exist_ok=True)

    if a.so_prompt:
        prompt = montar_prompt(canal, a.tema or base_nome, duracao, a.estilo,
                               cv.titulos_anteriores(a.canal, pasta), a.categoria)
        (pasta / "prompt_roteiro.txt").write_text(prompt, encoding="utf-8")
        print(prompt)
        cv.info(f"\n(Salvo em {pasta / 'prompt_roteiro.txt'}.)\nCole no Claude do My Hub, salve a resposta como roteiro.json e rode:\n"
                f"  python criar_animado.py {a.canal} --estilo {a.estilo} --categoria {a.categoria} --roteiro roteiro.json")
        return

    cv.info(f"\nProjeto: {pasta}")
    # 1. roteiro
    cv.info("\n[1/5] Roteiro")
    arq = pasta / "roteiro.json"
    if a.roteiro and not arq.exists():
        shutil.copy(a.roteiro, arq)
    if not arq.exists():
        if a.simular:
            r = roteiro_falso(a.estilo, a.tema)
        else:
            r = gerar_roteiro_gemini(canal, a.tema, duracao, a.estilo,
                                     cv.titulos_anteriores(a.canal, pasta), cfg, a.categoria)
        cv.salvar_json(arq, validar(r, a.estilo, a.categoria))
    else:
        cv.info("   roteiro.json ja existe, usando.")
    roteiro = validar(cv.ler_json(arq), a.estilo, a.categoria)
    cv.salvar_json(arq, roteiro)
    cv.info(f"   titulo: {roteiro['titulo']} ({len(roteiro['cenas'])} cenas)")
    if a.revisar:
        cv.info(f"\nRevise e edite {arq}. Depois rode o mesmo comando (sem --revisar) para continuar.")
        return

    # 2. voz
    cv.info("\n[2/5] Voz")
    narracao, duracoes = cv.gerar_voz(roteiro, pasta, canal, a.simular)
    total = sum(duracoes)

    # 3. cenas (duracao pela voz + legenda)
    cv.info("\n[3/5] Cenas")
    cenas = []
    for i, (c, d) in enumerate(zip(roteiro["cenas"], duracoes)):
        cc = {k: v for k, v in c.items() if v is not None}
        cc["duracao"] = round(d, 3)
        cc["legenda"] = legendas_da_cena(c["narracao"], d, cv.PAUSA_GANCHO if i == 0 else cv.PAUSA_CENA,
                                         int(canal["legenda_palavras"]))
        cenas.append(cc)
    identidade = canal.get("identidade") if isinstance(canal.get("identidade"), dict) else {}
    nome_canal = (identidade.get("nome_exibicao") or canal.get("nome") or "SEU CANAL").upper()[:16]
    render_roteiro = {"estilo": a.estilo, "canal": nome_canal, "cenas": cenas}

    # miniatura: um quadro da primeira cena
    miniatura = pasta / "miniatura.jpg"
    if not miniatura.exists():
        q = quadro_unico(render_roteiro, 0, min(2.4, cenas[0]["duracao"] * 0.8), "16x9", S=1).resize((1280, 720))
        q.convert("RGB").save(miniatura, quality=92)

    # 4. animacao e montagem
    cv.info("\n[4/5] Animacao e montagem")
    musica = cv.escolher_musica(canal, pasta)
    audio_final = pasta / "audio_final.m4a"
    if not audio_final.exists():
        misturar_audio(narracao, musica, float(canal["volume_musica"]), total, audio_final)
    saida = pasta / "saida"
    saida.mkdir(exist_ok=True)
    titulo_arq = cv.slug(roteiro["titulo"])
    for fmt in formatos:
        destino = saida / f"{titulo_arq}_{fmt}.mp4"
        if destino.exists():
            cv.info(f"   [{fmt}] ja existe, pulando.")
            continue
        parcial = saida / f"{titulo_arq}_{fmt}.parcial.mp4"
        if parcial.exists():
            parcial.unlink()
        ultimo = [-1]

        def cb(i, n, fmt=fmt, ultimo=ultimo):
            marco = int(i * 20 / max(1, n))
            if marco != ultimo[0]:
                ultimo[0] = marco
                cv.info(f"   [{fmt}] plano {marco + 1}/20")

        renderizar_roteiro(render_roteiro, str(parcial), fmt, a.fps, None, 1 if a.rapido else 2, str(audio_final), cb)
        parcial.replace(destino)
        cv.info(f"   pronto: {destino}")

    cv.info("\n[5/5] Publicacao")
    cv.salvar_publicacao(roteiro, pasta)
    cv.info(f"\nPRONTO. Veja a pasta: {pasta}\\saida\n(Revise o video e o arquivo publicacao.txt antes de publicar.)")


if __name__ == "__main__":
    main()
