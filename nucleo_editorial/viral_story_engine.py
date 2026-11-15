"""Ganchos, pontuação orientativa e otimização segura. NÃO prevê viralização."""
import json
import logging
import re
import unicodedata

_NUM = re.compile(r"\d[\d.,]*\d|\d")
_STOP = {"qual", "quais", "quando", "onde", "como", "porque", "para", "isso", "esse", "essa",
         "mais", "muito", "entre", "sobre", "desse", "dessa", "ainda", "pela", "pelo", "voce",
         "seria", "valer", "deve"}
_GENERICOS = ("ja conhecia", "o que mais te surpreendeu", "conta nos comentarios",
              "conta aqui nos comentarios", "voce sabia")
              
from .retention_planner import planejar_retencao, cta_contextual
from .resolver import obter_perfil


log = logging.getLogger(__name__)

PROIBIDOS = ("neste video", "neste vídeo", "voce sabia", "você sabia", "hoje vamos",
             "aposto que", "nao vai acreditar", "não vai acreditar")

# Detector de mini-gancho/virada, aplicado SÓ à última frase da cena.
GANCHO_RE = re.compile(r"\?\s*$|\b(mas|porém|até que|então|só que)\b", re.I)

FORMULAS = {
    "pergunta_causal": "Por que [fato estranho]?",
    "contradicao": "[Afirmação que contraria o senso comum].",
    "consequencia": "O que aconteceria se [premissa]?",
    "numero": "[Dado concreto] — e ninguém explica por quê.",
    "misterio": "Quem/Onde/Quando [elemento enigmático]?",
}
POR_PERFIL = {
    "didat": ("pergunta_causal", "consequencia", "contradicao"),
    "impacto": ("contradicao", "numero", "pergunta_causal"),
    "hist": ("misterio", "pergunta_causal", "contradicao"),
    "narrat": ("misterio", "pergunta_causal", "contradicao"),
    "notic": ("numero", "pergunta_causal"),
    "analit": ("pergunta_causal", "contradicao", "numero"),
    "humor": ("contradicao", "consequencia"),
    "especul": ("consequencia", "pergunta_causal"),
    "institu": ("pergunta_causal", "numero"),
}


def _formulas(perfil_id):
    for k, v in POR_PERFIL.items():
        if k in perfil_id:
            return v
    return ("pergunta_causal", "contradicao", "consequencia", "numero", "misterio")


def pontuar_gancho(texto):
    t = (texto or "").strip()
    n = len(t.split())
    s, notas = 40, []
    if 4 <= n <= 16: s += 20
    else: notas.append("tamanho fora de 4–16 palavras")
    if t.endswith("?") or re.search(r"\b(nunca|ninguém|apenas|mas|só)\b", t, re.I): s += 15
    else: notas.append("pouca tensão/dúvida")
    if re.search(r"\d|(?<=\s)[A-ZÁÉÍÓÚÂÊÔÃÕÇ]\w+", t): s += 10
    else: notas.append("pouco específico")
    if any(p in t.lower() for p in PROIBIDOS):
        s -= 30; notas.append("fórmula proibida")
    else: s += 15
    if not t.endswith("?") and re.search(r"\b(1\d{3}|20\d{2})\b", t):
        s -= 15; notas.append("parece entregar contexto/resposta")
    return {"texto": t, "score": max(0, min(100, s)), "notas": notas}


def selecionar_melhor(candidatos):
    pont = [pontuar_gancho(c if isinstance(c, str) else c.get("texto", "")) for c in candidatos[:5]]
    return (max(pont, key=lambda x: x["score"]), pont) if pont else (None, [])


def construir_plano(tema, n_cenas, duracao, fechamento_categoria, formato=None, resolucao=None):
    ret = planejar_retencao(n_cenas, duracao, formato, resolucao)
    return {
        "tema": tema,
        "formulas": _formulas(ret["perfil_id"]),
        "retencao": ret,
        "cta": cta_contextual(fechamento_categoria, ret["perfil_id"]),
    }


