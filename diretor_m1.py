"""diretor_m1.py - transforma o roteiro em cenas do M1 (modelo "generica") usando a biblioteca de recursos.

Nada aqui depende de codigo por personagem/objeto: o diretor so le o catalogo (id, tipo, tags, animacoes)
e monta JSON. Recurso novo na biblioteca (inclusive SVG gerado por IA) passa a ser usado automaticamente.

Fluxo:  roteiro (narracao + imagem/busca_stock) -> DIRECAO DE ARTE -> recursos novos criados (SVG/JSON, recursos_ia.py)
        -> plano por cena -> cena JSON do M1.
A direcao de arte vem do Gemini (modo "gemini": reaproveita o que ja existe na biblioteca e PEDE o que falta) ou do
diretor LOCAL (palavras da narracao x tags/nome dos recursos; cria icones/cenarios procedurais para o que faltar).
Qualquer falha da IA cai no diretor local; nenhuma cena fica sem recursos.
"""
import json
import re
import unicodedata
from collections import Counter

import recursos_ativos as A
import recursos_ia as R

STOP = set("""para pois como mais mas que uma uns umas por com sem sobre entre ate nos nas dos das seu sua seus suas
isso essa esse esta este aqui ali ela ele eles elas voce voces nao sim ja ao aos pela pelo era foi ser tem ter ha
vai vao muito muita todo toda todos todas quando onde porque porem ainda tambem so so mesmo cada outro outra""".split())

MOVIMENTO = {"anda", "andar", "caminh", "corre", "correr", "atravess", "cruz", "segue", "seguir", "persegu", "viaj",
             "migr", "avanc", "desloc"}
SAUDACAO = {"ola", "oi", "bem-vind", "bemvind", "bom", "boa", "salve", "fala"}

# alturas (fracao da altura da tela) e posicoes por formato
ALTURA = {"personagem": {"16x9": 0.55, "9x16": 0.30}, "objeto": {"16x9": 0.34, "9x16": 0.20}}
CHAO = {"16x9": 0.80, "9x16": 0.70}
SLOTS = {1: {"16x9": [0.50], "9x16": [0.50]},
         2: {"16x9": [0.34, 0.68], "9x16": [0.30, 0.70]},
         3: {"16x9": [0.22, 0.50, 0.78], "9x16": [0.20, 0.50, 0.80]},
         4: {"16x9": [0.17, 0.39, 0.61, 0.83], "9x16": [0.16, 0.38, 0.62, 0.84]},
         5: {"16x9": [0.12, 0.31, 0.50, 0.69, 0.88], "9x16": [0.12, 0.31, 0.50, 0.69, 0.88]}}
LARGURA = {"16x9": 1920.0, "9x16": 1080.0}
ALTURA_TELA = {"16x9": 1080.0, "9x16": 1920.0}
CLIMA_PALAVRAS = {"apagado": ("apag", "escur", "blackout", "sem energia", "sem luz", "breu"),
                  "alerta": ("crise", "caos", "colaps", "perig", "panico", "emergenc", "risco", "alerta", "desastre", "ataque"),
                  "dia": ("manha", "ensolarado", "claro", "amanhecer"), "entardecer": ("tarde", "entardec", "por do sol")}
SINONIMOS_ANIM = {"descer": ("cai", "caem", "queda", "reduz", "diminu", "desce", "despenc", "esfria", "recua"),
                  "desabar": ("desab", "colaps", "queda", "cai", "despenc", "quebr", "perda", "recessao", "crise"),
                  "subir": ("sobe", "suben", "subi", "aument", "esquent", "eleva", "dispar", "alta", "cresc"),
                  "crescer": ("cresc", "aument", "dispar", "sobe", "expand", "alta"),
                  "passar": ("passa", "hora", "dias", "tempo", "demor", "prazo", "semana", "minutos"),
                  "mirar": ("alvo", "mira", "foco", "objetivo", "ataque"),
                  "abrir": ("abre", "abert", "aberto", "abrindo"),
                  "atirar": ("ataque", "atira", "dispar", "bombard", "combate", "guerra", "tiro", "confront", "batalha"),
                  "voar": ("voa", "aereo", "aerea", "aviao", "caca", "espaco aereo"),
                  "varrer": ("radar", "detect", "monitor", "vigil", "rastre"),
                  "ondular": ("bandeira", "patria", "nacional"),
                  "apontar": ("apont", "ordem", "comand", "estrateg", "plano"),
                  "alerta": ("alerta", "atento", "vigia", "ameac", "tensao", "prontid"),
                  "piscar": ("luz", "lampada", "apag", "pisca", "falha", "energia", "eletric", "queda"),
                  "tremer": ("medo", "panico", "caos", "tremor", "colaps", "desespero", "terror", "crise"),
                  "pulsar": ("alarme", "coracao", "bateria", "sinal", "pulso", "bomb"),
                  "balancar": ("vento", "balanc", "onda", "oscil"),
                  "flutuar": ("flutu", "nuvem")}
