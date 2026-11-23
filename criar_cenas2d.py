"""criar_cenas2d.py - motor M1 "Cenas 2D em Camadas" (Fase 1).
Mesmos argumentos principais do criar_video.py. Diretor local; Gemini fica para a Fase 2."""
import argparse
import copy
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

import criar_video as cv
from editorial_rules import ensure_closing_question

sys.path.insert(0, str(Path(__file__).resolve().parent / "estudio"))
from estudio.cenas2d.recursos.biblioteca import Biblioteca
from estudio.estilos.cenas2d import Estilo
from estudio.nucleo import Tela
import diretor_m1

PRESET = "alerta_noturno"
VERSAO_RENDER = "2"
RESPIRO_INICIAL = 0.15
TIPOS_CENARIO = {"cenario", "fundo"}


def _sha(obj):
    return hashlib.sha1(json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------- voz
def invalidar_voz(roteiro, pasta):
    """Apaga WAVs de cenas cuja narracao mudou (gerar_voz reaproveita qualquer NN.wav existente)."""
    arq = pasta / "audio" / "hashes.json"
    novos = [_sha(c["narracao"]) for c in roteiro["cenas"]]
    if arq.exists():
        antigos = cv.ler_json(arq)
        mudou = len(antigos) != len(novos)
        for i, h in enumerate(novos, 1):
            if i > len(antigos) or antigos[i - 1] != h:
                (pasta / "audio" / f"{i:02d}.wav").unlink(missing_ok=True)
                mudou = True
        if mudou:
            (pasta / "narracao.wav").unlink(missing_ok=True)
    return novos


# ---------------------------------------------------------------- diretor local
def catalogo(bib):
    itens = bib.listar()  # CONFIRMAR formato
    if isinstance(itens, dict):
        itens = [{"id": k, **v} for k, v in itens.items()]
    return [r for r in itens if isinstance(r, dict) and r.get("id")]


def _aprovado(status):
    return str(status or "").lower().startswith("aprov")


def montar_cenas(roteiro, hashes, duracoes, bib, arq, modo="local", cfg=None, categoria=None, canal=None, chat_scope=None):
    """Diretor: roteiro -> cenas M1. Reaproveita cenas ja montadas (cache por narracao+duracao+diretor)."""
    antigo = cv.ler_json(arq).get("cenas", []) if arq.exists() else []
    saida = []
    chave_tema = [categoria, (canal or {}).get("tema_fixo"), (canal or {}).get("tema_acento")]
    chaves = [_sha([h, round(d, 1), modo, chave_tema]) for h, d in zip(hashes, duracoes)]
    if len(antigo) == len(chaves) and all(a.get("chave") == k for a, k in zip(antigo, chaves)):
        return [a["cena"] for a in antigo]
    cenas = diretor_m1.dirigir(roteiro, duracoes, bib, modo=modo, cfg=cfg, cv=cv, log=cv.info, categoria=categoria, canal=canal, chat_scope=chat_scope)
    for k, h, c in zip(chaves, hashes, cenas):
        saida.append({"chave": k, "hash_narracao": h, "cena": c})
    cv.salvar_json(arq, {"versao": 2, "cenas": saida})
    return cenas


# ---------------------------------------------------------------- pre-verificacao
def _varrer(o, refs, proib, caminho=""):
    if isinstance(o, dict):
        for k, v in o.items():
            if k in ("arquivo", "def"):
                proib.append(f"{caminho}/{k}")
            elif k == "ref" and isinstance(v, str):
                refs.add(v)
            else:
                _varrer(v, refs, proib, f"{caminho}/{k}")
    elif isinstance(o, list):
        for n, v in enumerate(o):
            _varrer(v, refs, proib, f"{caminho}[{n}]")


def _status(bib, ref):
    e = bib.idx["recursos"].get(ref)
    return str(e.get("status", "")).lower() if e else None


def preverificar(cenas, bib):
    """Plano B: recurso ausente, pendente ou arquivo/def inline = erro ANTES do render."""
    ausentes, pendentes, proibidos = set(), set(), []
    for i, c in enumerate(cenas, 1):
        refs, proib = set(), []
        _varrer(c, refs, proib, f"cena{i}")
        proibidos += proib
        for ref in refs:
            st = _status(bib, ref)
            if st is None:
                ausentes.add(ref)
            elif not _aprovado(st):
                pendentes.add(ref)
    if proibidos:
        cv.erro("cenas com 'arquivo'/'def' inline nao sao permitidas: " + ", ".join(proibidos[:5]))
    if ausentes:
        cv.erro("recursos inexistentes na biblioteca: " + ", ".join(sorted(ausentes)))
    if pendentes:
        cv.erro("recursos pendentes de aprovacao: " + ", ".join(sorted(pendentes)) +
                ". Aprove-os na biblioteca e use Retomar na interface.")


# ---------------------------------------------------------------- legenda e render
def trechos_legenda(texto, dur, pausa_fim, canal):
    n = max(1, int(canal.get("legenda_palavras", 4)))
    if canal.get("legenda_maiusculas", True):
        texto = texto.upper()
    pal = texto.split()
    if not pal:
        return []
    ini, fim = RESPIRO_INICIAL, max(RESPIRO_INICIAL + 0.5, dur - pausa_fim)
    grupos = [pal[k:k + n] for k in range(0, len(pal), n)]
    t, saida = ini, []
    for g in grupos:
        d = (fim - ini) * len(g) / len(pal)
        saida.append({"ini": round(t, 3), "fim": round(t + d, 3), "texto": " ".join(g)})
        t += d
    return saida


def preparar_cena(cena, narracao, dur, i, canal):
    c = copy.deepcopy(cena)   # a CenaGenerica altera os dicts
    c["modelo"] = "generica"
    c["duracao"] = dur
    c["legenda"] = trechos_legenda(narracao, dur, cv.PAUSA_GANCHO if i == 0 else cv.PAUSA_CENA, canal)
    return c


def _pix_fmt(img):
    modo = getattr(img, "mode", None)
    if modo:
        return {"RGB": "rgb24", "RGBA": "rgba", "L": "gray"}[modo]
    return "rgb24" if img.shape[-1] == 3 else "rgba"


def _salvar_png(img, caminho):
    if not hasattr(img, "save"):
        from PIL import Image
        img = Image.fromarray(img)
    img.convert("RGB").save(str(caminho))


def renderizar_segmento(cena, w, h, fps, n, bib, canal, destino):
    est = Estilo(w, h, PRESET, bib)
    tela = Tela(w, h, 1)
    tmp = destino.with_name(destino.stem + ".parcial.mp4")
    p = None
    with open(destino.with_suffix(".log"), "wb") as lg:
        try:
            for k in range(n):
                est.quadro(tela, k / fps, cena, canal)
                img = tela.img
                if p is None:
                    p = subprocess.Popen(
                        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", _pix_fmt(img),
                         "-s", f"{w}x{h}", "-r", str(fps), "-i", "-", "-an", "-c:v", "libx264",
                         "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", str(tmp)],
                        stdin=subprocess.PIPE, stderr=lg)
                p.stdin.write(img.tobytes())
        finally:
            rc = None
            if p is not None:
                p.stdin.close()
                rc = p.wait()
    if p is None or rc != 0:
        cv.erro(f"falha ao renderizar {destino.name} (veja {destino.with_suffix('.log').name}).")
    tmp.replace(destino)


