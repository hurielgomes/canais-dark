"""temas_m1.py - temas visuais do M1 (paleta, modo claro/escuro, bloom, legenda, HUD).

Prioridade de escolha:  1) canal.json -> "tema_fixo"   2) tema escolhido pelo Gemini (entre os daqui)   3) padrao da categoria.
A IA NUNCA inventa cores: ela escolhe um tema curado (contraste e legibilidade ja testados). O canal pode ainda
trocar so o acento ("tema_acento": "#RRGGBB") para manter a cor da marca.

Identidade do canal (fixa entre videos) = formato da legenda/chip/selo/contador, logo e animacao.
Paleta e modo claro/escuro mudam por assunto.
"""
import re

PADRAO = "neon_escuro"

# ceu_topo/ceu_base: cenarios procedurais; amb: (cor, forca) do veu do cenario; bloom/vinheta/contraste/tint: pos-processamento
# luz: (tipo, intensidade, cor) da luz de recorte atras do heroi; legenda: cores; chip: pilula do relogio
TEMAS = {
    "neon_escuro": dict(
        nome="Neon escuro", modo="escuro", ceu_topo="#070b24", ceu_base="#1b2a5c", chao_topo="#2a2f44", chao_base="#0b0d16",
        predio_fundo="#141a36", predio_meio="#0f1428", janela="#ffd37a", janelas_acesas=0.55, amb=("#0a1030", 0.12),
        acento="#ff4d4f", acento2="#2de2e6", bloom=1.0, bloom_limiar=175, vinheta=0.60, contraste=1.07, tint=(0, 3, 14),
        base_rgb=(8, 10, 20), luz=("neon", 0.42, None), fade=(3, 5, 12), faixa=((0, 0, 6), 0.58),
        legenda=dict(texto=(255, 255, 255), nao_falada=(196, 205, 230), sombra=(0, 0, 0)),
        chip=dict(chip_fundo=(10, 14, 32, 215), chip_borda=(255, 255, 255, 46), texto=(244, 247, 255, 255), mudo=(150, 163, 196, 255)),
        paleta="fundo azul-marinho/preto, acentos ciano e vermelho, luzes quentes de janela, brilho neon"),
    "tensao_quente": dict(
        nome="Tensao quente", modo="escuro", ceu_topo="#0b0710", ceu_base="#7a2c1c", chao_topo="#2a1a1e", chao_base="#08060a",
        predio_fundo="#1a1218", predio_meio="#0e0a10", janela="#ff9a5a", janelas_acesas=0.30, amb=("#2a0a08", 0.14),
        acento="#ff6a3d", acento2="#ffc24a", bloom=0.6, bloom_limiar=185, vinheta=0.66, contraste=1.10, tint=(6, 0, 0),
        base_rgb=(10, 6, 8), luz=("neon", 0.34, "#ff7a3d"), fade=(8, 3, 4), faixa=((6, 0, 0), 0.62),
        legenda=dict(texto=(255, 255, 255), nao_falada=(224, 200, 196), sombra=(0, 0, 0)),
        chip=dict(chip_fundo=(24, 10, 10, 220), chip_borda=(255, 200, 160, 50), texto=(255, 244, 238, 255), mudo=(210, 170, 150, 255)),
        paleta="fundo quase preto com horizonte vermelho/laranja e fumaca, acentos laranja e ambar, silhuetas escuras"),
    "financas_neutro": dict(
        nome="Financas neutro", modo="escuro", ceu_topo="#10151f", ceu_base="#26303f", chao_topo="#2b3342", chao_base="#10141c",
        predio_fundo="#1d2533", predio_meio="#151b27", janela="#e8d9a8", janelas_acesas=0.35, amb=("#10151f", 0.08),
        acento="#2fd07a", acento2="#f2c14e", bloom=0.30, bloom_limiar=195, vinheta=0.42, contraste=1.05, tint=(0, 2, 6),
        base_rgb=(14, 18, 26), luz=("suave", 0.22, "#cfe3ff"), fade=(10, 13, 20), faixa=((6, 8, 14), 0.55),
        legenda=dict(texto=(255, 255, 255), nao_falada=(190, 200, 215), sombra=(0, 0, 0)),
        chip=dict(chip_fundo=(16, 22, 34, 225), chip_borda=(255, 255, 255, 40), texto=(240, 245, 252, 255), mudo=(150, 163, 186, 255)),
        paleta="grafite azulado, acentos verde e dourado, superficies foscas, pouco brilho"),
    "saude_claro": dict(
        nome="Saude claro", modo="claro", ceu_topo="#f4fbff", ceu_base="#cfeaf4", chao_topo="#e3eef2", chao_base="#c2d4dc",
        predio_fundo="#d3e3ea", predio_meio="#bfd3dd", janela="#ffffff", janelas_acesas=0.0, amb=("#ffffff", 0.0),
        acento="#0a7c74", acento2="#3a7bd5", bloom=0.0, bloom_limiar=230, vinheta=0.10, contraste=1.02, tint=(0, 0, 0),
        base_rgb=(236, 246, 250), luz=("suave", 0.16, "#ffffff"), fade=(244, 250, 252), faixa=((236, 246, 250), 0.80),
        legenda=dict(texto=(14, 32, 56), nao_falada=(88, 110, 138), sombra=(255, 255, 255)),
        chip=dict(chip_fundo=(255, 255, 255, 238), chip_borda=(20, 50, 80, 60), texto=(14, 32, 56, 255), mudo=(88, 110, 138, 255)),
        paleta="fundo branco/azul-gelo muito claro, acentos teal e azul, tons de menta, sombras suaves, SEM neon, SEM preto"),
    "natureza_dia": dict(
        nome="Natureza dia", modo="claro", ceu_topo="#6ec1f2", ceu_base="#eaf8ff", chao_topo="#6aa84f", chao_base="#3d7a34",
        predio_fundo="#9fc8a0", predio_meio="#6fa56f", janela="#fff3c4", janelas_acesas=0.0, amb=("#fff6d6", 0.04),
        acento="#237644", acento2="#f2a93b", bloom=0.0, bloom_limiar=230, vinheta=0.12, contraste=1.04, tint=(2, 2, 0),
        base_rgb=(210, 236, 250), luz=("suave", 0.18, "#fff3c4"), fade=(232, 246, 252), faixa=((220, 240, 246), 0.78),
        legenda=dict(texto=(18, 44, 36), nao_falada=(70, 104, 92), sombra=(255, 255, 255)),
        chip=dict(chip_fundo=(255, 255, 255, 238), chip_borda=(30, 80, 50, 60), texto=(18, 44, 36, 255), mudo=(70, 104, 92, 255)),
        paleta="ceu azul claro, verdes vivos, terra e madeira, luz de dia, sem neon"),
    "historia_pergaminho": dict(
        nome="Historia pergaminho", modo="claro", ceu_topo="#efe2c4", ceu_base="#d9c196", chao_topo="#cdb48a", chao_base="#a58a5c",
        predio_fundo="#c9b083", predio_meio="#b39a6c", janela="#fff1c8", janelas_acesas=0.0, amb=("#8a6a3a", 0.06),
        acento="#98392c", acento2="#2f5d7c", bloom=0.0, bloom_limiar=230, vinheta=0.34, contraste=1.04, tint=(10, 5, 0),
        base_rgb=(224, 205, 165), luz=("suave", 0.14, "#fff1c8"), fade=(236, 222, 190), faixa=((228, 210, 170), 0.80),
        legenda=dict(texto=(44, 28, 16), nao_falada=(98, 74, 46), sombra=(255, 244, 214)),
        chip=dict(chip_fundo=(250, 238, 208, 238), chip_borda=(90, 60, 30, 70), texto=(44, 28, 16, 255), mudo=(112, 88, 60, 255)),
        paleta="tons de pergaminho e sepia, vermelho tijolo e azul petroleo, texturas de papel, sem neon"),
    "educacao_claro": dict(
        nome="Educacao claro", modo="claro", ceu_topo="#f6f8ff", ceu_base="#dfe7ff", chao_topo="#e6eaf6", chao_base="#c9d1ea",
        predio_fundo="#d5ddf2", predio_meio="#bcc7e6", janela="#ffffff", janelas_acesas=0.0, amb=("#ffffff", 0.0),
        acento="#3f5fe0", acento2="#ff8a3d", bloom=0.0, bloom_limiar=230, vinheta=0.10, contraste=1.03, tint=(0, 0, 4),
        base_rgb=(238, 242, 252), luz=("suave", 0.15, "#ffffff"), fade=(246, 248, 255), faixa=((238, 242, 252), 0.80),
        legenda=dict(texto=(18, 28, 60), nao_falada=(96, 108, 144), sombra=(255, 255, 255)),
        chip=dict(chip_fundo=(255, 255, 255, 238), chip_borda=(30, 40, 90, 60), texto=(18, 28, 60, 255), mudo=(96, 108, 144, 255)),
        paleta="fundo claro lavanda/branco, acentos azul royal e laranja, formas limpas, sem neon"),
    "pop_claro": dict(
        nome="Pop claro", modo="claro", ceu_topo="#fff4d6", ceu_base="#ffe3a8", chao_topo="#ffd37a", chao_base="#f2b441",
        predio_fundo="#ffd9a0", predio_meio="#ffc474", janela="#ffffff", janelas_acesas=0.0, amb=("#fff0c0", 0.04),
        acento="#c13a52", acento2="#2d9cdb", bloom=0.15, bloom_limiar=225, vinheta=0.12, contraste=1.06, tint=(0, 0, 0),
        base_rgb=(255, 236, 190), luz=("suave", 0.16, "#ffffff"), fade=(255, 246, 224), faixa=((255, 240, 200), 0.78),
        legenda=dict(texto=(40, 22, 36), nao_falada=(120, 84, 96), sombra=(255, 255, 255)),
        chip=dict(chip_fundo=(255, 255, 255, 240), chip_borda=(120, 50, 70, 60), texto=(40, 22, 36, 255), mudo=(120, 84, 96, 255)),
        paleta="fundo amarelo-creme quente, acentos rosa e azul vivo, formas arredondadas e divertidas, sem neon"),
}

