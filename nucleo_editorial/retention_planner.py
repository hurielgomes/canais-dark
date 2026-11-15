"""Planejamento de retenção: progressão narrativa, mini-ganchos e CTA."""
from .resolver import obter_perfil


def _perfil_id(resolucao):
    r = resolucao or {}
    p = r.get("perfil_id") or r.get("perfil") or ""
    return str(p.get("id", "") if isinstance(p, dict) else p).lower()


def _tensao(perfil_id):
    """'baixa' | 'média' | 'alta', lida do campo tensao_curiosidade do perfil."""
    try:
        txt = obter_perfil(perfil_id)["tensao_curiosidade"].lower()
        return re.split(r"[;,]", txt)[0].strip()
    except Exception:  # noqa  (canal legado ou perfil inválido: mantém o comportamento antigo)
        return "alta"


_CLAREZA = (
    "exemplo: ilustra o ponto anterior com um caso concreto",
    "explicação: define ou detalha o próximo conceito em linguagem simples",
)


def planejar_retencao(n_cenas, duracao, formato=None, resolucao=None):
    pid = _perfil_id(resolucao)
    tensao = _tensao(pid)
    curto = duracao <= 45 or formato == "9x16"
    passo = 2 if curto else 3
    if tensao.startswith("méd"):
        passo += 1
    marcos = {1: "gancho: abertura que desperta curiosidade, sem entregar a resposta"}
    marcos[2] = "contexto: começa a responder e dá o primeiro fato concreto"
    virada = max(3, round(n_cenas * 0.65))
    payoff = max(3, n_cenas - 1)
    for i, c in enumerate(range(3, n_cenas - 1, passo)):
        if tensao.startswith("baix"):
            marcos[c] = _CLAREZA[i % 2]
        else:
            marcos[c] = "mini-gancho: termina abrindo uma nova dúvida ou tensão"
    if tensao.startswith("baix"):
        marcos[virada] = "destaque: o ponto mais importante ou surpreendente, dito com clareza"
    else:
        marcos[virada] = "virada: reviravolta, dado mais surpreendente ou mudança de ângulo"
    marcos[payoff] = "payoff: entrega o que o gancho prometeu"
    marcos[n_cenas] = "fecho: retoma a pergunta inicial + pergunta final contextual"
    return {
        "marcos": dict(sorted(marcos.items())),
        "perfil_id": pid,
        "tensao": tensao,
        "intervalo_mini_gancho": passo,
    }


def cta_contextual(fechamento_categoria, perfil_id=""):
    if "humor" in perfil_id:
        tom = "leve e brincalhona"
    elif any(k in perfil_id for k in ("notic", "analit", "institu")):
        tom = "séria, convidando a opinião fundamentada"
    elif "hist" in perfil_id or "narrat" in perfil_id:
        tom = "que faça o espectador se colocar na situação"
    else:
        tom = "específica sobre o ponto mais marcante do vídeo"
    return f"{fechamento_categoria} Tom da pergunta: {tom}. Sem 'curta e se inscreva' genérico."