def _regra_marco(descricao):
    ponte = (" (OBRIGATÓRIO: termine a cena com uma PERGUNTA-PONTE: específica, nascida de um fato dito nesta cena, "
             "e que a PRÓXIMA cena responda com um dado concreto. Se não houver pergunta natural, termine com uma "
             "frase de virada que a próxima cena também entregue. Proibido pergunta retórica ou sem resposta.)")
    if descricao.startswith(("mini", "virada")):
        return ponte
    return ""


def _bloco_marcos(plano):
    return "\n".join(f"  - cena {c}: {d}{_regra_marco(d)}"
                     for c, d in plano["retencao"]["marcos"].items())


def bloco_prompt(plano):
    f = "\n".join(f"  - {k}: {FORMULAS[k]}" for k in plano["formulas"])
    m = _bloco_marcos(plano)
    return f"""PLANO DE RETENÇÃO (obrigatório, sem alterar fatos):
1. Antes de escrever, crie exatamente 5 ganchos candidatos para a cena 1, cada um com uma destas abordagens:
{f}
   Escolha o mais específico e curioso que NÃO revele a resposta. Ele vira a cena 1.
   Preencha "ganchos_candidatos" e "gancho_escolhido" exatamente como no formato JSON ao final deste prompt (sem campo "formula" e sem índice).
2. Progressão por cena:
{m}
3. CTA / pergunta final: {plano['cta']}
Nunca invente fatos para criar suspense: a tensão vem da ordem de revelação, não de exagero."""


def _ultima_frase(texto):
    frases = [f for f in re.split(r"(?<=[.!?])\s+", (texto or "").strip()) if f.strip()]
    return frases[-1] if frases else ""


def cenas_sem_gancho(cenas, plano):
    """Números (1-based) das cenas de mini-gancho/virada sem gancho na última frase."""
    marcos = [c for c, d in plano["retencao"]["marcos"].items()
              if d.startswith(("mini", "virada")) and c <= len(cenas)]
    faltam = [c for c in marcos if not GANCHO_RE.search(_ultima_frase(cenas[c - 1]))]
    return marcos, faltam


def avaliar_roteiro(roteiro, plano):
    cenas = [c["narracao"] for c in roteiro.get("cenas", [])]
    g = pontuar_gancho(cenas[0] if cenas else "")
    frases = [f for c in cenas for f in re.split(r"(?<=[.!?])\s+", c) if f.strip()]
    curtas = sum(len(f.split()) <= 14 for f in frases) / max(1, len(frases))
    marcos, faltam = cenas_sem_gancho(cenas, plano)
    cobertura = (len(marcos) - len(faltam)) / len(marcos) if marcos else 1.0
    final = bool(cenas) and cenas[-1].strip().endswith("?")
    score = round(0.35 * g["score"] + 0.25 * curtas * 100 + 0.25 * cobertura * 100 + 0.15 * (100 if final else 0))
    return {"score": score, "gancho": g, "frases_curtas": round(curtas, 2),
            "cobertura_mini_ganchos": round(cobertura, 2), "cenas_sem_gancho": faltam,
            "pergunta_final": final,
            "aviso": "Pontuação orientativa; não prevê viralização."}


def _ancoras(texto):
    nums = set(re.findall(r"\d[\d.,]*", texto))
    nomes = set(re.findall(r"(?<![.!?]\s)(?<!^)\b[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wáéíóúâêôãõç]+", texto))
    return nums | nomes


def fatos_preservados(antes, depois):
    return _ancoras(antes) <= _ancoras(depois) | set(depois.split())


