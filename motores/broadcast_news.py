from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import criar_video as cv  # noqa: E402
from editorial_rules import get_category, ensure_closing_question  # noqa: E402

WIDTHS = {"16x9": (1920, 1080), "9x16": (1080, 1920)}
FPS = 30
VISUAL_TYPES = {"headline", "stat", "flow", "timeline", "comparison", "chart", "bullets", "quote", "definition", "impacto"}


class BroadcastError(RuntimeError):
    pass


def info(message: str) -> None:
    print(message, flush=True)


def slug(text: str) -> str:
    return cv.slug(text) or "broadcast-news"


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BroadcastError(f"Nao foi possivel ler {path.name}: {exc}") from exc


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def cortar_texto(texto: str, limite: int) -> str:
    """Corta no ultimo espaco, sem quebrar palavra."""
    texto = " ".join(str(texto or "").split())
    if len(texto) <= limite:
        return texto
    corte = texto[:limite].rsplit(" ", 1)[0]
    return corte.rstrip(",;:-") + "..."


REGRAS_NARRACAO = """
REGRAS DE NARRACAO (obrigatorio):

1. Escreva PRIMEIRO o campo "narracao_completa": um texto corrido, como um apresentador falando,
   com conectivos entre as frases ("so que", "e ai", "por isso", "na pratica", "o detalhe e que").
2. Nunca comece duas frases seguidas com o mesmo sujeito. Use pronomes e sinonimos.
3. Use fatos e exemplos concretos do Brasil. NAO invente numeros; se nao tiver certeza, nao cite.
4. Cada frase deve puxar a proxima: pergunta -> resposta, causa -> consequencia, problema -> virada.
5. Depois divida a narracao_completa entre as cenas: o campo "narracao" de cada cena deve ser um
   TRECHO EXATO e consecutivo dela. Juntando todas, o resultado deve ser identico a narracao_completa.
6. A narracao de uma cena pode terminar no meio de um raciocinio e a proxima continuar; o que importa
   e o texto inteiro soar como uma fala unica.
7. Sem repeticao de ideia entre cenas. A ultima cena faz a pergunta final, sem resumo.
"""

LINGUAGEM_POPULAR = """
LINGUAGEM POPULAR (prioridade maxima, vale mais que qualquer outra regra de estilo):
- Publico: pessoa comum de 18 a 45 anos, que NAO se interessa pelo tema. Escreva como quem explica
  pra um amigo no WhatsApp ou pra mae na cozinha. Se ela nao entender de primeira, o roteiro falhou.
- Fale SEMPRE com "voce" e sobre a vida da pessoa: salario, mercado, conta de luz, celular, aluguel,
  padaria, onibus, Pix, delivery, guarda-roupa, familia. Nunca escreva do ponto de vista de empresas,
  empreendedores ou especialistas.
- Cada ideia precisa de um EXEMPLO CONCRETO do cotidiano logo em seguida ("Pensa no seu celular...",
  "Sabe quando voce vai no mercado e...").
- Proibido termo tecnico, palavra em ingles ou palavra de relatorio. Exemplos proibidos: faturamento,
  margem, demanda, varejo, alocar, recursos, emergente, vulneravel, principio, impacto, otimizar,
  best-seller, consumidor, setor. Se precisar de um termo tecnico, explique na mesma frase com palavras simples.
- Frases de no maximo 15 palavras. Uma ideia por frase. Pode usar "pois e", "repara", "olha so", "sabe quando".
- GANCHO: comece por uma situacao que a pessoa ja viveu ou uma pergunta sobre a vida dela, nunca pelo
  nome do conceito. Ruim: "Ja ouviu falar da regra 80/20?" Bom: "Por que voce sempre usa as mesmas roupas?"
- TITULO: curiosidade sobre a vida da pessoa, sem jargao. Ruim: "Regra de Pareto no varejo". Bom:
  "A regra que explica pra onde vai seu salario".
- PERGUNTA FINAL: sobre a vida pessoal de quem assiste, facil de responder em uma palavra ou frase.
- Textos da tela (headline, items, steps) seguem a mesma regra: palavras simples, nada de jargao.
- Antes de responder, releia a narracao e troque qualquer palavra que um jovem de 18 anos nao usaria.
"""


def make_research_prompt(channel: dict, topic: str, duration: int, category: str) -> str:
    scene_count = max(8, min(48, round(duration / 10)))
    words = max(120, round(duration * 2.15))
    channel_name = channel.get("nome", "Canal")
    audience = channel.get("publico", "publico geral")
    tone = channel.get("tom", "jornalismo explicativo, claro e direto")
    profile = get_category(category).get("editorial_profile", {})
    category_rules = "\n".join([f"Objetivo: {profile.get('objective', '')}", f"Tom: {profile.get('tone', '')}", "Estrutura: " + "; ".join(profile.get("structure", [])), f"Regra factual: {profile.get('fact_policy', '')}", f"Evitar: {profile.get('avoid', '')}", f"Direcao visual: {profile.get('visual_guidance', '')}"])
    closing = profile.get("closing_question", "Qual aspecto desse assunto mais chamou sua atencao? Comente.")
    return f"""Voce e roteirista de videos curtos virais (TikTok/Reels/Shorts) para o publico brasileiro geral, nao especialista.

CANAL: {channel_name}
PUBLICO: {audience}
TOM: {tone}
CATEGORIA: {category}
PERFIL EDITORIAL DA CATEGORIA:
{category_rules}
ASSUNTO: {topic}
DATA DE REFERENCIA: {date.today().strftime('%d/%m/%Y')}

FATOS E PRECISAO (SEM PESQUISA WEB):
- Nao use Google Search, ferramentas externas nem invente URLs.
- Priorize fatos historicos, conceitos, regras e mecanismos consolidados, amplamente conhecidos e estaveis.
- Nao afirme que uma lei, aliquota, calendario, eleicao, cargo, politica publica ou regra continua vigente hoje sem fonte atual fornecida pelo usuario.
- Se o tema depender de atualizacao recente, delimite o roteiro ao funcionamento geral e inclua uma nota em resumo_pesquisa: "conferir atualizacao antes de publicar".
- Nao invente numeros, porcentagens, datas, falas, pesquisas, leis, fontes ou citacoes. Se nao tiver certeza, omita o dado ou explicite a incerteza.
- Diferencie fato consolidado, proposta, previsao, opiniao e hipotese.
- Para direito, economia e politica, produza conteudo informativo, nao aconselhamento juridico, tributario ou financeiro.
- O texto deve explicar o assunto, nao apenas ler manchetes.

NARRATIVA:
- Gere cerca de {words} palavras, divididas em aproximadamente {scene_count} cenas.
- A primeira cena e o GANCHO: pergunta curiosa + frase de retencao ("Aposto que voce nao sabia dessa", "O ultimo ponto vai te surpreender"). Sem resposta ainda.
- Frases curtas, linguagem do dia a dia, mas sempre ligadas a frase anterior por conectivos.
- Termine retomando o gancho e com uma pergunta final que a pessoa QUEIRA responder: opiniao polarizada ("E voce, e a favor ou contra...?") ou experiencia pessoal ("Ja aconteceu com voce? Me conta aqui"). Proibido pergunta generica ou academica.
- A explicacao comeca na segunda cena.
- Use frases faladas, claras, sem jargao desnecessario.
- A cada 2 ou 3 cenas, introduza uma nova informacao ou virada.
- Pergunta final sugerida para a categoria: {closing}
- Ajuste a pergunta ao tom real do canal e ao tema; humor pede pergunta descontraida, assunto serio pede pergunta seria.
- Nao inclua saudacoes, "neste video" ou pedidos genericos de inscricao.

DIRECAO VISUAL — BROADCAST NEWS:
- Para cada cena, informe os campos de midia dentro de visual.
- midia_tipo: pessoa, local, evento ou conceito.
- busca_wikimedia: nome especifico para busca no Wikimedia Commons.
- Para pessoa, escreva nome e sobrenome. Nao use nomes vagos.
- prompt_midia_ia: ilustracao conceitual em ingles, sem texto.
- Nunca apresente ilustracao gerada como registro historico real.
- Nao use apresentador fixo nem bancada de jornal como protagonista.
- O protagonista e o fato, o mecanismo, os dados ou o acontecimento.
- Cada cena deve ter um cartao visual que esclareca a narracao.
- Use layouts variados: headline, stat, flow, timeline, comparison, chart, bullets, quote ou definition.
- Os valores de graficos devem vir de fatos encontrados nas fontes. Nao fabrique dados para preencher graficos.
- Se nao houver dados numericos verificaveis, escolha flow, timeline, bullets ou definition.
- Titulos visuais curtos, no maximo 10 palavras; texto de apoio no maximo 22 palavras por bloco.
- Evite texto pequeno demais e telas cheias de informacao.

RESPONDA SOMENTE COM JSON VALIDO, neste formato:
{{
  "titulo": "titulo especifico para o video, ate 70 caracteres",
  "descricao": "descricao factual em 2 a 4 frases",
  "tags": ["8 a 12 tags"],
  "gancho_texto": "chamada curta",
  "texto_miniatura": "frase de impacto para miniatura, ate 6 palavras",
  "resumo_pesquisa": "resumo do conhecimento consolidado utilizado; indicar conferencia manual se depender de dado atual",
  "narracao_completa": "texto corrido de todo o video, com conectivos; as narracoes das cenas sao trechos exatos dele",
  "cenas": [
    {{
      "narracao": "trecho exato e consecutivo da narracao_completa",
      "visual": {{
        "type": "headline|stat|flow|timeline|comparison|chart|bullets|quote|definition",
        "midia_tipo": "pessoa|local|evento|conceito",
        "busca_wikimedia": "nome especifico para busca",
        "prompt_midia_ia": "conceptual illustration prompt in English",
        "kicker": "PALAVRA-CHAVE CURTA DO TEMA",
        "headline": "titulo visual curto",
        "subheadline": "complemento curto",
        "value": "valor principal somente se confirmado",
        "value_label": "o que o valor representa",
        "items": [{{"title":"rotulo", "body":"explicacao curta", "value":"valor opcional"}}],
        "steps": [{{"title":"etapa", "detail":"explicacao"}}],
        "events": [{{"date":"data", "title":"evento", "detail":"contexto"}}],
        "left": {{"title":"lado A", "body":"descricao"}},
        "right": {{"title":"lado B", "body":"descricao"}},
        "chart": {{"title":"titulo", "labels":["A","B"], "values":[10,20], "unit":"unidade"}},
        "quote": "citacao curta, somente se literal e confirmada",
        "attribution": "autor ou documento, se confirmado"
      }},
      "source_ids": ["S1"]
    }}
  ],
  "fontes_sugeridas": ["tipos de documentos ou fontes primarias a consultar manualmente, se necessario"],
  "pergunta_final": "pergunta especifica para estimular comentarios"
}}

Nao invente URLs nem apresente fontes como consultadas. Se sugerir documentos para checagem, identifique-os apenas como fontes sugeridas, nao como fontes lidas.
{REGRAS_NARRACAO}{LINGUAGEM_POPULAR}"""