GENERICAS = {"parado", "balancar", "pulsar", "piscar", "flutuar", "tremer", "desligada"}
NUMERO_RE = re.compile(r"(\d[\d\.,]*)\s*(horas?|dias?|minutos?|semanas?|meses|anos?|segundos?|%|por cento|bilhoes|bilhao|milhoes|milhao|mil|graus|km|metros|reais|dolares)", re.I)


def _norm(txt):
    txt = unicodedata.normalize("NFKD", str(txt or "").lower())
    return "".join(c for c in txt if not unicodedata.combining(c))


def palavras(txt):
    return [w for w in re.findall(r"[a-z0-9]+", _norm(txt)) if len(w) >= 3 and w not in STOP]


def _casa(a, b):
    """igualdade ou mesmo radical (plural/genero): um comeca com o outro e a diferenca e de ate 3 letras"""
    if a == b:
        return True
    n = min(len(a), len(b))
    return n >= 4 and (a.startswith(b) or b.startswith(a)) and abs(len(a) - len(b)) <= 3


def _radical(w, k):
    """palavra do texto chama a chave (radical) do dicionario: igual, ou comeca com a chave (chave >= 4 letras)"""
    return w == k or (len(k) >= 4 and w.startswith(k))


def _chaves(rec):
    """palavras que 'chamam' o recurso: tags, nome e id."""
    ks = []
    for t in rec.get("tags") or []:
        ks += palavras(t)
    ks += palavras(rec.get("nome", "")) + palavras(str(rec.get("id", "")).replace("_", " "))
    return list(dict.fromkeys(ks))


def pontuar(rec, pal):
    """quantas palavras distintas da cena casam com as chaves do recurso (+ lista das que casaram)"""
    achadas = [w for w in dict.fromkeys(pal) if any(_casa(w, k) for k in _chaves(rec))]
    return len(achadas), achadas


def catalogo_aprovado(bib):
    return [r for r in bib.listar() if str(r.get("status", "")).startswith("aprov")]


# ------------------------------------------------------------------ plano local (casa recursos existentes + cria o que falta)
def _clima(texto):
    """clima por PALAVRA inteira/radical (nunca por trecho: 'sol' nao pode casar com 'soldados')"""
    pal = palavras(texto)
    for nome, chaves in CLIMA_PALAVRAS.items():
        if any(_radical(w, c.strip()) for w in pal for c in chaves if " " not in c.strip()):
            return nome
    return "noite"


def _rotulos(narracao):
    out = []
    for m in NUMERO_RE.finditer(narracao):
        txt = f"{m.group(1)} {m.group(2)}".upper().replace("POR CENTO", "%")
        if txt not in [o["texto"] for o in out]:
            out.append({"texto": txt})
    return out[:1]


_NOMES_ATIVO = {}


def _ativo_info(chave):
    if chave not in _NOMES_ATIVO:
        _, _, tipo, nome, tags = A.ATIVOS[chave]()
        _NOMES_ATIVO[chave] = (tipo, nome, tags)
    return _NOMES_ATIVO[chave]


def _icone_de(pal):
    """primeira palavra que chama um ativo detalhado (soldado, tanque...) ou um icone procedural -> spec de recurso novo"""
    for w in pal:
        for k, chave in A.CHAVES_ATIVO.items():
            if _radical(w, k):
                tipo, nome, tags = _ativo_info(chave)
                return {"id": chave, "tipo": tipo, "nome": nome, "tags": list(dict.fromkeys([w] + tags))}
        for k, (ic, cor, nome) in R.CHAVES_ICONE.items():
            if _radical(w, k):
                return {"id": R.slug(nome), "tipo": "personagem" if ic == "pessoa" else "objeto", "nome": nome, "tags": [w, k]}
    return None