def otimizar_roteiro(roteiro, plano, avaliacao, chamar_ia, ruins=()):
    """chamar_ia(prompt) -> texto JSON. Retorna (roteiro, aplicado)."""
    cenas = [c["narracao"] for c in roteiro["cenas"]]
    faltam = avaliacao.get("cenas_sem_gancho") or cenas_sem_gancho(cenas, plano)[1]
    prompt = f"""Reescreva SOMENTE o estilo da narração para melhorar a retenção.
PROIBIDO alterar, remover ou inventar fatos, nomes, números, datas. Mantenha exatamente {len(cenas)} cenas, na mesma ordem.
Problemas no gancho: {avaliacao['gancho']['notas']}.
Cenas SEM mini-gancho/virada (numeradas a partir de 1): {faltam}.
Cenas cuja pergunta final NÃO é respondida pela cena seguinte: {list(ruins)}.
Nas cenas sem gancho: acrescente no FIM uma pergunta-ponte curta (até 12 palavras) que a PRÓXIMA cena já responde, ou uma frase de virada que ela entrega.
Nas cenas com pergunta não respondida: troque a última frase por uma pergunta que a próxima cena realmente responda, ou por uma afirmação de virada.
Nunca use pergunta retórica nem sem resposta no vídeo. Só mexa na última frase dessas cenas.
Marcos do plano:
{_bloco_marcos(plano)}
A última cena deve terminar com UMA única pergunta que convide a opinar sobre um ponto do vídeo, sem repetir pergunta já respondida nele: {plano['cta']}
Responda só JSON: {{"narracoes": ["..."]}}
CENAS: {json.dumps(cenas, ensure_ascii=False)}"""
    try:
        novas = json.loads(re.sub(r"^```(?:json)?|```$", "", chamar_ia(prompt).strip(), flags=re.M))["narracoes"]
    except Exception as e:  # noqa
        log.warning("otimizar_roteiro: resposta inválida da IA (%s)", e)
        return roteiro, False
    if len(novas) != len(cenas):
        log.warning("otimizar_roteiro: número de cenas mudou (%d -> %d)", len(cenas), len(novas))
        return roteiro, False
    if not fatos_preservados(" ".join(cenas), " ".join(novas)):
        perdidas = _ancoras(" ".join(cenas)) - (_ancoras(" ".join(novas)) | set(" ".join(novas).split()))
        log.warning("otimizar_roteiro: fatos perdidos na reescrita: %s", sorted(perdidas))
        return roteiro, False
    novo = json.loads(json.dumps(roteiro))
    for c, n in zip(novo["cenas"], novas):
        c["narracao"] = n
    return novo, True

def perguntas_sem_resposta(cenas, chamar_ia):
    """Números (1-based) das cenas cuja pergunta final não é respondida pela cena seguinte."""
    pares = [{"cena": i + 1, "pergunta": _ultima_frase(c), "proxima_cena": cenas[i + 1]}
            for i, c in enumerate(cenas[:-1]) if i > 0 and _ultima_frase(c).endswith("?")]
    if not pares:
        return []
    prompt = f"""Para cada par, diga se "proxima_cena" RESPONDE de forma direta e concreta a "pergunta".
Pergunta retórica, vaga ou sem resposta no texto = false.
Responda só JSON: {{"resultado": [{{"cena": 1, "respondida": true}}]}}
PARES: {json.dumps(pares, ensure_ascii=False)}"""
    try:
        d = json.loads(re.sub(r"^```(?:json)?|```$", "", chamar_ia(prompt).strip(), flags=re.M))
        return [r["cena"] for r in d["resultado"] if not r.get("respondida")]
    except Exception as e:  # noqa
        log.warning("perguntas_sem_resposta: checagem falhou (%s)", e)
        return []