# padrao por categoria (catalogo da Fabrica). Mude aqui para ajustar o gosto.
POR_CATEGORIA = {
    "curiosidades": "neon_escuro", "what_if": "neon_escuro", "tecnologia": "neon_escuro", "engenharia": "neon_escuro",
    "como_funciona": "educacao_claro", "educacao": "educacao_claro",
    "historia": "historia_pergaminho", "documentario": "historia_pergaminho",
    "economia": "financas_neutro", "noticias": "financas_neutro", "politica_institucional": "financas_neutro",
    "humor": "pop_claro", "celebridades": "pop_claro", "esportes": "pop_claro",
}

# sem IA: palavra do titulo/roteiro -> tema (heuristica barata)
HEURISTICA = [
    (("saude", "medic", "doenca", "hospital", "corpo", "cerebro", "sono", "vacina", "dieta", "virus", "bacteria", "cancer"), "saude_claro"),
    (("natureza", "animal", "floresta", "oceano", "planta", "clima", "ecossistema", "selva", "bicho"), "natureza_dia"),
    (("guerra", "crime", "misterio", "assassin", "terror", "conflito", "invasao", "atentado", "desaparec"), "tensao_quente"),
    (("dinheiro", "investimento", "bolsa", "inflacao", "mercado", "economia", "banco"), "financas_neutro"),
]