def planejar_local(roteiro, catalogo):
    """planos com ids existentes (casamento por tags) + 'novo' (specs de recursos a criar) quando a biblioteca nao cobre."""
    cen = [r for r in catalogo if r["tipo"] == "cenario"]
    per = [r for r in catalogo if r["tipo"] == "personagem"]
    obj = [r for r in catalogo if r["tipo"] not in ("cenario", "fundo", "personagem")]
    cenas = roteiro["cenas"]
    textos = [" ".join(str(c.get(k, "")) for k in ("narracao", "imagem", "busca_stock")) for c in cenas]
    pals = [palavras(t) for t in textos]
    video_txt = " ".join([str(roteiro.get("titulo", ""))] + textos)
    pal_video = palavras(video_txt)
    clima_video = _clima(video_txt)
    cont = Counter()
    for pal in pals:
        for w in pal:
            spec = _icone_de([w])
            if spec:
                cont[spec["id"]] += 1
    dominante = cont.most_common(1)[0][0] if cont else None
    tipo_cen = next((R.CHAVES_CENARIO[k] for w in pal_video for k in R.CHAVES_CENARIO if _radical(w, k)), "cidade")
    planos, cen_atual, ids_ult = [], None, []
    for i, pal in enumerate(pals):
        plano = {"cenario": None, "personagens": [], "objetos": [], "destaques": [],
                 "rotulos": _rotulos(textos[i]) or (_rotulos(str(roteiro.get("titulo", ""))) if i == 0 else []),
                 "clima": _clima(textos[i]) if _clima(textos[i]) != "noite" else clima_video}
        # cenario: biblioteca primeiro; senao um procedural coerente com o tema/clima
        melhor = max(cen, key=lambda r: pontuar(r, pal)[0]) if cen else None
        forte = False
        if melhor is not None:      # evidencia forte: 2+ palavras casam, ou TODAS as palavras do id (ex.: "savana"; "sala"+"noite")
            toks = palavras(str(melhor["id"]).replace("_", " "))
            forte = pontuar(melhor, pal)[0] >= 2 or (bool(toks) and all(any(_casa(w, k) for w in pal) for k in toks))
        if forte:
            cen_atual = melhor["id"]
        elif cen_atual is None or not str(cen_atual).startswith("cenario_"):
            cen_atual = {"novo": {"id": f"cenario_{tipo_cen}_{plano['clima']}", "tipo": "cenario", "nome": f"Cenario {tipo_cen}",
                                  "tags": [tipo_cen, plano["clima"]], "clima": plano["clima"]}}
        elif isinstance(cen_atual, dict) and cen_atual["novo"]["clima"] != plano["clima"]:
            cen_atual = {"novo": {"id": f"cenario_{tipo_cen}_{plano['clima']}", "tipo": "cenario", "nome": f"Cenario {tipo_cen}",
                                  "tags": [tipo_cen, plano["clima"]], "clima": plano["clima"]}}
        plano["cenario"] = cen_atual
        # personagens / objetos da biblioteca que casam
        pp = sorted(((pontuar(r, pal)[0], -k, r["id"]) for k, r in enumerate(per)), reverse=True)
        plano["personagens"] = [x[2] for x in pp if x[0] > 0][:2]
        op = sorted(((pontuar(r, pal)[0], -k, r["id"]) for k, r in enumerate(obj)), reverse=True)
        plano["objetos"] = [x[2] for x in op if x[0] > 0][:3]
        # o que a biblioteca nao cobre vira recurso NOVO (icone procedural, ou SVG por IA no modo gemini)
        vistos = set()
        anteriores = set(planos[-1].get("_ids", [])) if planos else set()
        cands = []
        for w in pal:
            spec = _icone_de([w])
            if spec and spec["id"] not in [c["id"] for c in cands]:
                cands.append(spec)
        frescos = [c for c in cands if c["id"] not in anteriores]
        for spec in (frescos or cands)[:3]:
            if spec["id"] in vistos:
                continue
            vistos.add(spec["id"])
            if any(r["id"] == spec["id"] for r in catalogo):
                (plano["personagens"] if spec["tipo"] == "personagem" else plano["objetos"]).append(spec["id"])
            else:
                (plano["personagens"] if spec["tipo"] == "personagem" else plano["objetos"]).append({"novo": spec})
        if not plano["objetos"] and not plano["personagens"] and dominante:
            spec = next((_icone_de([k]) for k in list(R.CHAVES_ICONE) if R.slug(R.CHAVES_ICONE[k][2]) == dominante), None)
            if spec:
                plano["objetos" if spec["tipo"] != "personagem" else "personagens"].append({"novo": spec})
        plano["personagens"], plano["objetos"] = _unicos(plano["personagens"])[:2], _unicos(plano["objetos"])[:3]
        plano["_ids"] = [x if isinstance(x, str) else x["novo"]["id"] for x in plano["personagens"] + plano["objetos"]]
        ach = []
        for r in catalogo:
            if r["id"] in plano["personagens"] + plano["objetos"]:
                ach += pontuar(r, pal)[1]
        plano["destaques"] = list(dict.fromkeys(ach))[:3]
        planos.append(plano)
    return planos


def _unicos(lista):
    vistos, out = set(), []
    for x in lista:
        k = x if isinstance(x, str) else x["novo"]["id"]
        if k not in vistos:
            vistos.add(k)
            out.append(x)
    return out