def planejar_narrativa(tema, resolucao, n_cenas, duracao, chamar_ia):
    pid = (resolucao or {}).get("perfil_id") or (resolucao or {}).get("perfil")
    perfil = obter_perfil(pid) if pid else {}
    estrutura = perfil.get("estrutura", [])
    plano = {"origem": "reserva", "estrutura": estrutura, "pergunta_central": tema,
             "conflito": "", "revelacoes": [], "pico": "", "recompensa": "", "final": "",
             "perguntas_ponte": []}
    prompt = f"""Planeje (sem escrever o roteiro) um vídeo de {duracao}s, {n_cenas} cenas, sobre: {tema}.
Perfil: {perfil.get('nome','livre')}. Tom: {perfil.get('tom','')}. Tensão: {perfil.get('tensao_curiosidade','')}.
Estrutura base: {estrutura}. Cuidados: {perfil.get('cuidados', [])}.
Use SOMENTE fatos de que tenha certeza. Se o tema tiver superlativo (maior, mais rápido...), defina o CRITÉRIO exato (altura, volume, largura...) e mantenha o mesmo em todo o vídeo, sem se contradizer.
Defina de 3 a 5 perguntas-ponte: cada uma com a resposta concreta que a cena seguinte vai dar (ex.: "quando foi a última erupção?" -> "em 2022, após 38 anos").
Responda só JSON:
{{"pergunta_central": "", "conflito": "conflito, mistério, descoberta ou problema", "revelacoes": ["em ordem de apresentação"], "pico": "momento de maior impacto", "recompensa": "o que o espectador ganha", "final": "como termina", "perguntas_ponte": [{{"pergunta": "", "resposta": ""}}]}}"""
    try:
        d = json.loads(re.sub(r"^```(?:json)?|```$", "", chamar_ia(prompt).strip(), flags=re.M))
        if d.get("pergunta_central") and d.get("revelacoes"):
            plano.update({k: d.get(k, plano[k]) for k in plano if k in d}, origem="ia")
            if not isinstance(plano["perguntas_ponte"], list):
                plano["perguntas_ponte"] = []
    except Exception as e:  # noqa
        log.warning("planejar_narrativa: usando plano de reserva (%s)", e)
    return plano


def bloco_narrativo(pn):
    if not pn:
        return ""
    rev = "\n".join(f"  {i}. {r}" for i, r in enumerate(pn["revelacoes"], 1)) or "  (siga a estrutura do perfil)"
    pp = "\n".join(f"  - {p.get('pergunta', '')} -> {p.get('resposta', '')}"
                   for p in pn.get("perguntas_ponte", []) if isinstance(p, dict)) or "  (crie perguntas que a cena seguinte responda)"
    return f"""PLANO NARRATIVO (o roteiro deve cumprir este plano):
- Pergunta central: {pn['pergunta_central']}
- Conflito/mistério: {pn['conflito']}
- Revelações, nesta ordem:
{rev}
- Pico: {pn['pico']}
- Recompensa: {pn['recompensa']}
- Final: {pn['final']}
- Perguntas-ponte (a pergunta termina uma cena e a resposta abre a seguinte):
{pp}
REGRA DO GANCHO: a cena 1 só pode prometer a pergunta central e a recompensa acima. Nunca prometa algo que o vídeo não responde.
REGRA DAS PERGUNTAS: toda pergunta no meio do vídeo precisa ser respondida na cena seguinte. A pergunta final deve convidar o espectador a opinar sobre um ponto apresentado no vídeo, sem repetir pergunta já respondida nele. Se o tema compara dois critérios de medição, diga numa cena que o recorde tradicional continua valendo no critério original. Nunca use opinião genérica ("teria coragem de...")."""


# ===== COLE em nucleo_editorial/viral_story_engine.py =====

def cenas_repetidas(cenas, limite=0.5):
    """Pares (i, j), numerados de 1, que repetem a mesma informação."""
    toks = [{w for w in re.findall(r"\w+", c.lower()) if len(w) > 4} for c in cenas]
    pares = []
    for i in range(len(cenas)):
        for j in range(i + 1, len(cenas)):
            comuns = toks[i] & toks[j]
            if len(comuns) >= 3 and len(comuns) / max(1, min(len(toks[i]), len(toks[j]))) >= limite:
                pares.append((i + 1, j + 1))
    return pares


def cenas_frases_longas(cenas, maximo=14):
    """Cenas (numeradas de 1) com alguma frase acima do limite (cena 1: 16 palavras)."""
    out = []
    for i, c in enumerate(cenas, 1):
        lim = 16 if i == 1 else maximo
        if any(len(f.split()) > lim for f in re.split(r"(?<=[.!?])\s+", c) if f.strip()):
            out.append(i)
    return out