def _sem_acento(t):
    import unicodedata
    t = unicodedata.normalize("NFKD", str(t or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def existe(tid):
    return tid in TEMAS


def padrao_categoria(categoria):
    return POR_CATEGORIA.get(str(categoria or ""), PADRAO)


def escolher_local(categoria, texto=""):
    """sem IA: palavra-chave do assunto vence a categoria; senao, padrao da categoria"""
    t = _sem_acento(texto)
    for chaves, tid in HEURISTICA:
        if any(re.search(r"\b" + c, t) for c in chaves):
            return tid
    return padrao_categoria(categoria)


def resolver(categoria, canal=None, escolha_ia=None, texto=""):
    """-> (id_do_tema, origem). Prioridade: canal.tema_fixo > IA > categoria (+heuristica local quando nao ha IA)."""
    fixo = (canal or {}).get("tema_fixo")
    if fixo and existe(fixo):
        return fixo, "canal"
    if escolha_ia and existe(escolha_ia):
        return escolha_ia, "ia"
    return escolher_local(categoria, texto), "categoria"


def tema(tid, canal=None):
    """dict do tema; aplica o acento da marca do canal (tema_acento) se valido"""
    t = dict(TEMAS.get(tid) or TEMAS[PADRAO], id=tid if tid in TEMAS else PADRAO)
    ac = (canal or {}).get("tema_acento")
    if isinstance(ac, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", ac):
        t["acento"] = ac
    return t


def lista_para_prompt():
    return "\n".join(f'- "{k}" ({v["modo"]}): {v["paleta"]}' for k, v in TEMAS.items())


def para_motor(t):
    """tokens que o motor de cena (cena_generica/cenas.py) entende, dentro do JSON da cena"""
    leg = t["legenda"]
    return {"id": t["id"], "modo": t["modo"], "bloom_ganho": t["bloom"], "bloom_limiar": t["bloom_limiar"], "vinheta": t["vinheta"],
            "contraste": t["contraste"], "tint": list(t["tint"]), "base_rgb": list(t["base_rgb"]), "fade": list(t["fade"]),
            "faixa": {"cor": list(t["faixa"][0]), "forca": t["faixa"][1]},
            "legenda": {"texto": list(leg["texto"]), "nao_falada": list(leg["nao_falada"]), "sombra": list(leg["sombra"]), "destaque": t["acento"]},
            "chip": {k: list(v) for k, v in t["chip"].items()}, "acento": t["acento"], "halo": 1.0 if t["bloom"] >= 0.5 else (0.45 if t["bloom"] > 0 else 0.0)}


def cor_rgb(hexa):
    h = hexa.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def contraste_wcag(a, b):
    """razao de contraste WCAG entre duas cores RGB (>= 4.5 recomendado para texto)"""
    def lum(c):
        r = []
        for v in c:
            v /= 255.0
            r.append(v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4)
        return 0.2126 * r[0] + 0.7152 * r[1] + 0.0722 * r[2]
    la, lb = lum(a), lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)