# ------------------------------------------------------------------ direcao de arte por IA (Gemini)
def llm_gemini(cfg, cv):
    from google import genai
    from google.genai import types
    cli = genai.Client(api_key=cfg["gemini_api_key"], http_options=types.HttpOptions(timeout=240000))

    def llm(prompt, json_mode=True):
        conf = types.GenerateContentConfig(response_mime_type="application/json" if json_mode else "text/plain",
                                           temperature=0.5 if json_mode else 0.8)
        return cv.gerar_conteudo_texto_com_fallback(cli, cfg, prompt, conf, operacao="direcao de arte" if json_mode else "desenho de recurso").text or ""
    return llm


PROMPT_ARTE = """Voce e o DIRETOR DE ARTE de um video explicativo 2D, cinematografico, no estilo infografico noturno (referencia: uma cena sobre \
apagao em que um REFRIGERADOR grande e detalhado, com a porta abrindo e mostrando garrafas, ocupa o centro; ao lado um TERMOMETRO vermelho com marcador "15 C"; \
ao fundo uma JANELA com lua e predios iluminados; no topo um chip "22:10 SEXTA" e um selo "4 HORAS - porta fechada").
O video e montado por JSON/SVG: voce escolhe recursos da biblioteca e PEDE novos recursos para tudo que a narracao mostra e a biblioteca nao tem.
Um ilustrador desenhara cada recurso novo com MUITO detalhe, entao seja ESPECIFICO no que pede (nunca "icone de energia" - e sim "subestacao eletrica com transformadores e linhas de alta tensao").

PARA CADA CENA defina uma COMPOSICAO que conte a historia daquela fala:
- cenario: o lugar (ref existente ou novo), com clima (noite|dia|entardecer|alerta|apagado). Descreva no cenario os elementos do lugar (janela, lua, predios, ruinas...).
- hero: o objeto PRINCIPAL da cena, grande e detalhado, o que a fala esta mostrando (ex.: tanque, mapa estrategico, aviao de combate, painel de radar).
- apoio: 1 a 3 objetos menores que reforcam a ideia (ex.: termometro, bandeira, mapa, missil, grafico em queda).
- personagens: 0 a 2 (soldado, civil, cientista...), com 'anim' coerente (ex.: apontar, caminhar, alerta) e "andar":true se atravessam a cena.
- chip: texto curtissimo de contexto no topo, "TEMPO · LUGAR" (ex.: "22:10 · SEXTA", "DIA 1 · FRONTEIRA"), ou null.
- rotulos: ate 1 destaque. Se for um NUMERO, comece pelo numero (ele sera exibido gigante e contando de 0 ate o valor): {"texto":"8.551.000 KM2","sub":"extensao do territorio"}. Se for um termo, use MAIUSCULAS curtas.
- chamada: opcional, leitura presa ao hero com linha-guia (ex.: {"texto":"15 C","detalhe":"temperatura interna"}).
DIDATICA E VIRALIDADE: o espectador precisa entender a ideia em 2 segundos SEM ouvir. Prefira objetos CONCRETOS e reconheciveis (tanque, soldado, mapa do Brasil, \
aviao, navio, hospital, geladeira) a abstracoes (nada de "marco fronteirico gigante", "linhas de latitude"). Mostre a ideia por MUDANCA DE ESTADO: o catalogo traz widgets \
animados prontos (termometro que sobe, medidor, relogio que passa, barras_crescendo, barras_caindo, alvo) - USE-OS para temperatura, risco, tempo, crescimento, queda e alvo. \
Cada fala deve ter um MOMENTO visual claro (algo muda, abre, sobe, cai, aparece). A cena 1 e o gancho: o hero mais impactante + numero grande.
REGRAS: cada cena DEVE ter hero ou personagem; varie o hero entre cenas e reutilize o MESMO id quando o elemento reaparece; nao reutilize um recurso \
generico que nao tenha a ver com a fala; use ids do catalogo apenas quando servirem EXATAMENTE; 'anim' so pode ser animacao do catalogo para aquele \
recurso (ou, para recurso novo, um nome de animacao que voce quer: ex. "atirar","abrir","varrer","voar"); mantenha o mesmo cenario enquanto o lugar nao mudar.
Recurso novo: {"novo":{"id":"snake_case","tipo":"cenario|personagem|objeto","nome":"...","tags":["palavras que o chamam"],"descricao":"descricao VISUAL detalhada: formas, cores, partes, estado, luz","clima":"..."}}
Responda apenas JSON: {"cenas":[{"n":1,"cenario":{"ref":"id"}|{"novo":{...}},"clima":"noite","hero":{"ref":"id"|"novo":{...},"anim":null},"apoio":[{"ref":..}|{"novo":{...}}],\
"personagens":[{"ref":..|"novo":{...},"anim":null,"andar":false}],"chip":"...","rotulos":[{"texto":"72 HORAS","sub":"sem energia"}],"chamada":{"texto":"15 C","detalhe":"temperatura"}|null}]}
"""