def verificar_promessa(roteiro, plano_narr, chamar_ia):
    """Retorna {"cumprida": bool, "problemas": [str]}. Em caso de falha da IA, não bloqueia."""
    cenas = [c["narracao"] for c in roteiro["cenas"]]
    pn = plano_narr or {}
    prompt = f"""Você é revisor editorial e factual de roteiros. Analise o roteiro abaixo.
GANCHO (cena 1): {cenas[0]}
CONFLITO DO PLANO: {pn.get('conflito', '')}
FECHAMENTO DO PLANO: {pn.get('final', '')}
Verifique:
1. O gancho afirma ou pressupõe algo que o próprio vídeo desmente ou nunca esclarece (premissa falsa ou enganosa)?
2. O vídeo responde ao que o gancho promete?
3. Se o tema compara medidas (maior, mais alto, mais rápido), o critério exato aparece nas cenas e é mantido até o fim?
4. Há superlativo impreciso (ex.: "maior" sem dizer em que critério)?
Liste só problemas reais e objetivos. Se não houver, devolva lista vazia.
Responda só JSON: {{"cumprida": true ou false, "problemas": ["..."]}}
CENAS: {json.dumps(cenas, ensure_ascii=False)}"""
    try:
        r = json.loads(re.sub(r"^```(?:json)?|```$", "", chamar_ia(prompt).strip(), flags=re.M))
        problemas = [str(p) for p in r.get("problemas", []) if str(p).strip()]
        return {"cumprida": bool(r.get("cumprida", not problemas)) and not problemas,
                "problemas": problemas}
    except Exception as e:  # noqa
        log.warning("verificar_promessa: resposta inválida (%s)", e)
        return {"cumprida": True, "problemas": [], "erro": True}


def _reescrita_valida(cenas, novas):
    if len(novas) != len(cenas) or any(not str(n).strip() for n in novas):
        return False, "número de cenas mudou ou cena vazia"
    if len(novas[0].split()) > 16:
        return False, "gancho com mais de 16 palavras"
    if sum(len(n.split()) for n in novas) < 0.75 * sum(len(c.split()) for c in cenas):
        return False, "roteiro encolheu demais"
    if not fatos_preservados(" ".join(cenas), " ".join(novas)):
        perdidas = _ancoras(" ".join(cenas)) - (_ancoras(" ".join(novas)) | set(" ".join(novas).split()))
        return False, f"fatos perdidos: {sorted(perdidas)}"
    return True, ""