def _render_worker(args):
    """roda num processo separado (Windows: spawn). Devolve (indice, erro|None)."""
    idx, raiz_bib, c, w, h, fps, n, canal, seg = args
    try:
        bib = Biblioteca(raiz_bib, bloquear_pendentes=True)
        renderizar_segmento(c, w, h, fps, n, bib, canal, Path(seg))
        return idx, None
    except BaseException as e:  # noqa  (cv.erro usa SystemExit)
        return idx, str(e) or e.__class__.__name__


def renderizar_formato(nome, w, h, roteiro, cenas, duracoes, bib, canal, pasta):
    fps = cv.FPS
    segdir = pasta / "segmentos" / nome
    segdir.mkdir(parents=True, exist_ok=True)
    marcos, acum = [0], 0.0
    for d in duracoes:
        acum += d
        marcos.append(round(acum * fps))   # arredondamento acumulado: soma bate com o audio
    refs_hash, lista, pendentes = {}, [], []
    total = len(cenas)
    for i, cena in enumerate(cenas):
        n = marcos[i + 1] - marcos[i]
        seg = segdir / f"cena_{i + 1:02d}.mp4"
        c = preparar_cena(cena, roteiro["cenas"][i]["narracao"], duracoes[i], i, canal)
        refs = set()
        _varrer(c, refs, [])
        for r in refs:
            refs_hash[r] = (bib.idx["recursos"].get(r) or {}).get("hash")
        h_cena = _sha([VERSAO_RENDER, c, n, w, h, fps, refs_hash])
        marca = seg.with_suffix(".hash")
        if seg.exists() and marca.exists() and marca.read_text().strip() == h_cena:
            cv.info(f"   [{nome}] plano {i + 1}/{total} (cache)")
        else:
            pendentes.append((i, (i, str(bib.raiz), c, w, h, fps, n, canal, str(seg)), marca, h_cena))
        lista.append(f"file '{seg.name}'")
    if pendentes:
        import os
        from concurrent.futures import ProcessPoolExecutor
        trabalhadores = max(1, min(len(pendentes), int(canal.get("render_processos") or max(1, (os.cpu_count() or 2) - 1))))
        info = {p[0]: p for p in pendentes}
        if trabalhadores == 1:
            resultados = (_render_worker(p[1]) for p in pendentes)
            pool = None
        else:
            pool = ProcessPoolExecutor(max_workers=trabalhadores)
            resultados = pool.map(_render_worker, [p[1] for p in pendentes])
        try:
            for idx, err in resultados:
                if err:
                    cv.erro(f"falha ao renderizar o plano {idx + 1} ({err}).")
                info[idx][2].write_text(info[idx][3])
                cv.info(f"   [{nome}] plano {idx + 1}/{total}")
        finally:
            if pool:
                pool.shutdown(cancel_futures=True)
    (segdir / "lista.txt").write_text("\n".join(lista), encoding="utf-8")
    return segdir