def planejar_arte_ia(roteiro, catalogo, llm, cv):
    """Gemini escolhe recursos existentes e PEDE os que faltam (descricao visual). Ids invalidos sao descartados."""
    cat = [{"id": r["id"], "tipo": r["tipo"], "nome": r.get("nome", ""), "tags": r.get("tags", []), "animacoes": r.get("animacoes", [])} for r in catalogo]
    cenas = [{"n": i + 1, "narracao": c["narracao"], "visual": c.get("imagem", "")} for i, c in enumerate(roteiro["cenas"])]
    prompt = (PROMPT_ARTE + f"\nTITULO: {roteiro.get('titulo', '')}\n\nCATALOGO (reutilizaveis):\n{json.dumps(cat, ensure_ascii=False)}"
              f"\n\nCENAS:\n{json.dumps(cenas, ensure_ascii=False)}")
    dados = cv._parse_json(llm(prompt, True))
    ids = {x["id"]: x for x in catalogo}

    def item(x, tipos):
        if isinstance(x, str):
            x = {"ref": x}
        if not isinstance(x, dict):
            return None, {}
        extra = {"anim": x.get("anim"), "andar": bool(x.get("andar"))}
        if x.get("ref") in ids and ids[x["ref"]]["tipo"] in tipos:
            return x["ref"], extra
        n = x.get("novo")
        if isinstance(n, dict) and (n.get("id") or n.get("nome")):
            n = dict(n, tipo=n.get("tipo") if n.get("tipo") in ("cenario", "personagem", "objeto") else tipos[0])
            n["id"] = R.slug(n.get("id") or n.get("nome"))
            return {"novo": n}, extra
        return None, {}

    planos = []
    for i in range(len(roteiro["cenas"])):
        it = next((c for c in dados.get("cenas", []) if c.get("n") == i + 1), {})
        pl = {"cenario": None, "personagens": [], "objetos": [], "destaques": [], "ia": {}, "rotulos": [], "hero": None,
              "chip": (str(it.get("chip") or "").strip().upper()[:28] or None),
              "clima": it.get("clima") if it.get("clima") in R.CLIMAS else "noite"}
        pl["cenario"], _ = item(it.get("cenario"), ("cenario",))
        nomeid = lambda v: v if isinstance(v, str) else v["novo"]["id"]  # noqa: E731
        hv, hx = item(it.get("hero"), ("objeto", "personagem"))
        if hv:
            pl["objetos" if (isinstance(hv, str) and ids[hv]["tipo"] != "personagem") or (not isinstance(hv, str) and hv["novo"]["tipo"] != "personagem") else "personagens"].append(hv)
            pl["hero"] = nomeid(hv)
            pl["ia"][nomeid(hv)] = hx
        for x in (it.get("apoio") or [])[:3]:
            v, ex = item(x, ("objeto",))
            if v and nomeid(v) not in [nomeid(o) for o in pl["objetos"]]:
                pl["objetos"].append(v)
                pl["ia"][nomeid(v)] = ex
        for x in (it.get("personagens") or [])[:2]:
            v, ex = item(x, ("personagem",))
            if v and nomeid(v) not in [nomeid(o) for o in pl["personagens"]]:
                pl["personagens"].append(v)
                pl["ia"][nomeid(v)] = ex
        ch = it.get("chamada")
        if isinstance(ch, dict) and ch.get("texto"):
            pl["chamada"] = {"texto": str(ch["texto"]), "detalhe": str(ch.get("detalhe") or "")}
        for r in (it.get("rotulos") or [])[:1]:
            t = (r.get("texto") if isinstance(r, dict) else str(r) or "").strip()
            if t:
                pl["rotulos"].append({"texto": t.upper()[:28], "sub": (str(r.get("sub") or "")[:40] if isinstance(r, dict) else "")})
        planos.append(pl)
    return planos


def materializar(planos, bib, llm, log=print):
    """cria os recursos 'novo' (IA ou procedural), registra/aprova e troca os pedidos por ids."""
    criados = {}

    def res(x):
        if x is None or isinstance(x, str):
            return x
        n = x["novo"]
        if n["id"] not in criados:
            criados[n["id"]] = R.criar_recurso(n, bib, llm, log)
        return criados[n["id"]]
    for p in planos:
        p["cenario"] = res(p["cenario"])
        p["personagens"] = [res(x) for x in p["personagens"]]
        p["objetos"] = [res(x) for x in p["objetos"]]
        ia = p.get("ia") or {}
        p["ia"] = {(R.slug(k) if R.slug(k) in criados.values() else k): v for k, v in ia.items()}
        if p.get("hero"):
            p["hero"] = R.slug(p["hero"]) if R.slug(p["hero"]) in criados.values() else p["hero"]
        p["personagens"] = _unicos([x for x in p["personagens"] if x])
        p["objetos"] = _unicos([x for x in p["objetos"] if x])
    return planos