def limpar_roteiro(roteiro, plano, problemas, repetidas, longas, chamar_ia, plano_narr=None):
    """Passagem 1: repetição, frases inúteis, transições, frases longas e promessa do gancho."""
    cenas = [c["narracao"] for c in roteiro["cenas"]]
    baixa = plano["retencao"]["tensao"].startswith("baix")
    revelacoes = (plano_narr or {}).get("revelacoes", [])
    prompt = f"""Faça uma LIMPEZA editorial na narração. Mantenha exatamente {len(cenas)} cenas, na mesma ordem.
PROIBIDO inventar fatos, nomes, números ou datas. Você só pode usar fatos que já estão nas cenas ou nestas revelações do plano: {json.dumps(revelacoes, ensure_ascii=False)}
PROBLEMAS DETECTADOS (corrija todos):
- Promessa/coerência do gancho: {problemas}
- Cenas que repetem a mesma informação (pares, numerados de 1): {repetidas}
- Cenas com frase acima de 14 palavras (cena 1: 16): {longas}
O QUE FAZER:
1. Repetição: em cada par, mantenha a informação na cena onde ela é mais forte. Na outra, troque por um fato novo do plano ou por uma transição curta que avance a história.
2. Remova frases inúteis (enchimento, adjetivos vazios, exagero sem base, como "facilidade assustadora").
3. Corrija transições para que cada cena nasça da anterior.
4. Quebre frases longas em frases de 6 a 14 palavras.
5. Gancho (cena 1): se ele afirmar uma premissa que o vídeo desmente ou nunca esclarece, reescreva-o com até 16 palavras, SEM revelar a resposta e SEM premissa falsa. Se tem critério de medida (maior, mais alto), o critério deve estar dito até a cena 3 e valer até o fim.
6. Se uma afirmação usa superlativo, deixe o critério explícito na própria frase.
7. {'Perfil técnico: NÃO crie suspense nem pergunta retórica.' if baixa else 'Mantenha as perguntas-ponte cuja resposta está na cena seguinte.'}
8. A última cena termina com UMA pergunta específica sobre um fato que o vídeo apresentou: {plano['cta']}
Responda só JSON: {{"narracoes": ["..."]}}
CENAS: {json.dumps(cenas, ensure_ascii=False)}"""
    try:
        novas = json.loads(re.sub(r"^```(?:json)?|```$", "", chamar_ia(prompt).strip(), flags=re.M))["narracoes"]
    except Exception as e:  # noqa
        log.warning("limpar_roteiro: resposta inválida (%s)", e)
        return roteiro, False
    ok, motivo = _reescrita_valida(cenas, novas)
    if not ok:
        log.warning("limpar_roteiro: descartada (%s)", motivo)
        return roteiro, False
    novo = json.loads(json.dumps(roteiro))
    for c, n in zip(novo["cenas"], novas):
        c["narracao"] = n
    # mantém os campos derivados do gancho e da pergunta final em sincronia
    novo.setdefault("gancho_escolhido", {})["texto"] = novas[0]
    ult = re.findall(r"[^.!?]*\?", novas[-1])
    if ult:
        novo["pergunta_final"] = ult[-1].strip()
    return novo, True


def otimizar_roteiro_completo(roteiro, plano, avaliar, perguntas_ruins, chamar_ia, plano_narr=None):
    """
    Passagem 1: limpeza + promessa do gancho.  Passagem 2: mini-ganchos/perguntas (otimizar_roteiro).
    `avaliar(roteiro)` -> (avaliacao, ruins) recalcula nota e perguntas sem resposta.
    Retorna (roteiro, relatorio).
    """
    rel = {"aplicado": False, "passagem1": False, "passagem2": False}
    cenas = [c["narracao"] for c in roteiro["cenas"]]

    prom = verificar_promessa(roteiro, plano_narr, chamar_ia)
    repetidas = cenas_repetidas(cenas)
    longas = cenas_frases_longas(cenas)
    rel["diagnostico"] = {"promessa": prom, "repetidas": repetidas, "frases_longas": longas}

    if prom["problemas"] or repetidas or longas:
        roteiro, ok = limpar_roteiro(roteiro, plano, prom["problemas"], repetidas, longas,
                                     chamar_ia, plano_narr)
        rel["passagem1"] = ok
        if ok:
            rel["promessa_depois"] = verificar_promessa(roteiro, plano_narr, chamar_ia)

    aval, ruins = avaliar(roteiro)
    if aval.get("cenas_sem_gancho") or ruins:
        roteiro, ok = otimizar_roteiro(roteiro, plano, aval, chamar_ia, ruins)
        rel["passagem2"] = ok

    rel["aplicado"] = rel["passagem1"] or rel["passagem2"]
    return roteiro, rel


def _sem_acento(t):
    t = unicodedata.normalize("NFD", t.lower())
    return "".join(ch for ch in t if unicodedata.category(ch) != "Mn")


def _json_ia(txt):
    return json.loads(re.sub(r"^```(?:json)?|```$", "", txt.strip(), flags=re.M))


def _termos(frase):
    ps = re.findall(r"[a-z0-9]{4,}", _sem_acento(frase))
    return {p[:5] for p in ps if p not in _STOP}


