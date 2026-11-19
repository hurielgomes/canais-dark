"""
diretor.py - "diretor local" do M1: transforma a narracao de cada cena em uma CENA GENERICA do M1, sem IA.

Como funciona (Fase 1 - sem LLM):
  * KITS (biblioteca_m1/kits.json): modelos de cena (cenario + elementos + linha do tempo + camera) com palavras-chave.
    Todos os recursos citados por um kit precisam estar APROVADOS na biblioteca; senao o kit e ignorado.
  * Para cada cena do roteiro: tokens da narracao/tema/busca -> kit com mais palavras em comum; sem correspondencia
    usa um kit "neutro" (so ambiente) em rodizio, sem repetir o anterior.
  * O tempo do kit e ESTICADO/COMPRIMIDO para a duracao real da narracao da cena.
  * Se o roteiro trouxer "cena2d" (direcao visual escrita por uma IA), ela tem prioridade (validada aqui).
Nada neste modulo executa codigo externo: so le JSON.
"""
import copy
import hashlib
import json
import re
import unicodedata
from pathlib import Path

STOP = set("""a o as os um uma uns umas de do da dos das em no na nos nas por para com sem sobre entre ate que se ou e mas
como mais menos muito muita muitos muitas isso isto esse essa esses essas este esta estes estas ele ela eles elas seu sua
seus suas foi era ser sao tem ter tinha vai vao ja so nao sim quando onde qual quais quem tambem ainda depois antes
aqui ali la entao porque pois cada todo toda todos todas outro outra outros outras mesmo mesma nosso nossa""".split())

CHAVES_TEMPO = ("t", "fim", "ini")


def norm(s):
    s = unicodedata.normalize("NFD", str(s).lower())
    return re.sub(r"[^a-z0-9 ]", " ", "".join(c for c in s if unicodedata.category(c) != "Mn"))


def tokens(*textos):
    out = set()
    for t in textos:
        for w in norm(t or "").split():
            if len(w) >= 3 and w not in STOP:
                out.add(w)
    return out


# --------------------------------------------------------------------------- kits
def carregar_kits(caminho):
    p = Path(caminho)
    if not p.is_file():
        return []
    d = json.loads(p.read_text(encoding="utf-8"))
    kits = []
    for k in d.get("kits", []):
        if isinstance(k, dict) and k.get("id") and isinstance(k.get("cena"), dict):
            k.setdefault("palavras", [])
            k.setdefault("dur_ref", 7.0)
            kits.append(k)
    return kits