# ------------------------------------------------------------------ plano -> cena JSON
def _escolher_anim(rec, pal, primeira, andar, tipo, k):
    anims = list(rec.get("animacoes") or [])
    if not anims:
        return None
    txt = " ".join(pal)
    for a in anims:                       # nome da animacao dito na narracao
        if a not in GENERICAS and any(_casa(w, x) for w in pal for x in palavras(a.replace("_", " "))):
            return a
    if andar and "caminhar" in anims:
        return "caminhar"
    if primeira and "acenar" in anims:
        return "acenar"
    for a, chaves in SINONIMOS_ANIM.items():   # sinonimos (luz -> piscar, ataque -> atirar, radar -> varrer ...)
        if a in anims and any(c in txt for c in chaves):
            return a
    PREF = ["subir", "crescer", "passar", "mirar", "desabar", "atirar", "voar", "varrer", "ondular", "abrir", "apontar"]
    proprias = sorted((a for a in anims if a not in GENERICAS and a not in ("caminhar", "acenar", "ligar", "ligada")),
                      key=lambda a: (PREF.index(a) if a in PREF else 99, a))
    if tipo == "objeto" and proprias:
        return proprias[k % len(proprias)]
    if tipo == "personagem" and "alerta" in anims:
        return "alerta"
    if tipo == "objeto" and "flutuar" in anims and rec.get("origem") in ("ia", "procedural"):
        return ("flutuar", "pulsar", "balancar")[k % 3] if ("pulsar" in anims and "balancar" in anims) else "flutuar"
    return None


def _caixa(bib, rid, fallback):
    try:
        return bib.obter(rid)[0]["caixa"]
    except Exception:  # noqa
        return fallback


# (x, y, altura) por papel e formato. A altura e limitada pela largura disponivel.
LAYOUT = {
    "16x9": {"hero": (0.40, 0.80, 0.64), "hero_so": (0.50, 0.80, 0.68), "pers": [(0.76, 0.83, 0.58), (0.90, 0.83, 0.50)],
             "apoio": [(0.13, 0.79, 0.30), (0.62, 0.74, 0.24), (0.90, 0.75, 0.26)], "apoio_so": [(0.16, 0.79, 0.32), (0.85, 0.79, 0.32), (0.50, 0.70, 0.20)]},
    "9x16": {"hero": (0.56, 0.68, 0.40), "hero_so": (0.50, 0.69, 0.44), "pers": [(0.22, 0.76, 0.28), (0.82, 0.76, 0.24)],
             "apoio": [(0.15, 0.70, 0.17), (0.86, 0.70, 0.17), (0.50, 0.30, 0.0)], "apoio_so": [(0.15, 0.71, 0.18), (0.86, 0.71, 0.18), (0.50, 0.30, 0.0)]},
}
LARG_MAX = {"16x9": {"hero": 0.50, "pers": 0.30, "apoio": 0.24}, "9x16": {"hero": 0.84, "pers": 0.42, "apoio": 0.30}}
ACENTO = {"noite": "#2de2e6", "alerta": "#ff4d4f", "apagado": "#ffb02e", "dia": "#ffd37a", "entardecer": "#ff8a4a"}
NUM_RE = re.compile(r"^\s*(\d[\d\.,]*)\s*(.*)$")


def _contador(texto):
    """'8.551.000 KM2' -> {de:0, ate:8551000, sufixo:' KM2'}; None se nao comecar por numero"""
    m = NUM_RE.match(texto or "")
    if not m:
        return None
    tok, resto = m.group(1).rstrip(".,"), m.group(2).strip()
    try:
        if re.fullmatch(r"\d{1,3}(\.\d{3})+", tok):
            val, dec = float(tok.replace(".", "")), 0
        elif "," in tok:
            val, dec = float(tok.replace(".", "").replace(",", ".")), len(tok.split(",")[-1])
        else:
            val, dec = float(tok), 0
    except ValueError:
        return None
    return {"de": 0, "ate": val, "decimais": dec, "sufixo": (" " + resto.upper()) if resto else ""}