def validar_narracao(roteiro: dict) -> str:
    """Garante que narracao_completa == juncao das cenas (ignorando pontuacao)."""
    norm = lambda t: " ".join(re.findall(r"\w+", (t or "").lower()))
    juntas = " ".join(str(c.get("narracao", "")).strip() for c in roteiro.get("cenas", []))
    completa = str(roteiro.get("narracao_completa") or "").strip()
    if not completa:
        return juntas
    if norm(completa) != norm(juntas):
        info("   aviso: narracao_completa diverge das cenas; usando a juncao das cenas.")
        return juntas
    return completa


def generate_script_without_search(channel: dict, topic: str, duration: int, category: str, config: dict) -> tuple[dict, list[dict[str, str]]]:
    """Tenta o Gemini; se falhar (cota, 503, chave, timeout), tenta as outras IAs."""
    import ia_fallback
    prompt = make_research_prompt(channel, topic, duration, category)
    erro_gemini = "sem chave GEMINI_API_KEY"
    if config.get("gemini_api_key"):
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(
                api_key=config["gemini_api_key"],
                http_options=types.HttpOptions(timeout=60000),  # 60 s
            )
            response = cv.gerar_conteudo_texto_com_fallback(
                client, config, prompt,
                types.GenerateContentConfig(response_mime_type="application/json", temperature=0.7),
                operacao="roteiro broadcast",
            )
            return ia_fallback.extrair_json(getattr(response, "text", None) or ""), []
        except Exception as exc:
            erro_gemini = str(exc)[:200]
    info(f"   Gemini indisponivel ({erro_gemini}). Tentando outras IAs...")
    try:
        return ia_fallback.gerar_roteiro(prompt, config, info), []
    except Exception as exc:
        raise BroadcastError(f"Gemini: {erro_gemini} | {exc}") from exc



def simulated_script(topic: str) -> dict[str, Any]:
    return {
        "titulo": f"Entenda: {topic[:58]}",
        "descricao": "Video demonstrativo do motor Broadcast News. Conteudo simulado para validar o renderizador; nao utilizar como informacao factual.",
        "tags": ["demonstracao", "broadcast news", "explicador", "motion graphics"],
        "gancho_texto": "O que esta por tras disso?",
        "resumo_pesquisa": "Roteiro simulado. Nenhuma pesquisa factual foi realizada.",
        "cenas": [
            {"narracao": f"O que realmente esta por tras de {topic}?", "visual": {"type": "headline", "kicker": "EXPLICADOR · DEMONSTRACAO", "headline": topic, "subheadline": "Uma simulacao visual do pacote jornalistico.", "items": [{"title": "FATO", "body": "O que esta confirmado"}, {"title": "CONTEXTO", "body": "O que ajuda a entender"}, {"title": "IMPACTO", "body": "O que observar"}]}},
            {"narracao": "Primeiro, precisamos separar o que e fato, o que e contexto e o que ainda esta em discussao.", "visual": {"type": "flow", "kicker": "COMO ANALISAR", "headline": "Tres camadas para entender o assunto", "steps": [{"title": "FATO", "detail": "O que pode ser confirmado"}, {"title": "CONTEXTO", "detail": "O que explica o cenario"}, {"title": "IMPACTO", "detail": "Quem pode ser afetado"}]}},
            {"narracao": "Depois, observamos os principais pontos e como eles se conectam. Os elementos visuais ajudam a acompanhar cada etapa.", "visual": {"type": "comparison", "kicker": "LEITURA DO CENARIO", "headline": "O que observar", "left": {"title": "PONTO DE PARTIDA", "body": "A situacao inicial e suas regras"}, "right": {"title": "PROXIMO PASSO", "body": "As consequencias que precisam ser verificadas"}}},
            {"narracao": "A conclusao depende de fontes confiaveis, datas e dados confirmados. Esta demonstracao mostra a identidade visual, nao uma analise factual.", "visual": {"type": "bullets", "kicker": "RESUMO", "headline": "Informacao com contexto", "items": [{"title": "Verifique", "body": "Consulte documentos e fontes primarias"}, {"title": "Compare", "body": "Separe propostas, regras e resultados"}, {"title": "Atualize", "body": "Observe datas e mudancas recentes"}]}}
        ]
    }