def repeticoes_numericas(cenas, janela=2):
    """Mesmo número em cenas próximas (1-based). Ignora se a cena de origem termina em pergunta."""
    nums = [set(_NUM.findall(c)) for c in cenas]
    achados, vistos = [], set()
    for j in range(len(cenas)):
        for i in range(max(0, j - janela), j):
            if cenas[i].rstrip().endswith("?"):
                continue
            for n in sorted(nums[i] & nums[j]):
                if len(n) >= 3 and (j, n) not in vistos:
                    vistos.add((j, n))
                    achados.append({"cena": j + 1, "origem": i + 1, "numero": n})
    return achados


def pergunta_final_repetida(cenas, pergunta, limiar=0.5):
    alvo = _termos(pergunta)
    if not alvo:
        return False
    for c in cenas[:-1]:
        for q in re.findall(r"[^.!?]*\?", c):
            t = _termos(q)
            if t and len(alvo & t) / min(len(alvo), len(t)) >= limiar:
                return True
    return False


def _corrigir_cenas(roteiro, reps, sem, chamar_ia):
    cenas = [c["narracao"] for c in roteiro["cenas"]]
    tarefas, nums_rep = {}, {}
    for r in reps:
        nums_rep.setdefault(r["cena"], []).append(r["numero"])
        tarefas.setdefault(r["cena"], []).append(
            f"remova o número {r['numero']} (já dito na cena {r['origem']}); mantenha só a informação nova")
    for n in sem:
        if n >= len(cenas):
            continue
        prox = cenas[n]
        if prox.rstrip().endswith("?"):
            how = "termine com uma frase curta de virada (até 12 palavras), SEM pergunta, pois a próxima cena já é uma pergunta"
        else:
            how = "termine com uma pergunta-ponte curta (até 12 palavras) que a próxima cena responde"
        tarefas.setdefault(n, []).append(how)
    if not tarefas:
        return roteiro, False

    blocos = []
    for n in sorted(tarefas):
        prox = cenas[n] if n < len(cenas) else "(fim)"
        blocos.append(f'Cena {n}: "{cenas[n - 1]}"\n  Próxima cena: "{prox}"\n  Tarefas: ' + "; ".join(tarefas[n]))
    lista = "\n".join(blocos)
    prompt = f"""Reescreva SOMENTE as cenas listadas, mudando o mínimo possível.
PROIBIDO inventar ou remover fatos, nomes, números ou datas, exceto o que a tarefa manda remover. Frases de até 14 palavras.
{lista}
Responda só JSON: {{"cenas": [{{"cena": N, "narracao": "..."}}]}}"""
    try:
        novas = {int(x["cena"]): str(x["narracao"]).strip() for x in _json_ia(chamar_ia(prompt))["cenas"]}
    except Exception as e:  # noqa
        log.warning("refino: resposta inválida da IA (%s)", e)
        return roteiro, False

    atual, aplicado = list(cenas), False
    for n, txt in sorted(novas.items()):
        if n not in tarefas or not txt or len(txt.split()) > 40:
            continue
        if any(num in txt for num in nums_rep.get(n, [])):
            log.warning("refino: cena %d manteve o número repetido", n)
            continue
        cand = atual[:n - 1] + [txt] + atual[n:]
        if not fatos_preservados(" ".join(atual), " ".join(cand)):
            log.warning("refino: cena %d perdeu fatos, descartada", n)
            continue
        atual, aplicado = cand, True
    if aplicado:
        roteiro = json.loads(json.dumps(roteiro))
        for c, t in zip(roteiro["cenas"], atual):
            c["narracao"] = t
    return roteiro, aplicado