def plano_para_cena(plano, catalogo, narracao, dur, i, texto_extra="", bib=None):
    ids = {r["id"]: r for r in catalogo}
    if bib is not None:                         # origem do recurso (ia/procedural) pode mudar a escolha da animacao
        for r in catalogo:
            r.setdefault("origem", bib.idx["recursos"].get(r["id"], {}).get("origem"))
    pal = palavras(narracao + " " + texto_extra)
    andar_geral = any(_casa(w, m) for w in pal for m in MOVIMENTO)
    cena = {"modelo": "generica", "duracao": dur, "elementos": []}
    clima = plano.get("clima") or "noite"
    acento = ACENTO.get(clima, "#2de2e6")
    if plano.get("cenario") in ids:
        cena["cenario"] = {"ref": plano["cenario"]}
        amb = R.CLIMAS.get(clima, R.CLIMAS["noite"])
        cena["cenario"]["ambiente"] = {"cor": amb[4], "forca": round(amb[5] * 0.55, 3)}     # menos "veu" escuro: o cenario precisa aparecer
    chars = [c for c in plano.get("personagens", []) if c in ids][:2]
    objs = [o for o in plano.get("objetos", []) if o in ids]
    hero = plano.get("hero") if plano.get("hero") in objs else (objs[0] if objs else None)
    apoio = [o for o in objs if o != hero][:3]
    itens = []      # (id, papel, indice_no_papel)
    if hero:
        itens.append((hero, "hero", 0))
    itens += [(c, "pers", k) for k, c in enumerate(chars)]
    itens += [(o, "apoio", k) for k, o in enumerate(apoio)]
    info_hero = {}
    for k, (rid, papel, idx) in enumerate(itens):
        rec = ids[rid]
        tipo = "personagem" if rec["tipo"] == "personagem" else "objeto"
        cx = _caixa(bib, rid, [0, 0, 200, 200]) if bib is not None else [0, 0, 200, 200]
        asp = max(0.15, (cx[2] - cx[0]) / max(1.0, (cx[3] - cx[1])))
        pos, alt, ok = {}, {}, True
        for f in ("16x9", "9x16"):
            L = LAYOUT[f]
            if papel == "hero":
                x, y, h = L["hero"] if chars else L["hero_so"]
            elif papel == "pers":
                x, y, h = L["pers"][idx] if hero or apoio else (0.5 if idx == 0 else 0.8, L["pers"][0][1], L["pers"][0][2])
            else:
                x, y, h = (L["apoio"] if (hero and chars) or (chars and not hero) else L["apoio_so"])[idx]
            if h <= 0:
                ok = False
                break
            h = min(h, LARG_MAX[f][papel] * LARGURA[f] / (ALTURA_TELA[f] * asp))
            pos[f], alt[f] = [x, y], round(h, 3)
        if not ok:
            continue
        if papel == "hero":
            info_hero = {f: (pos[f][0], pos[f][1], alt[f]) for f in pos}
        el = {"id": rid, "ref": rid, "z": 10 + (30 if papel == "pers" else 20 if papel == "hero" else 0) + k, "altura": alt, "k": 1.0, "pos": pos}
        el["entrada"] = ({"tipo": "pop", "t": 0.1, "dur": 0.6} if papel == "hero" else
                         {"tipo": ("esq" if idx % 2 == 0 else "dir"), "t": 0.35 + 0.15 * idx, "dur": 0.6} if papel == "pers" else
                         {"tipo": "subir", "t": 0.55 + 0.2 * idx, "dur": 0.55})
        ia = (plano.get("ia") or {}).get(rid, {})
        andar = (ia.get("andar") if ia else andar_geral) and tipo == "personagem"
        pedida = ia.get("anim") if ia.get("anim") in (rec.get("animacoes") or []) else None
        anim = pedida or _escolher_anim(rec, pal, i == 0, andar, tipo, k)
        tl = [{"t": 0.0, "anim": "parado"}] if "parado" in (rec.get("animacoes") or []) else []
        if anim and anim != "parado":
            tl.append({"t": round(0.7 + 0.2 * k, 2), "anim": anim, "mix": 0.3, **({"sincronizar": True} if anim == "caminhar" else {})})
            if tipo == "objeto" and anim == "ligar" and "ligada" in rec["animacoes"]:
                tl.append({"t": 1.6, "anim": "ligada", "mix": 0})
            elif anim in ("atirar",) and dur > 3.5:        # repete o disparo no meio da cena
                tl.append({"t": round(min(dur - 1.5, dur / 2 + 0.3), 2), "anim": "atirar", "mix": 0.1})
        if tl:
            el["linha_do_tempo"] = tl
        if andar and anim == "caminhar" and dur > 2:
            a = {f: [max(0.12, pos[f][0] - 0.25), pos[f][1]] for f in ("16x9", "9x16")}
            b = {f: [min(0.88, pos[f][0] + 0.25), pos[f][1]] for f in ("16x9", "9x16")}
            el["pos"] = a
            el["mover"] = [{"t": 0.0, "para": a}, {"t": 0.9, "para": a}, {"t": max(1.6, dur - 0.8), "para": b, "ease": "in_out"}]
            el["olhar"] = "direita"
            el.pop("entrada", None)
        cena["elementos"].append(el)
    # luz de recorte atras do heroi: separa o objeto do fundo e guia o olhar
    luzes = []
    if info_hero:
        luzes.append({"pos": {f: [info_hero[f][0], info_hero[f][1] - info_hero[f][2] * 0.5] for f in info_hero}, "raio": {"16x9": 0.55, "9x16": 0.40},
                      "cor": acento, "int": 0.42, "k": 0.6, "exp": 1.6})
    if luzes:
        cena["luzes"] = luzes
    if dur > 1.5:      # "soco" de camera no inicio + aproximacao lenta (o motor ja soma um assentamento de 0,5 s)
        cena["camera"] = {"zoom": [{"t": 0, "v": 1.0}, {"t": round(dur, 2), "v": 1.07, "ease": "in_out"}]}
    hud = {}
    chip = plano.get("chip")
    if chip and dur > 1.5:
        partes = re.split(r"\s*[·|•/-]\s*", str(chip), maxsplit=1)
        hud["chip"] = {"hora": partes[0].strip()[:18], "dia": (partes[1].strip()[:18] if len(partes) > 1 else ""), "t": 0.3}
    rot = (plano.get("rotulos") or [None])[0]
    if rot and dur > 2:
        cont = _contador(rot["texto"])
        if cont:     # numero dominante com contagem animada (gancho visual); a explicacao vai embaixo
            hud["contadores"] = [dict(cont, t=0.7, fim=max(1.5, dur - 0.4), dur=1.8, cor=("#ff3e48" if clima in ("alerta", "apagado") else "#ffd23a"),
                                      sub=rot.get("sub", ""), tam={"16x9": 150, "9x16": 150},
                                      pos={"16x9": [0.76, 0.22], "9x16": [0.5, 0.17]})]
        else:
            hx = {f: (min(0.84, info_hero[f][0] + 0.26) if f == "16x9" else min(0.80, info_hero[f][0] + 0.28), max(0.14, info_hero[f][1] - info_hero[f][2] - 0.01))
                  for f in info_hero} if info_hero else {"16x9": (0.76, 0.18), "9x16": (0.5, 0.16)}
            hud["etiquetas"] = [{"texto": rot["texto"], "sub": rot.get("sub", ""), "t": 0.8, "fim": max(1.5, dur - 0.4), "tam": 58, "rot": -3,
                                 "pos": {f: list(hx[f]) for f in hx}}]
    ch = plano.get("chamada")
    if ch and info_hero and dur > 2.5:
        hud["chamadas"] = [{"texto": str(ch.get("texto", ""))[:18], "detalhe": str(ch.get("detalhe", ""))[:30], "t": 1.4, "cor": "#ff8a80", "tam": 34,
                            "alvo": {f: [info_hero[f][0], info_hero[f][1] - info_hero[f][2] * 0.55] for f in info_hero},
                            "para": {f: [info_hero[f][0] - (0.10 if f == "16x9" else 0.08), info_hero[f][1] - info_hero[f][2] * 0.95] for f in info_hero}}]
    if hud:
        cena["hud"] = hud
    if plano.get("destaques"):
        cena["destaques"] = list(plano["destaques"])
    return cena