def normalize_script(script: dict[str, Any], sources: list[dict[str, str]]) -> dict[str, Any]:
    if not isinstance(script, dict):
        raise BroadcastError("O roteiro retornado nao e um objeto JSON.")
    scenes = script.get("cenas")
    if not isinstance(scenes, list) or len(scenes) < 4:
        raise BroadcastError("O roteiro Broadcast News precisa ter pelo menos quatro cenas.")
    normalized = []
    for index, scene in enumerate(scenes, 1):
        if not isinstance(scene, dict) or not str(scene.get("narracao", "")).strip():
            raise BroadcastError(f"A cena {index} nao possui narracao.")
        visual = scene.get("visual") if isinstance(scene.get("visual"), dict) else {}
        kind = str(visual.get("type") or "bullets").lower()
        if kind not in VISUAL_TYPES:
            kind = "bullets"
        safe_visual = {**visual, "type": kind}
        for list_key in ("items", "steps", "events"):
            value = safe_visual.get(list_key, [])
            safe_visual[list_key] = [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []
        for object_key in ("left", "right", "chart"):
            if not isinstance(safe_visual.get(object_key), dict):
                safe_visual[object_key] = {}
        normalized.append({
            "narracao": str(scene["narracao"]).strip(),
            "visual": safe_visual,
            "source_ids": scene.get("source_ids", []) if isinstance(scene.get("source_ids", []), list) else [],
        })
    result = {
        "titulo": str(script.get("titulo") or "Explicador Broadcast News")[:100],
        "descricao": str(script.get("descricao") or "")[:4000],
        "tags": script.get("tags") if isinstance(script.get("tags"), list) else [],
        "gancho_texto": cortar_texto(script.get("gancho_texto"), 160),
        "texto_miniatura": cortar_texto(script.get("texto_miniatura") or script.get("gancho_texto"), 60),
        "resumo_pesquisa": str(script.get("resumo_pesquisa") or ""),
        "cenas": normalized,
        "fontes": sources,
        "fontes_sugeridas": script.get("fontes_sugeridas", []) if isinstance(script.get("fontes_sugeridas", []), list) else [],
        "pergunta_final": str(script.get("pergunta_final") or ""),
    }
    result["narracao_completa"] = validar_narracao({**script, "cenas": normalized})
    return result


def font_path(bold: bool = False) -> str | None:
    candidates = []
    if sys.platform == "win32":
        candidates += [r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
                      r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf"]
    candidates += ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                   "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"]
    return next((x for x in candidates if Path(x).is_file()), None)


def get_font(size: int, bold: bool = False):
    path = font_path(bold)
    try:
        return ImageFont.truetype(path, size=size) if path else ImageFont.load_default()
    except OSError:
        return ImageFont.load_default()


def fit_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    words = str(text or "").split()
    if not words:
        return [""]
    lines: list[str] = []
    line = ""
    for word in words:
        test = f"{line} {word}".strip()
        if draw.textbbox((0, 0), test, font=font)[2] <= max_width or not line:
            line = test
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def draw_wrapped(draw, xy, text, font, fill, max_width, line_gap=8, max_lines=None):
    x, y = xy
    lines = fit_text(draw, str(text or ""), font, max_width)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        if lines:
            last = lines[-1]
            while last and draw.textbbox((0, 0), last + "…", font=font)[2] > max_width:
                last = last[:-1]
            lines[-1] = last.rstrip() + "…"
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        bbox = draw.textbbox((x, y), line or " ", font=font)
        y += max(1, bbox[3] - bbox[1]) + line_gap
    return y


def draw_round(draw, box, fill, outline=None, radius=24, width=2):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def gradient_background(width: int, height: int) -> Image.Image:
    top = (5, 19, 39)
    bottom = (10, 51, 88)
    image = Image.new("RGB", (width, height), top)
    draw = ImageDraw.Draw(image)
    for y in range(height):
        t = y / max(1, height - 1)
        color = tuple(round(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
        draw.line((0, y, width, y), fill=color)
    grid = (18, 67, 104)
    step = max(32, width // 32)
    for x in range(0, width, step):
        draw.line((x, 0, x, height), fill=grid, width=1)
    for y in range(0, height, step):
        draw.line((0, y, width, y), fill=grid, width=1)
    return image


def _card(draw, x, y, w, h, title, body="", value="", accent=(30, 190, 230), compact=False):
    draw_round(draw, (x, y, x + w, y + h), (10, 34, 60), (31, 90, 127), radius=max(14, w // 70), width=2)
    draw.rounded_rectangle((x, y, x + 10, y + h), radius=5, fill=accent)
    pad = max(18, w // 22)
    title_font = get_font(max(19, min(34, w // 12)), True)
    body_font = get_font(max(16, min(26, w // 15)))
    value_font = get_font(max(32, min(62, w // 6)), True)
    cy = y + pad
    if value:
        draw.text((x + pad, cy), str(value)[:36], font=value_font, fill=(246, 250, 255))
        cy += value_font.size + 8
    cy = draw_wrapped(draw, (x + pad, cy), title, title_font, (65, 216, 242), w - 2 * pad, max_lines=2)
    if body and not compact:
        draw_wrapped(draw, (x + pad, cy + 8), body, body_font, (211, 225, 239), w - 2 * pad, max_lines=3)


def draw_visual(draw: ImageDraw.ImageDraw, visual: dict, x: int, y: int, width: int, height: int, vertical: bool):
    """Desenha apenas o componente principal; titulo/subtitulo ja aparecem no topo."""
    kind = visual.get("type", "bullets")
    accent = (30, 192, 230)
    items = visual.get("items") if isinstance(visual.get("items"), list) else []
    steps = visual.get("steps") if isinstance(visual.get("steps"), list) else []
    events = visual.get("events") if isinstance(visual.get("events"), list) else []
    pad = 28 if not vertical else 24

    if kind == "stat":
        value = str(visual.get("value") or "DADO")[:28]
        label = str(visual.get("value_label") or visual.get("detail") or "Indicador em destaque")
        draw_round(draw, (x, y, x + width, y + height), (7, 30, 56), (28, 132, 181), radius=28, width=3)
        draw.text((x + pad, y + pad), "INDICADOR EM DESTAQUE", font=get_font(20 if not vertical else 18, True), fill=(64, 205, 235))
        value_font = get_font(100 if not vertical else 88, True)
        draw_wrapped(draw, (x + pad, y + 95), value, value_font, (255, 201, 63), width - 2 * pad, max_lines=2)
        draw_wrapped(draw, (x + pad, y + (height * .62)), label, get_font(34 if not vertical else 29, True), (246, 250, 255), width - 2 * pad, max_lines=3)
        return

    if kind == "chart":
        chart = visual.get("chart") if isinstance(visual.get("chart"), dict) else {}
        labels = chart.get("labels") if isinstance(chart.get("labels"), list) else []
        values = chart.get("values") if isinstance(chart.get("values"), list) else []
        pairs = []
        for label, value in zip(labels[:6], values[:6]):
            try:
                pairs.append((str(label), float(value)))
            except (TypeError, ValueError):
                continue
        draw_round(draw, (x, y, x + width, y + height), (7, 30, 56), (28, 132, 181), radius=24, width=2)
        if not pairs:
            draw_wrapped(draw, (x + pad, y + pad), "Sem serie numerica confirmada para este quadro. O conteudo sera apresentado em formato explicativo.", get_font(30, True), (236, 244, 250), width - 2 * pad, max_lines=4)
            return
        max_value = max(max(v for _, v in pairs), 1)
        top = y + pad
        label_w = int(width * (0.27 if not vertical else 0.30))
        available = height - 2 * pad
        gap = 16 if not vertical else 18
        bar_h = max(28, int((available - gap * (len(pairs) - 1)) / len(pairs)))
        for i, (label, value) in enumerate(pairs):
            yy = top + i * (bar_h + gap)
            draw_wrapped(draw, (x + pad, yy + 2), label[:26], get_font(20 if not vertical else 18, True), (215, 231, 244), label_w - 12, max_lines=2)
            bx = x + pad + label_w
            bw = width - label_w - 3 * pad - 70
            draw.rounded_rectangle((bx, yy + 3, bx + bw, yy + bar_h - 3), radius=(bar_h - 6)//2, fill=(18, 59, 88))
            fill_w = max(8, int(bw * value / max_value))
            draw.rounded_rectangle((bx, yy + 3, bx + fill_w, yy + bar_h - 3), radius=(bar_h - 6)//2, fill=(21, 185, 226))
            draw.text((bx + bw + 14, yy + 4), f"{value:g}", font=get_font(19, True), fill=(255, 205, 91))
        return

    if kind in ("flow", "timeline"):
        entries = steps if kind == "flow" else events
        entries = entries or items
        entries = entries[:5]
        if not entries:
            entries = [{"title": "Contexto", "detail": "A informacao principal e suas etapas."}]
        if vertical:
            gap = 18
            card_h = max(125, int((height - gap * (len(entries) - 1)) / len(entries)))
            cy = y
            for i, entry in enumerate(entries):
                title = entry.get("title") or entry.get("date") or f"Etapa {i + 1}"
                body = entry.get("detail") or entry.get("body") or ""
                _card(draw, x, cy, width, card_h, title, body, entry.get("value", ""), accent=(255, 94, 88) if kind == "timeline" else accent)
                cy += card_h + gap
        else:
            gap = 22
            cw = (width - gap * (len(entries) - 1)) // len(entries)
            card_h = min(height - 26, 330)
            cy = y + max(12, (height - card_h) // 2)
            for i, entry in enumerate(entries):
                xx = x + i * (cw + gap)
                title = entry.get("title") or entry.get("date") or f"Etapa {i + 1}"
                body = entry.get("detail") or entry.get("body") or ""
                _card(draw, xx, cy, cw, card_h, title, body, entry.get("value", ""), accent=(255, 94, 88) if kind == "timeline" else accent)
                if i < len(entries) - 1:
                    mid = xx + cw + gap // 2
                    draw.line((mid - 8, cy + card_h // 2, mid + 8, cy + card_h // 2), fill=(255, 201, 63), width=5)
        return

    if kind == "comparison":
        left = visual.get("left") if isinstance(visual.get("left"), dict) else {}
        right = visual.get("right") if isinstance(visual.get("right"), dict) else {}
        gap = 24
        cw = (width - gap) // 2
        ch = min(height - 20, 390 if not vertical else 530)
        cy = y + max(10, (height - ch) // 2)
        _card(draw, x, cy, cw, ch, left.get("title", "Ponto A"), left.get("body", ""), left.get("value", ""), accent=(36, 190, 228))
        _card(draw, x + cw + gap, cy, cw, ch, right.get("title", "Ponto B"), right.get("body", ""), right.get("value", ""), accent=(255, 91, 88))
        return

    if kind == "quote":
        quote = str(visual.get("quote") or visual.get("subheadline") or visual.get("headline") or "")
        attribution = str(visual.get("attribution") or "Atribuicao nao informada")
        draw_round(draw, (x, y, x + width, y + height), (7, 30, 56), (28, 132, 181), radius=28, width=3)
        draw.text((x + pad, y + pad - 8), "“", font=get_font(100, True), fill=(255, 201, 63))
        draw_wrapped(draw, (x + pad + 35, y + 110), quote, get_font(37 if not vertical else 32, True), (247, 250, 253), width - 2 * pad - 35, max_lines=5)
        draw_wrapped(draw, (x + pad, y + height - 78), attribution, get_font(22), (110, 206, 235), width - 2 * pad, max_lines=2)
        return

    if kind == "definition":
        term = str(visual.get("term") or visual.get("headline") or "Conceito")
        definition = str(visual.get("definition") or visual.get("subheadline") or "")
        _card(draw, x, y + 12, width, height - 24, term, definition, visual.get("value", ""))
        return

    if kind == "headline":
        body = str(visual.get("key_message") or visual.get("subheadline") or "Acompanhe o fato, o contexto e o que ainda precisa ser confirmado.")
        draw_round(draw, (x, y + 10, x + width, y + height - 10), (7, 30, 56), (28, 132, 181), radius=28, width=3)
        if vertical:
            # Coluna principal e tres marcadores editoriais em composicao vertical.
            draw.text((x + pad, y + pad + 8), "O PONTO CENTRAL", font=get_font(21, True), fill=(64, 205, 235))
            draw_wrapped(draw, (x + pad, y + 74), body, get_font(35, True), (247, 250, 253), width - 2 * pad, max_lines=5)
            labels = items[:3] or [
                {"title": "FATO", "body": "O que esta confirmado"},
                {"title": "CONTEXTO", "body": "O que ajuda a entender"},
                {"title": "IMPACTO", "body": "O que observar daqui em diante"},
            ]
            cy = y + int(height * .52)
            card_h = max(110, int((height * .43 - 24) / min(3, len(labels))))
            for item in labels[:3]:
                _card(draw, x + pad, cy, width - 2 * pad, card_h, item.get("title", "Ponto-chave"), item.get("body", ""), accent=accent, compact=False)
                cy += card_h + 12
        else:
            left_w = int(width * .65)
            draw.text((x + pad, y + pad + 8), "O PONTO CENTRAL", font=get_font(21, True), fill=(64, 205, 235))
            draw_wrapped(draw, (x + pad, y + 78), body, get_font(39, True), (247, 250, 253), left_w - 2 * pad, max_lines=5)
            # Globo estilizado sem mapa factual: recurso grafico de pacote jornalistico.
            panel_x = x + left_w + 12
            panel_w = width - left_w - pad - 12
            panel_y = y + 24
            panel_h = height - 48
            draw_round(draw, (panel_x, panel_y, panel_x + panel_w, panel_y + panel_h), (9, 45, 75), (30, 115, 155), radius=24, width=2)
            radius = min(panel_w // 3, panel_h // 3, 118)
            cx = panel_x + panel_w // 2
            cy = panel_y + radius + 40
            draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=(44, 199, 230), width=5)
            draw.ellipse((cx - radius // 2, cy - radius, cx + radius // 2, cy + radius), outline=(44, 199, 230), width=3)
            draw.arc((cx - radius, cy - radius // 2, cx + radius, cy + radius // 2), 0, 360, fill=(44, 199, 230), width=3)
            draw.line((cx - radius, cy, cx + radius, cy), fill=(44, 199, 230), width=3)
            labels = items[:3] or [
                {"title": "FATO", "body": "O que esta confirmado"},
                {"title": "CONTEXTO", "body": "O que ajuda a entender"},
                {"title": "IMPACTO", "body": "O que observar"},
            ]
            card_h = max(58, int((panel_h - 2 * radius - 70) / 3))
            cy2 = panel_y + 2 * radius + 55
            for item in labels[:3]:
                draw.rounded_rectangle((panel_x + 18, cy2, panel_x + panel_w - 18, cy2 + card_h - 8), radius=10, fill=(16, 73, 108))
                draw.text((panel_x + 30, cy2 + 5), str(item.get("title", "PONTO"))[:20].upper(), font=get_font(17, True), fill=(255, 201, 63))
                draw_wrapped(draw, (panel_x + 30, cy2 + 28), str(item.get("body", "")), get_font(15, False), (224, 238, 247), panel_w - 60, max_lines=2)
                cy2 += card_h
        return

    # bullets: cartoes equilibrados; nao deixa um unico bloco de texto ocupar a tela.
    if not items:
        items = [{"title": "Ponto principal", "body": "Fato, contexto e impacto devem aparecer de forma clara."}]
    count = min(3 if not vertical else 4, len(items))
    gap = 18 if not vertical else 16
    if vertical:
        card_h = max(145, int((height - gap * (count - 1)) / count))
        cy = y
        for item in items[:count]:
            _card(draw, x, cy, width, card_h, item.get("title", "Ponto-chave"), item.get("body", ""), item.get("value", ""))
            cy += card_h + gap
    else:
        cw = (width - gap * (count - 1)) // count
        card_h = min(height - 20, 350)
        cy = y + max(10, (height - card_h) // 2)
        for i, item in enumerate(items[:count]):
            _card(draw, x + i * (cw + gap), cy, cw, card_h, item.get("title", "Ponto-chave"), item.get("body", ""), item.get("value", ""))

def create_scene_card(scene: dict[str, Any], index: int, total: int, channel_name: str, category: str, sources: list[dict[str, str]], fmt: str, destination: Path) -> None:
    width, height = WIDTHS[fmt]
    vertical = fmt == "9x16"
    image = gradient_background(width, height)
    draw = ImageDraw.Draw(image)
    margin = int(width * (0.055 if not vertical else 0.065))
    header_h = 112 if not vertical else 150
    accent_red = (233, 57, 67)
    accent_cyan = (30, 192, 230)
    footer_h = 150 if not vertical else 245
    footer_y = height - footer_h

    # Faixa superior de identidade jornalistica.
    draw.rectangle((0, 0, width, header_h), fill=(4, 13, 29))
    draw.rectangle((0, header_h - 7, width, header_h), fill=accent_cyan)
    dot = 18 if not vertical else 20
    draw.ellipse((margin, int(header_h * .38), margin + dot, int(header_h * .38) + dot), fill=accent_red)
    header_font = get_font(23 if not vertical else 22, True)
    draw.text((margin + 34, int(header_h * .24)), "BROADCAST  /  EXPLICADOR", font=header_font, fill=(225, 240, 250))
    brand = str(channel_name or "CANAL").upper()[:24]
    brand_font = get_font(22 if not vertical else 20, True)
    brand_box = draw.textbbox((0, 0), brand, font=brand_font)
    draw.text((width - margin - (brand_box[2] - brand_box[0]), int(header_h * .24)), brand, font=brand_font, fill=(110, 200, 230))

    visual = scene.get("visual") if isinstance(scene.get("visual"), dict) else {}
    kicker = str(visual.get("kicker") or category or "INFORMACAO")[:46].upper()
    kicker_y = header_h + (34 if not vertical else 44)
    kicker_font = get_font(19 if not vertical else 20, True)
    kicker_w = min(width - 2 * margin, max(250, draw.textbbox((0, 0), kicker, font=kicker_font)[2] + 30))
    draw.rounded_rectangle((margin, kicker_y, margin + kicker_w, kicker_y + 42), radius=9, fill=accent_red)
    draw.text((margin + 14, kicker_y + 8), kicker[:36], font=kicker_font, fill=(255, 255, 255))

    title = str(visual.get("headline") or (scene.get("narracao", "").split(".")[0] if scene.get("narracao") else "O que esta acontecendo?"))
    title_y = kicker_y + 66
    title_font = get_font(54 if not vertical else 48, True)
    title_max = int(width - 2 * margin)
    title_max_lines = 2 if not vertical else 3
    lines = fit_text(draw, title, title_font, title_max)[:title_max_lines]
    for line in lines:
        draw.text((margin, title_y), line, font=title_font, fill=(248, 251, 255))
        bbox = draw.textbbox((margin, title_y), line, font=title_font)
        title_y += (bbox[3] - bbox[1]) + 7
    title_y += 14

    sub = str(visual.get("subheadline") or "")
    if sub:
        sub_font = get_font(25 if not vertical else 24)
        title_y = draw_wrapped(draw, (margin, title_y), sub, sub_font, (160, 201, 226), width - 2 * margin, line_gap=5, max_lines=2)
        title_y += 22

    content_y = title_y + 8
    content_h = max(220, footer_y - content_y - 24)
    draw_visual(draw, visual, margin, content_y, width - 2 * margin, content_h, vertical)

    # Rodape com fonte e ticker editorial.
    draw.rectangle((0, footer_y, width, height), fill=(3, 12, 27))
    draw.rectangle((0, footer_y, width, footer_y + 7), fill=accent_red)
    source_names = [s.get("title", "Fonte") for s in sources[:3]]
    source_line = (
        "FONTES: " + " · ".join(source_names)
        if source_names
        else "SEM FONTES CONSULTADAS AUTOMATICAMENTE - CONFIRA ANTES DE PUBLICAR"
    )
    source_font = get_font(17 if not vertical else 18, True)
    draw_wrapped(draw, (margin, footer_y + 25), source_line[:190], source_font, (163, 198, 221), width - 2 * margin, max_lines=2)
    ticker_y = height - 57
    draw.rectangle((0, ticker_y - 8, width, height), fill=(10, 67, 103))
    ticker_text = f"{category.upper()}   •   FATOS   •   CONTEXTO   •   DADOS   •   FONTES   •   {index:02d}/{total:02d}"
    draw.text((margin, ticker_y), ticker_text[:160], font=get_font(19 if not vertical else 18, True), fill=(247, 250, 253))
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, format="PNG", optimize=True)

def render_scene_clip(image_path: Path, duration: float, width: int, height: int, destination: Path) -> None:
    if shutil.which("ffmpeg") is None:
        raise BroadcastError("FFmpeg nao encontrado no PATH.")
    frames = max(1, int(round(duration * FPS)))
    zoom_filter = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},"
        f"zoompan=z='min(1+on*0.00010,1.012)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"d=1:s={width}x{height}:fps={FPS},format=yuv420p"
    )
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-loop", "1", "-framerate", str(FPS), "-i", str(image_path),
        "-vf", zoom_filter, "-frames:v", str(frames),
        "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", str(destination),
    ]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise BroadcastError("FFmpeg falhou ao renderizar um cartao: " + (result.stderr or "")[-900:])


# ---------------------------------------------------------------------------
# Midia de apoio fornecida pelo usuario
# ---------------------------------------------------------------------------

def find_scene_media(project_dir: Path, index: int) -> Path | None:
    """Procura uma midia manual em imagens/01.mp4, imagens/01.png etc."""
    folder = project_dir / "imagens"

    for extension in (".mp4", ".mov", ".webm", ".mkv", ".png", ".jpg", ".jpeg", ".webp"):
        candidate = folder / f"{index:02d}{extension}"
        if candidate.is_file():
            return candidate

    return None


def create_media_overlay(
    scene: dict[str, Any],
    index: int,
    total: int,
    channel_name: str,
    category: str,
    fmt: str,
    destination: Path,
) -> None:
    """Cria uma tarja transparente para usar sobre foto ou video."""
    width, height = WIDTHS[fmt]
    vertical = fmt == "9x16"

    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    margin = int(width * 0.055)
    header_h = 92 if not vertical else 110
    footer_h = 220 if not vertical else 300
    footer_y = height - footer_h

    draw.rectangle((0, 0, width, header_h), fill=(5, 5, 5, 225))
    draw.rectangle((0, header_h - 5, width, header_h), fill=(255, 204, 48, 255))

    brand = str(channel_name or "CANAL").upper()[:28]
    draw_wrapped(
        draw,
        (margin, 25),
        brand,
        get_font(25 if not vertical else 27, True),
        (240, 248, 255, 255),
        int(width * 0.65),
        max_lines=1,
    )

    counter = f"{index:02d}/{total:02d}"
    counter_font = get_font(23, True)
    counter_box = draw.textbbox((0, 0), counter, font=counter_font)
    draw.text(
        (width - margin - (counter_box[2] - counter_box[0]), 27),
        counter,
        font=counter_font,
        fill=(255, 204, 48, 255),
    )

    draw.rectangle((0, footer_y, width, height), fill=(5, 5, 5, 235))
    draw.rectangle((0, footer_y, width, footer_y + 6), fill=(255, 204, 48, 255))

    visual = scene.get("visual") if isinstance(scene.get("visual"), dict) else {}
    kicker = str(visual.get("kicker") or category or "EXPLICADOR").upper()[:45]
    title = str(visual.get("headline") or "").strip()

    if not title:
        title = str(scene.get("narracao") or "Entenda o assunto").split(".")[0]

    draw_wrapped(
        draw,
        (margin, footer_y + 21),
        kicker,
        get_font(20 if not vertical else 22, True),
        (255, 204, 48, 255),
        width - 2 * margin,
        max_lines=1,
    )

    draw_wrapped(
        draw,
        (margin, footer_y + 61),
        title,
        get_font(45 if not vertical else 43, True),
        (250, 252, 255, 255),
        width - 2 * margin,
        line_gap=8,
        max_lines=2 if not vertical else 3,
    )

    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, format="PNG")


def render_media_clip(
    media_path: Path,
    overlay_path: Path,
    duration: float,
    width: int,
    height: int,
    destination: Path,
) -> None:
    """Renderiza imagem ou video com a tarja jornalistica sobreposta."""
    frames = max(1, round(duration * FPS))
    is_video = media_path.suffix.lower() in cv.EXT_VIDEO

    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]

    if is_video:
        command += ["-stream_loop", "-1", "-i", str(media_path.resolve())]
    else:
        command += [
            "-loop", "1",
            "-framerate", str(FPS),
            "-i", str(media_path.resolve()),
        ]

    command += [
        "-loop", "1",
        "-framerate", str(FPS),
        "-i", str(overlay_path.resolve()),
    ]

    filters = (
        f"[0:v]scale={width}:{height}:"
        f"force_original_aspect_ratio=increase,"
        f"crop={width}:{height},"
        f"fps={FPS},setsar=1[background];"
        f"[1:v]format=rgba,fade=t=in:st=0:d=0.45:alpha=1[overlay];"
        f"[background][overlay]overlay=0:0:format=auto,"
        f"format=yuv420p[video]"
    )

    command += [
        "-filter_complex", filters,
        "-map", "[video]",
        "-an",
        "-frames:v", str(frames),
        "-r", str(FPS),
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        str(destination.resolve()),
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if result.returncode != 0:
        raise BroadcastError(
            f"FFmpeg falhou ao renderizar a midia {media_path.name}: "
            + (result.stderr or "")[-1200:]
        )


# ---------------------------------------------------------------------------
# Midias automaticas: Wikimedia Commons e ilustracao conceitual
# ---------------------------------------------------------------------------

def preparar_midias_automaticas(
    script: dict,
    project_dir: Path,
    config: dict,
    simular: bool,
) -> None:
    """Busca midias e registra procedencia. Nao garante identificacao correta."""
    if simular:
        info("   simulacao: busca externa e Cloudflare desativados.")
        return

    import html
    import unicodedata
    import urllib.parse
    import urllib.request

    pasta = project_dir / "imagens"
    pasta.mkdir(parents=True, exist_ok=True)
    registro_path = project_dir / "midias_automaticas.json"

    if registro_path.exists():
        try:
            registro = load_json(registro_path)
        except BroadcastError:
            info("   aviso: nao foi possivel ler o registro anterior de midias.")
            registro = {"midias": []}
    else:
        registro = {"midias": []}

    itens = registro.get("midias")
    if not isinstance(itens, list):
        itens = []

    por_cena = {
        item["cena"]: item
        for item in itens
        if isinstance(item, dict) and isinstance(item.get("cena"), int)
    }

    def salvar_registro():
        save_json(
            registro_path,
            {"midias": [por_cena[k] for k in sorted(por_cena)]},
        )

    def limpar_html(valor):
        valor = re.sub(r"<[^>]+>", " ", str(valor or ""))
        return " ".join(html.unescape(valor).split())

    def normalizar(valor):
        valor = unicodedata.normalize("NFKD", str(valor or ""))
        valor = "".join(c for c in valor if not unicodedata.combining(c))
        return re.sub(r"[^a-z0-9]+", " ", valor.lower()).strip()

    def meta(metadata, nome):
        campo = metadata.get(nome)
        return campo.get("value", "") if isinstance(campo, dict) else ""

    def licenca_aceita(url):
        partes = urllib.parse.urlparse(str(url or "").strip())
        if partes.scheme not in ("http", "https"):
            return False
        if partes.netloc.lower() not in (
            "creativecommons.org",
            "www.creativecommons.org",
        ):
            return False

        caminho = partes.path.lower().rstrip("/")
        return bool(
            re.fullmatch(r"/licenses/by/(3\.0|4\.0)", caminho)
            or caminho in (
                "/publicdomain/zero/1.0",
                "/publicdomain/mark/1.0",
            )
        )

    def buscar_commons(termo):
        parametros = {
            "action": "query",
            "generator": "search",
            "gsrsearch": termo,
            "gsrnamespace": "6",
            "gsrlimit": "15",
            "prop": "imageinfo",
            "iiprop": "url|mime|extmetadata",
            "format": "json",
            "formatversion": "2",
        }
        url = (
            "https://commons.wikimedia.org/w/api.php?"
            + urllib.parse.urlencode(parametros)
        )
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "BroadcastNewsMediaBot/1.0 (Wikimedia media search)"
            },
        )

        with urllib.request.urlopen(req, timeout=25) as resposta:
            dados = json.loads(resposta.read().decode("utf-8"))

        palavras = [
            p for p in normalizar(termo).split()
            if len(p) >= 3
        ]
        if not palavras:
            return None

        paginas = dados.get("query", {}).get("pages", [])
        paginas.sort(key=lambda p: p.get("index", 999))

        extensoes = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
        }

        for pagina in paginas:
            imagens = pagina.get("imageinfo") or []
            if not imagens:
                continue

            imagem = imagens[0]
            extensao = extensoes.get(str(imagem.get("mime", "")).lower())
            if not extensao:
                continue

            metadata = imagem.get("extmetadata") or {}
            licenca_url = meta(metadata, "LicenseUrl")
            autor = limpar_html(meta(metadata, "Artist"))

            if not licenca_aceita(licenca_url) or not autor:
                continue

            texto_verificacao = normalizar(
                pagina.get("title", "") + " "
                + limpar_html(meta(metadata, "ImageDescription"))
            )

            correspondencias = sum(
                1 for palavra in palavras if palavra in texto_verificacao
            )

            if correspondencias < min(2, len(palavras)):
                continue

            url_arquivo = imagem.get("url") or ""
            pagina_arquivo = imagem.get("descriptionurl") or ""

            if not url_arquivo or not pagina_arquivo:
                continue

            return {
                "url_arquivo": url_arquivo,
                "pagina": pagina_arquivo,
                "titulo": pagina.get("title", ""),
                "autor": autor,
                "licenca": limpar_html(meta(metadata, "LicenseShortName")),
                "licenca_url": licenca_url,
                "extensao": extensao,
            }

        return None

    def baixar_imagem(url, destino):
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "BroadcastNewsMediaBot/1.0 (Wikimedia media search)"
            },
        )
        parcial = destino.with_name(destino.name + ".part")
        limite = 20 * 1024 * 1024

        try:
            with urllib.request.urlopen(req, timeout=60) as resposta:
                with parcial.open("wb") as saida:
                    total = 0
                    while True:
                        bloco = resposta.read(64 * 1024)
                        if not bloco:
                            break
                        total += len(bloco)
                        if total > limite:
                            raise ValueError("Imagem maior que 20 MB.")
                        saida.write(bloco)

            with Image.open(parcial) as imagem:
                imagem.verify()

            parcial.replace(destino)
        finally:
            parcial.unlink(missing_ok=True)

    for indice, cena in enumerate(script.get("cenas", []), 1):
        if find_scene_media(project_dir, indice):
            info(f"   cena {indice}: midia existente preservada.")
            continue

        visual = cena.get("visual")
        if not isinstance(visual, dict):
            visual = {}

        tipo = str(visual.get("midia_tipo") or "").strip().lower()
        busca = str(visual.get("busca_wikimedia") or "").strip()
        prompt = str(visual.get("prompt_midia_ia") or "").strip()

        resultado = None

        if busca:
            info(f"   cena {indice}: buscando imagem real: {busca[:100]}")
            try:
                resultado = buscar_commons(busca)
            except Exception as exc:
                info(f"   cena {indice}: busca indisponivel: {str(exc)[:140]}")

        if resultado:
            destino = pasta / f"{indice:02d}{resultado['extensao']}"
            try:
                baixar_imagem(resultado["url_arquivo"], destino)
                por_cena[indice] = {
                    "cena": indice,
                    "arquivo": destino.name,
                    "tipo": "imagem obtida no Wikimedia Commons",
                    "busca": busca,
                    "titulo": resultado["titulo"],
                    "autor": resultado["autor"],
                    "pagina": resultado["pagina"],
                    "licenca": resultado["licenca"],
                    "licenca_url": resultado["licenca_url"],
                }
                salvar_registro()
                info(f"   cena {indice}: imagem encontrada.")
                continue
            except Exception as exc:
                info(f"   cena {indice}: falha no download: {str(exc)[:140]}")

        if (
            tipo == "conceito"
            and prompt
            and config.get("cloudflare_account_id")
            and config.get("cloudflare_api_token")
        ):
            info(f"   cena {indice}: tentando ilustracao no Cloudflare.")
            try:
                caminho = cv.imagem_cloudflare(
                    config["cloudflare_account_id"],
                    config["cloudflare_api_token"],
                    config.get(
                        "modelo_cloudflare",
                        "@cf/black-forest-labs/flux-1-schnell",
                    ),
                    prompt + (
                        ", conceptual editorial illustration, no text, "
                        "no logo, no identifiable real person"
                    ),
                    pasta / f"{indice:02d}",
                    config.get("cloudflare_steps", 4),
                )
                por_cena[indice] = {
                    "cena": indice,
                    "arquivo": caminho.name,
                    "tipo": "ilustracao gerada por IA",
                    "provedor": "Cloudflare",
                }
                salvar_registro()
                info(f"   cena {indice}: ilustracao gerada.")
                continue
            except Exception as exc:
                info(f"   cena {indice}: Cloudflare indisponivel: {str(exc)[:140]}")

        info(f"   cena {indice}: sem midia; usando cartao grafico.")

    salvar_registro()


def acrescentar_creditos_midias(project_dir: Path) -> None:
    registro_path = project_dir / "midias_automaticas.json"
    publicacao_path = project_dir / "publicacao.txt"

    if not registro_path.exists() or not publicacao_path.exists():
        return

    try:
        registro = load_json(registro_path)
    except BroadcastError:
        return

    midias = registro.get("midias") or []
    if not midias:
        return

    with publicacao_path.open("a", encoding="utf-8") as arquivo:
        arquivo.write("\n\nMIDIAS — CONFIRA IDENTIFICACAO E CREDITOS\n")

        for item in midias:
            arquivo.write(
                f"\nCena {item.get('cena', '?')}: "
                f"{item.get('tipo', '')}\n"
            )

            for chave, rotulo in (
                ("titulo", "Arquivo"),
                ("autor", "Autor"),
                ("pagina", "Origem"),
                ("licenca", "Licenca"),
                ("licenca_url", "Link da licenca"),
                ("provedor", "Provedor"),
            ):
                valor = item.get(chave)
                if valor:
                    arquivo.write(f"  {rotulo}: {valor}\n")

        arquivo.write(
            "\nConfira cada imagem e as exigencias da licenca "
            "antes de publicar.\n"
        )


def render_format(script: dict, durations: list[float], narration: Path, project_dir: Path, fmt: str, channel: dict, category: str) -> Path:
    width, height = WIDTHS[fmt]
    title_slug = slug(script["titulo"])
    output_dir = project_dir / "saida"
    output_dir.mkdir(parents=True, exist_ok=True)
    final = output_dir / f"{title_slug}_{fmt}.mp4"
    if final.exists() and final.stat().st_size > 20_000:
        info(f"   [{fmt}] arquivo final ja existe; reaproveitando.")
        return final
    work_dir = project_dir / "broadcast_assets" / fmt
    work_dir.mkdir(parents=True, exist_ok=True)
    clips_dir = work_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    clip_paths = []
    sources = script.get("fontes", [])
    channel_name = str(channel.get("nome", "Canal"))
    total = len(script["cenas"])
    for index, (scene, duration) in enumerate(zip(script["cenas"], durations), 1):
        card = work_dir / f"cena_{index:03d}.png"
        if not card.exists():
            create_scene_card(scene, index, total, channel_name, category, sources, fmt, card)
        clip = clips_dir / f"cena_{index:03d}.mp4"
        media = find_scene_media(project_dir, index)

        if media:
            overlay = work_dir / f"tarja_{index:03d}.png"
            create_media_overlay(
                scene,
                index,
                total,
                channel_name,
                category,
                fmt,
                overlay,
            )

            info(f"   [{fmt}] renderizando midia da cena {index}/{total}: {media.name}")
            render_media_clip(media, overlay, duration, width, height, clip)

        elif not clip.exists() or clip.stat().st_size < 10_000:
            info(f"   [{fmt}] renderizando cartao {index}/{total}")
            render_scene_clip(card, duration, width, height, clip)

        clip_paths.append(clip)

    concat_file = clips_dir / "concat.txt"
    concat_file.write_text("\n".join(f"file '{p.name}'" for p in clip_paths) + "\n", encoding="utf-8")
    silent = work_dir / "video_sem_audio.mp4"
    concat = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", concat_file.name,
         "-c", "copy", "-movflags", "+faststart", str(silent)],
        cwd=clips_dir, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if concat.returncode != 0:
        raise BroadcastError("Nao foi possivel unir as cenas: " + (concat.stderr or "")[-900:])

    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(silent), "-i", str(narration),
        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest", "-movflags", "+faststart", str(final),
    ]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise BroadcastError("Nao foi possivel adicionar a narracao: " + (result.stderr or "")[-900:])
    return final


def write_sources(project_dir: Path, sources: list[dict[str, str]]) -> None:
    save_json(project_dir / "fontes.json", {"fontes": sources, "acessado_em": time.strftime("%Y-%m-%d %H:%M:%S")})
    text = ("FONTES CONSULTADAS\n\n" + "\n".join(
        f"[{item.get('id','S?')}] {item.get('title','Fonte')}\n{item.get('url','')}" for item in sources
    ) + "\n") if sources else "PESQUISA WEB NAO UTILIZADA. Roteiro baseado no conhecimento consolidado do modelo; conferir fontes primarias e atualizacoes antes de publicar.\n"
    (project_dir / "fontes.txt").write_text(text, encoding="utf-8")


def create_project_dir(channel_name: str, topic: str, project_arg: str | None, delivery_format: str | None = None) -> Path:
    projects_root = (ROOT / "projetos").resolve()
    channel_root = (projects_root / channel_name).resolve()
    if project_arg:
        project = Path(project_arg).expanduser()
        if not project.is_absolute():
            project = (ROOT / project).resolve()
        project = project.resolve()
        if project.parent != channel_root or not project.is_dir():
            raise BroadcastError("--projeto deve apontar para uma pasta existente diretamente dentro de projetos/<canal>/.")
        return project
    suffix = f"_{delivery_format}" if delivery_format in ("16x9", "9x16") else ""
    project = channel_root / f"{date.today().isoformat()}_{slug(topic)}{suffix}"
    project.mkdir(parents=True, exist_ok=True)
    return project

# ---------------------------------------------------------------------------
# Voz unica + alinhamento das cenas pelos segundos
# ---------------------------------------------------------------------------

def duracao_audio(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    try:
        return float(r.stdout.strip())
    except ValueError as exc:
        raise BroadcastError(f"Nao foi possivel medir o audio {path.name}.") from exc


def _palavras(texto: str) -> list[str]:
    return re.findall(r"\w+", (texto or "").lower())


def tempos_palavras(audio: Path, modelo_nome: str = "small") -> list[tuple[float, float]] | None:
    """Tempo (inicio, fim) de cada palavra via faster-whisper. None se indisponivel."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        info("   faster-whisper nao instalado; alinhando cenas pelo tamanho do texto.")
        return None
    try:
        info(f"   alinhando cenas com Whisper ({modelo_nome})...")
        modelo = WhisperModel(modelo_nome, device="cpu", compute_type="int8")
        segs, _ = modelo.transcribe(str(audio), language="pt", word_timestamps=True)
        tempos = [(w.start, w.end) for s in segs for w in (s.words or [])]
        return tempos or None
    except Exception as exc:
        info(f"   Whisper falhou ({str(exc)[:120]}); alinhando pelo tamanho do texto.")
        return None


def alinhar_cenas(audio: Path, cenas: list[dict], total: float, modelo_whisper: str = "small") -> list[float]:
    """Retorna a duracao de cada cena; a soma e igual a duracao do audio."""
    contagens = [max(1, len(_palavras(c["narracao"]))) for c in cenas]
    soma = sum(contagens)
    tempos = tempos_palavras(audio, modelo_whisper)
    limites: list[float] = []
    acum = 0
    for i, n in enumerate(contagens[:-1]):
        acum += n
        if tempos:
            escala = len(tempos) / soma
            idx = max(0, min(int(round(acum * escala)) - 1, len(tempos) - 1))
            prox = min(idx + 1, len(tempos) - 1)
            corte = (tempos[idx][1] + tempos[prox][0]) / 2
        else:
            corte = total * acum / soma
        minimo = (limites[-1] if limites else 0.0) + 0.6
        limites.append(min(max(corte, minimo), total - 0.6 * (len(contagens) - 1 - i)))
    pontos = [0.0] + limites + [total]
    return [round(pontos[i + 1] - pontos[i], 3) for i in range(len(cenas))]


def gerar_voz_unica(script: dict, project_dir: Path, channel: dict, simular: bool) -> tuple[Path, list[float]]:
    """Gera UM audio com a narracao completa e calcula a duracao de cada cena."""
    pasta = project_dir / "voz_unica"
    pasta.mkdir(parents=True, exist_ok=True)
    roteiro_voz = {
        **script,
        "cenas": [{"narracao": script["narracao_completa"], "visual": {}, "source_ids": []}],
    }
    narration, _ = cv.gerar_voz(roteiro_voz, pasta, channel, simular)
    total = duracao_audio(narration)

    cache = project_dir / "tempos_cenas.json"
    if cache.exists():
        try:
            dados = load_json(cache)
            if dados.get("cenas") == len(script["cenas"]) and abs(dados.get("total", 0) - total) < 0.05:
                info("   tempos das cenas reaproveitados.")
                return narration, dados["duracoes"]
        except BroadcastError:
            pass

    duracoes = alinhar_cenas(narration, script["cenas"], total, channel.get("modelo_whisper", "small"))
    save_json(cache, {"cenas": len(script["cenas"]), "total": total, "duracoes": duracoes})
    for i, d in enumerate(duracoes, 1):
        info(f"   cena {i:02d}: {d:.2f}s")
    return narration, duracoes


def main() -> int:
    parser = argparse.ArgumentParser(description="Motor Broadcast News — explicadores baseados em fatos consolidados e motion graphics local")
    parser.add_argument("canal")
    parser.add_argument("tema")
    parser.add_argument("--categoria", default="noticias")
    parser.add_argument("--duracao", type=int, default=300)
    parser.add_argument("--formatos", default="16x9")
    parser.add_argument("--simular", action="store_true")
    parser.add_argument("--revisar", action="store_true")
    parser.add_argument("--entrega-format", choices=["16x9", "9x16"])
    parser.add_argument("--projeto")
    parser.add_argument("--voz-por-cena", action="store_true", help="modo antigo: um audio por cena")
    args = parser.parse_args()

    try:
        if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
            raise BroadcastError("FFmpeg e FFprobe precisam estar no PATH.")
        try:
            from PIL import Image  # noqa: F401
        except ImportError as exc:
            raise BroadcastError("Instale Pillow: py -m pip install Pillow") from exc

        channel = cv.carregar_canal(args.canal)
        config = cv.carregar_config()
        cv.PAUSA_CENA = float(channel.get("pausa_entre_cenas", 0.2))
        cv.PAUSA_GANCHO = float(channel.get("pausa_gancho", 0.8))
        formats = [x.strip() for x in args.formatos.split(",") if x.strip()]
        if not formats or any(x not in WIDTHS for x in formats):
            raise BroadcastError("Formatos aceitos: 16x9 e 9x16.")
        if args.duracao < 60 or args.duracao > 1200:
            raise BroadcastError("A duracao do Broadcast News deve ficar entre 60 segundos e 20 minutos.")

        project_dir = create_project_dir(args.canal, args.tema, args.projeto, args.entrega_format)
        info(f"Projeto: {project_dir}")
        roteiro_path = project_dir / "roteiro.json"
        research_path = project_dir / "pesquisa.json"
        sources: list[dict[str, str]] = []

        info("\n[1/5] Pesquisa e roteiro")
        if roteiro_path.exists():
            raw_script = load_json(roteiro_path)
            sources = raw_script.get("fontes", [])
            info("   roteiro.json existente; reutilizando o projeto salvo.")
        elif args.simular:
            raw_script = simulated_script(args.tema)
        else:
            raw_script, sources = generate_script_without_search(channel, args.tema, args.duracao, args.categoria, config)
        script = normalize_script(raw_script, sources)
        script = ensure_closing_question(script, args.categoria, args.tema, channel.get("tom", ""))
        script["narracao_completa"] = validar_narracao(script)
        save_json(roteiro_path, script)
        if not research_path.exists():
            save_json(research_path, {"resumo": script.get("resumo_pesquisa", ""), "fontes": sources,
                                      "modo": "sem pesquisa web; conhecimento consolidado do modelo"})
            write_sources(project_dir, sources)
        info(f"   titulo: {script['titulo']} ({len(script['cenas'])} cenas)")
        if args.revisar:
            info(f"   roteiro salvo para revisao: {roteiro_path}")
            return 0

        info("\n[2/5] Voz")
        if args.voz_por_cena or not channel.get("voz_unica", True):
            narration, durations = cv.gerar_voz(script, project_dir, channel, args.simular)
        else:
            narration, durations = gerar_voz_unica(script, project_dir, channel, args.simular)
        info(f"   narracao pronta: {narration.name}")

        info("\n[2.5/5] Busca automatica de midias")
        preparar_midias_automaticas(script, project_dir, config, args.simular)

        info("\n[3/5] Cartoes graficos")
        for fmt in formats:
            folder = project_dir / "broadcast_assets" / fmt
            folder.mkdir(parents=True, exist_ok=True)
            for i, scene in enumerate(script["cenas"], 1):
                card = folder / f"cena_{i:03d}.png"
                if not card.exists():
                    create_scene_card(scene, i, len(script["cenas"]), channel.get("nome", args.canal), args.categoria, sources, fmt, card)
        info("   cartoes graficos preparados para os formatos selecionados.")

        info("\n[4/5] Renderizacao e montagem")
        outputs = []
        for fmt in formats:
            output = render_format(script, durations, narration, project_dir, fmt, channel, args.categoria)
            cv.aplicar_branding_video(output, channel, fmt)
            outputs.append(output)
            info(f"   pronto: {output}")

        info("\n[5/5] Publicacao")
        cv.salvar_publicacao(script, project_dir)
        publication = project_dir / "publicacao.txt"
        with publication.open("a", encoding="utf-8") as handle:
            if sources:
                handle.write("\n\nFONTES CONSULTADAS\n")
                for source in sources:
                    handle.write(f"- {source.get('title','Fonte')}: {source.get('url','')}\n")
            else:
                handle.write("\n\nNOTA EDITORIAL: este roteiro foi gerado sem pesquisa web. Confira fontes primarias, datas, regras e dados atuais antes de publicar.\n")
                suggested = script.get("fontes_sugeridas", [])
                if suggested:
                    handle.write("Fontes sugeridas para checagem manual:\n" + "\n".join(f"- {x}" for x in suggested) + "\n")
        acrescentar_creditos_midias(project_dir)
        info("   fontes e arquivos de publicacao registrados.")
        info("\nPRONTO. Videos salvos em:")
        for output in outputs:
            info(f"   {output}")
        return 0
    except (BroadcastError, ValueError, OSError) as exc:
        info(f"ERRO: {exc}")
        return 1
    except SystemExit as exc:
        code = int(exc.code or 1) if isinstance(exc.code, int) or exc.code is None else 1
        info("ERRO: O pipeline legado encerrou a execucao com uma falha. Confira as mensagens anteriores.")
        return code


if __name__ == "__main__":
    raise SystemExit(main())