def _ajustar_pergunta_final(roteiro, chamar_ia):
    cenas = [c["narracao"] for c in roteiro["cenas"]]
    ultima = cenas[-1]
    qs = re.findall(r"[^.!?]*\?", ultima)
    atual = (roteiro.get("pergunta_final") or (qs[-1] if qs else "")).strip()
    if not atual:
        return roteiro, False
    if not (pergunta_final_repetida(cenas, atual) or any(g in _sem_acento(atual) for g in _GENERICOS)):
        return roteiro, False
    prompt = f"""Escreva UMA pergunta final para este vídeo.
Regras: convide o espectador a opinar sobre um ponto que o vídeo apresentou; NÃO pode ser respondida no vídeo nem repetir nenhuma pergunta anterior; até 18 palavras; termine com "?".
Pergunta atual (ruim, repete o conteúdo): {atual}
ROTEIRO: {json.dumps(cenas, ensure_ascii=False)}
Responda só JSON: {{"pergunta": ""}}"""
    try:
        nova = str(_json_ia(chamar_ia(prompt))["pergunta"]).strip()
    except Exception as e:  # noqa
        log.warning("refino: pergunta final inválida (%s)", e)
        return roteiro, False
    if (not nova.endswith("?") or not 3 <= len(nova.split()) <= 20
            or pergunta_final_repetida(cenas, nova)
            or any(g in _sem_acento(nova) for g in _GENERICOS)):
        return roteiro, False
    novo = json.loads(json.dumps(roteiro))
    if atual in ultima:
        texto = ultima.replace(atual, nova)
    else:
        texto = (re.sub(r"[^.!?]*\?\s*$", "", ultima).strip() + " " + nova).strip()
    novo["cenas"][-1]["narracao"] = texto
    novo["pergunta_final"] = nova
    return novo, True


def refinar_roteiro(roteiro, plano, chamar_ia):
    """Retorna (roteiro, relatório). Sem problema detectado, não chama a IA."""
    cenas = [c["narracao"] for c in roteiro["cenas"]]
    reps = repeticoes_numericas(cenas)
    sem = list(cenas_sem_gancho(cenas, plano)[1])
    rel = {"aplicado": False, "repeticoes": reps, "sem_gancho_antes": sem,
           "cenas_corrigidas": False, "pergunta_final_trocada": False}

    roteiro, ok1 = _corrigir_cenas(roteiro, reps, sem, chamar_ia)
    rel["cenas_corrigidas"] = ok1

    roteiro, ok2 = _ajustar_pergunta_final(roteiro, chamar_ia)
    rel["pergunta_final_trocada"] = ok2

    cenas = [c["narracao"] for c in roteiro["cenas"]]
    rel["repeticoes_depois"] = repeticoes_numericas(cenas)
    rel["sem_gancho_depois"] = list(cenas_sem_gancho(cenas, plano)[1])
    rel["aplicado"] = ok1 or ok2
    return roteiro, rel


def nota_7_criterios(roteiro, aval):
    cenas = [c["narracao"] for c in roteiro["cenas"]]
    ruins = len(aval.get("perguntas_sem_resposta") or [])
    reps = len(repeticoes_numericas(cenas))
    prom = ((aval.get("otimizacao") or {}).get("promessa_depois") or {}).get("cumprida", True)
    pf = (roteiro.get("pergunta_final") or "").strip()
    txt = _sem_acento(" ".join(cenas))
    gen = sum(g in txt for g in _GENERICOS)
    if not pf:
        enc = 70
    else:
        enc = 40 if pergunta_final_repetida(cenas, pf) else 100
    criterios = {
        "gancho": aval["gancho"]["score"],
        "retencao": round(aval["cobertura_mini_ganchos"] * 100),
        "coerencia": max(0, 100 - 20 * ruins - 20 * reps),
        "promessa": 100 if prom else 50,
        "clareza": round(aval["frases_curtas"] * 100),
        "encerramento": enc,
        "originalidade": max(0, 100 - 30 * gen),
    }
    pesos = {"gancho": 20, "retencao": 20, "coerencia": 15, "promessa": 15,
             "clareza": 10, "encerramento": 10, "originalidade": 10}
    nota = round(sum(criterios[k] * pesos[k] for k in pesos) / 100)
    return {"nota": nota, "criterios": criterios,
            "pior": min(criterios, key=criterios.get),
            "aviso": "Heurística orientativa; não mede veracidade nem prevê viralização."}