def dirigir(roteiro, duracoes, bib, modo="auto", cfg=None, cv=None, log=print):
    """devolve lista de cenas M1 (uma por cena do roteiro). Cria na biblioteca os recursos que o roteiro pedir."""
    R.garantir_kit(bib, log)
    cat = catalogo_aprovado(bib)
    llm = None
    if modo in ("auto", "gemini") and cfg and cfg.get("gemini_api_key") and cv is not None:
        try:
            llm = llm_gemini(cfg, cv)
        except Exception as e:  # noqa
            log(f"   IA indisponivel ({str(e)[:80]}); usando o diretor local.")
    planos = None
    if llm:
        # a IA so ve recursos de qualidade (curados/desenhados por IA): icones procedurais de reserva nao sao oferecidos
        cat_ia = [r for r in cat if bib.idx["recursos"].get(r["id"], {}).get("origem") != "procedural"]
        try:
            planos = planejar_arte_ia(roteiro, cat_ia, llm, cv)
            log("   direcao de arte: Gemini")
        except Exception as e:  # noqa
            log(f"   direcao de arte por IA falhou ({str(e)[:80]}); usando o diretor local.")
    if planos is None:
        planos = planejar_local(roteiro, cat)
        log("   direcao de arte: local (palavras-chave + biblioteca)")
    planos = materializar(planos, bib, llm if planos and llm else None, log)
    cat = catalogo_aprovado(bib)
    return [plano_para_cena(p, cat, c["narracao"], duracoes[i], i, " ".join(str(c.get(k, "")) for k in ("imagem", "busca_stock")), bib=bib)
            for i, (p, c) in enumerate(zip(planos, roteiro["cenas"]))]