def montar_final(nome, segdir, narracao, musica, duracoes, canal, pasta, titulo_arq):
    saida = pasta / "saida"
    saida.mkdir(exist_ok=True)
    destino = saida / f"{titulo_arq}_{nome}.mp4"
    parcial = saida / f"{titulo_arq}_{nome}.parcial.mp4"
    if destino.exists():
        cv.info(f"   [{nome}] ja existe, pulando.")
        return destino
    parcial.unlink(missing_ok=True)
    total = sum(duracoes)
    fim = f"{max(0, total - cv.FADE):.2f}"
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "lista.txt", "-i", str(narracao.resolve())]
    if musica:
        cmd += ["-stream_loop", "-1", "-i", str(Path(musica).resolve())]
        audio = (f"[1:a]afade=t=in:st=0:d={cv.FADE},afade=t=out:st={fim}:d={cv.FADE}[n];"
                 f"[2:a]volume={float(canal['volume_musica'])},afade=t=in:st=0:d=1.5,"
                 f"afade=t=out:st={fim}:d={cv.FADE}[m];"
                 "[n][m]amix=inputs=2:duration=first:dropout_transition=0,volume=2,"
                 "loudnorm=I=-14:TP=-1.5:LRA=9,alimiter=limit=0.95[a]")
    else:
        audio = f"[1:a]afade=t=in:st=0:d={cv.FADE},afade=t=out:st={fim}:d={cv.FADE},loudnorm=I=-14:TP=-1.5:LRA=9[a]"
    cmd += ["-filter_complex", audio, "-map", "0:v", "-map", "[a]", "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.2f}", "-movflags", "+faststart",
            str(parcial.resolve())]
    cv.rodar(cmd, cwd=segdir)
    parcial.replace(destino)
    cv.info(f"   pronto: {destino}")
    return destino