def refs_de(obj, acc=None):
    """todos os recursos ('ref') citados em uma cena (cenario, elementos e slots)"""
    acc = set() if acc is None else acc
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "ref" and isinstance(v, str):
                acc.add(v)
            else:
                refs_de(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            refs_de(v, acc)
    return acc


def kit_usavel(kit, bib):
    """(True, []) se todos os recursos do kit estao aprovados; senao (False, [(ref, status|None), ...])"""
    falta = [(r, bib.status_de(r)) for r in sorted(refs_de(kit["cena"])) if bib.status_de(r) != "aprovado"]
    return (not falta), falta


def _pontuar(kit, toks):
    pts = 0
    for pal in kit.get("palavras", []):
        n = norm(pal).strip()
        if not n:
            continue
        if any(t.startswith(n) or (len(t) >= 4 and n.startswith(t)) for t in toks):
            pts += 1
    return pts


def escolher_kit(kits, toks, indice, anterior=None, toks_tema=()):
    """Escolhe o kit da cena. Retorna (kit|None, motivo).
      1) kit com mais palavras em comum com a CENA, sem repetir o kit anterior;
      2) senao, um kit NEUTRO (so ambiente) coerente com cena+tema, em rodizio;
      3) senao, qualquer kit (repetindo se for o unico)."""
    if not kits:
        return None, "nenhum kit utilizavel"
    ativos = [k for k in kits if not k.get("neutro")]
    pont = sorted(((_pontuar(k, toks), k) for k in ativos if k["id"] != anterior), key=lambda x: -x[0])
    if pont and pont[0][0] > 0:
        topo = pont[0][0]
        melhores = [k for p, k in pont if p == topo]
        return melhores[indice % len(melhores)], f"{topo} palavra(s) em comum"
    neutros = [k for k in kits if k.get("neutro") and k["id"] != anterior] or [k for k in kits if k.get("neutro")]
    if neutros:
        amplo = set(toks) | set(toks_tema)
        pn = sorted(((_pontuar(k, amplo), k) for k in neutros), key=lambda x: -x[0])
        topo = pn[0][0]
        melhores = [k for p, k in pn if p == topo]
        return melhores[indice % len(melhores)], ("ambiente do tema" if topo > 0 else "sem correspondencia: ambiente neutro")
    alt = [k for k in kits if k["id"] != anterior] or kits
    return alt[indice % len(alt)], "unico kit disponivel"


# --------------------------------------------------------------------------- instanciar
def _clamp(v, a, b):
    return max(a, min(b, v))


def escalar_tempos(obj, f):
    """multiplica os tempos (t / ini / fim) de uma cena por f (estica/comprime a linha do tempo)"""
    if isinstance(obj, dict):
        return {k: (round(v * f, 3) if k in CHAVES_TEMPO and isinstance(v, (int, float)) and not isinstance(v, bool) else escalar_tempos(v, f))
                for k, v in obj.items()}
    if isinstance(obj, list):
        return [escalar_tempos(v, f) for v in obj]
    return obj


def instanciar(kit, dur, trechos, destaques):
    f = _clamp(dur / float(kit["dur_ref"]), 0.6, 1.8)
    cena = escalar_tempos(copy.deepcopy(kit["cena"]), f)
    cena.update({"modelo": "generica", "duracao": round(float(dur), 3), "legenda": trechos, "destaques": destaques,
                 "kit": kit["id"]})
    return cena


def validar_cena_externa(cena):
    """cena escrita por IA (roteiro['cena2d']): sem arquivo/def inline; so recursos da biblioteca. -> lista de erros"""
    erros = []
    if not isinstance(cena, dict):
        return ["cena2d deve ser um objeto"]

    def varre(o, caminho):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("arquivo", "def"):
                    erros.append(f"{caminho}/{k}: recursos novos devem vir em 'recursos_novos' do roteiro, nao inline na cena")
                else:
                    varre(v, f"{caminho}/{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                varre(v, f"{caminho}[{i}]")
    varre(cena, "cena2d")
    if cena.get("modelo", "generica") != "generica":
        erros.append("cena2d.modelo deve ser 'generica'")
    return erros


# --------------------------------------------------------------------------- legenda e destaques
def destaques_de(texto, n=2):
    """palavras-chave para realce: numeros/porcentagens primeiro, depois as palavras longas mais 'raras'"""
    palavras = re.findall(r"[\wÀ-ÿ%$.,-]+", texto)
    limpa = [re.sub(r"^[^\wÀ-ÿ%$]+|[^\wÀ-ÿ%$]+$", "", p) for p in palavras]
    nums = [p for p in limpa if re.search(r"\d", p)]
    outros = sorted({p for p in limpa if len(p) >= 6 and norm(p).strip() not in STOP and not re.search(r"\d", p)},
                    key=lambda p: -len(p))
    return (nums + outros)[:n]


def trechos_legenda(texto, dur, pausa_fim, n_palavras=4, maiusculas=False, respiro=0.15):
    pal = (texto.upper() if maiusculas else texto).split()
    if not pal:
        return []
    ini, fim = respiro, max(respiro + 0.5, dur - pausa_fim)
    grupos = [pal[k:k + n_palavras] for k in range(0, len(pal), max(1, n_palavras))]
    t, out = ini, []
    for g in grupos:
        d = (fim - ini) * len(g) / len(pal)
        out.append({"ini": round(t, 3), "fim": round(t + d, 3), "texto": " ".join(g)})
        t += d
    return out


def hash_texto(s):
    return hashlib.sha1(str(s).encode("utf-8")).hexdigest()[:16]