# ---------------------------------------------------------------- main
def roteiro_falso(tema):
    return {"titulo": f"Teste: {tema}", "descricao": "Descricao de teste.", "tags": ["teste"],
            "gancho_texto": "Ninguem explica isso", "texto_miniatura": "O segredo", "prompt_miniatura": "",
            "cenas": [
                {"narracao": f"Esta e a primeira cena do video de teste sobre {tema}. Ela serve para checar a legenda.",
                 "imagem": "x", "busca_stock": "x"},
                {"narracao": "Aqui vem a segunda cena, um pouco mais longa, para ver como as legendas quebram em trechos curtos e acompanham a fala.",
                 "imagem": "x", "busca_stock": "x"},
                {"narracao": "E esta e a cena final. Fim do teste.", "imagem": "x", "busca_stock": "x"}]}


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa
        pass
    ap = argparse.ArgumentParser(description="Cria um video com Cenas 2D em Camadas (M1).")
    ap.add_argument("canal")
    ap.add_argument("tema", nargs="?", default="")
    ap.add_argument("--duracao", type=int)
    ap.add_argument("--categoria", default="curiosidades")
    ap.add_argument("--entrega-format", choices=["16x9", "9x16"])
    ap.add_argument("--roteiro")
    ap.add_argument("--projeto")
    ap.add_argument("--revisar", action="store_true")
    ap.add_argument("--simular", action="store_true")
    ap.add_argument("--formatos", default="9x16")
    ap.add_argument("--perfil", default=None)
    ap.add_argument("--diretor", choices=["auto", "local", "gemini", "myhub"], default=None,
                    help="IA da direcao de arte (padrao: config.json -> m1_diretor_padrao; auto = MyHub se instalado, senao Gemini, senao local)")
    a = ap.parse_args()

    for prog in ("ffmpeg", "ffprobe"):
        if shutil.which(prog) is None:
            cv.erro(f"'{prog}' nao foi encontrado. Instale o FFmpeg e abra um novo terminal.")

    cfg = cv.carregar_config()
    canal = cv.carregar_canal(a.canal)
    cv.PAUSA_CENA = float(canal["pausa_entre_cenas"])
    cv.PAUSA_GANCHO = float(canal["pausa_gancho"])
    canal["_usa_video"] = False
    duracao = a.duracao or int(canal["duracao_alvo_segundos"])
    formatos = [a.entrega_format] if a.entrega_format else \
        [f.strip() for f in a.formatos.split(",") if f.strip() in cv.FORMATOS]
    if not formatos:
        cv.erro("--formatos deve ser 16x9, 9x16 ou os dois separados por virgula.")

    if a.roteiro:
        base_nome = cv.ler_json(a.roteiro).get("titulo", a.tema or "video")
    elif a.tema or a.projeto:
        base_nome = a.tema or "video"
    else:
        cv.erro('informe o tema entre aspas. Exemplo: python criar_cenas2d.py exemplo "Tema do video"')
    if a.projeto:
        pasta = Path(a.projeto).expanduser()
        if not pasta.is_absolute():
            pasta = RAIZ / pasta
        pasta = pasta.resolve()
        if pasta.parent != (RAIZ / "projetos" / a.canal).resolve() or not pasta.is_dir():
            cv.erro("--projeto deve apontar para uma pasta existente diretamente dentro de projetos/<canal>/.")
    else:
        sufixo = f"_{a.entrega_format}" if a.entrega_format else ""
        pasta = RAIZ / "projetos" / a.canal / f"{date.today().isoformat()}_{cv.slug(base_nome)}{sufixo}"
    pasta.mkdir(parents=True, exist_ok=True)
    cv.info(f"\nProjeto: {pasta}")

    # 1. roteiro
    cv.info("\n[1/5] Roteiro")
    arq_roteiro = pasta / "roteiro.json"
    if a.roteiro and not arq_roteiro.exists():
        shutil.copy(a.roteiro, arq_roteiro)
    if not arq_roteiro.exists():
        if a.simular:
            cv.salvar_json(arq_roteiro, roteiro_falso(a.tema))
        else:
            cv.salvar_json(arq_roteiro, cv.gerar_roteiro(
                canal, a.tema, duracao, cv.titulos_anteriores(a.canal, pasta), cfg, a.categoria, a.perfil,
                chat_scope=f"{a.canal}_{pasta.name}"))
    else:
        cv.info("   roteiro.json ja existe, usando.")
    roteiro = cv.validar_roteiro(cv.ler_json(arq_roteiro))
    roteiro = ensure_closing_question(roteiro, a.categoria, a.tema, canal.get("tom", ""))
    cv.salvar_json(arq_roteiro, roteiro)
    cv.info(f"   titulo: {roteiro['titulo']} ({len(roteiro['cenas'])} cenas)")
    if a.revisar:
        cv.info(f"\nRevise e edite {arq_roteiro}. Depois retome para continuar.")
        return

    # 2. voz
    cv.info("\n[2/5] Voz")
    hashes = invalidar_voz(roteiro, pasta)
    narracao, duracoes = cv.gerar_voz(roteiro, pasta, canal, a.simular)
    cv.salvar_json(pasta / "audio" / "hashes.json", hashes)

    # 3. cenas
    cv.info("\n[3/5] Cenas (direcao de arte + recursos)")
    bib = Biblioteca(RAIZ / "biblioteca_m1", bloquear_pendentes=True)
    modo_diretor = str(a.diretor or cfg.get("m1_diretor_padrao") or "auto").strip().lower()
    if modo_diretor not in ("myhub", "gemini", "local", "auto"):
        cv.erro(f"m1_diretor_padrao invalido: {modo_diretor!r}. Use myhub, gemini, local ou auto.")
    cenas = montar_cenas(roteiro, hashes, duracoes, bib, pasta / "cenas2d.json",
                         "local" if a.simular else modo_diretor, cfg, a.categoria, canal, chat_scope=f"{a.canal}_{pasta.name}")
    preverificar(cenas, bib)

    # 4. render + montagem
    cv.info("\n[4/5] Render e montagem")
    musica = cv.escolher_musica(canal, pasta)
    titulo_arq = cv.slug(roteiro["titulo"])
    for nome in formatos:
        w, h = cv.FORMATOS[nome]
        segdir = renderizar_formato(nome, w, h, roteiro, cenas, duracoes, bib, canal, pasta)
        video = montar_final(nome, segdir, narracao, musica, duracoes, canal, pasta, titulo_arq)
        try:
            cv.aplicar_branding_video(video, canal, nome)
        except RuntimeError as e:
            cv.info(f"   aviso: branding nao aplicado ({e})")

    # miniatura: quadro da cena 1, sem chamar IA de imagem (prompt_miniatura zerado)
    if not (pasta / "miniatura.jpg").exists():
        w, h = cv.FORMATOS[formatos[0]]
        est, tela = Estilo(w, h, PRESET, bib), Tela(w, h, 1)
        c1 = preparar_cena(cenas[0], roteiro["cenas"][0]["narracao"], duracoes[0], 0, canal)
        est.quadro(tela, min(1.0, max(0.0, duracoes[0] - 0.1)), c1, canal)
        (pasta / "cache").mkdir(exist_ok=True)
        png = pasta / "cache" / "quadro_cena1.png"
        _salvar_png(tela.img, png)
        imagens = [str(png)]
    else:
        imagens = [str(pasta / "miniatura.jpg")]
    cv.gerar_miniatura(dict(roteiro, prompt_miniatura=""), pasta, cfg, canal, a.simular, imagens, formatos[0])

    try:
        bib.galeria(pasta / "saida" / "recursos.html")
    except Exception as e:  # noqa
        cv.info(f"   aviso: galeria nao gerada ({e})")

    # 5. publicacao
    cv.info("\n[5/5] Publicacao")
    cv.salvar_publicacao(roteiro, pasta)
    cv.info(f"\nPRONTO. Veja a pasta: {pasta}\\saida")


if __name__ == "__main__":
    main()