"""
app.py - Fabrica de videos: interface local (abre no navegador, sem internet para a tela).

Uso:  python app.py     (ou de duplo clique em iniciar.bat)
Depois abra http://127.0.0.1:8765  (o iniciar.bat ja abre sozinho).

Esta janela precisa ficar aberta enquanto voce usa a interface.
So aceita conexoes do proprio computador (127.0.0.1).
"""

import contextlib
import io
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
from uuid import uuid4

from job_store import JobStore
from engine_registry import get_adapter, get_engine, get_health as engines_health, is_engine_executable, list_categories, list_engines, list_thumbnail_templates

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))
import criar_video as cv  # noqa: E402

PORTA = 8765
PROJETOS = RAIZ / "projetos"
RASCUNHOS = PROJETOS / "_planejamento"
DATA_DIR = RAIZ / "data"
STORE = JobStore(DATA_DIR / "fabrica.sqlite3")
INTERRUPTIDOS_NA_INICIALIZACAO = STORE.mark_interrupted()
LOCK = threading.RLock()
FILA = STORE.list()
PROCESSOS = {}

NOMES_ETAPAS = {1: "Roteiro", 2: "Voz", 3: "Imagens e videos", 4: "Montagem", 5: "Publicacao"}
BASE_ETAPA = {1: 2, 2: 12, 3: 30, 4: 55, 5: 97}


# ------------------------------------------------------------------ fila

def persistir_job(job):
    """Persiste o estado atual da tarefa no SQLite."""
    STORE.save(job)


def novo_job(canal, tema, opc):
    motor = str(opc.get("motor") or "classico")
    categoria = str(opc.get("categoria") or "curiosidades")
    categorias_validas = {x["id"] for x in list_categories()}
    if categoria not in categorias_validas:
        raise ValueError(f"Categoria '{categoria}' nao consta no catalogo.")
    adapter = get_adapter(motor)
    if adapter is None:
        spec = get_engine(motor)
        nome = spec.get("name", motor) if spec else motor
        raise ValueError(f"O motor '{nome}' ainda esta em preparacao.")
    if not (RAIZ / "canais" / canal / "canal.json").is_file():
        raise ValueError(f"Canal '{canal}' nao encontrado.")
    try:
        adapter.validate_job({**opc, "canal": canal, "tema": tema, "formatos": opc.get("formatos") or "16x9,9x16"})
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
    with LOCK:
        job = {
            "canal": canal, "tema": tema,
            "motor": motor, "categoria": categoria,
            "formatos": opc.get("formatos") or "16x9,9x16",
            "duracao": int(opc.get("duracao") or 0),
            "entrega_format": str(opc.get("entrega_format") or (str(opc.get("formatos") or "").split(",")[0] if opc.get("formatos") else "")),
            "duracao_longa": int(opc.get("duracao_longa") or 0),
            "duracao_curta": int(opc.get("duracao_curta") or 0),
            "revisar": bool(opc.get("revisar")),
            "simular": bool(opc.get("simular")),
            "status": "pendente", "etapa": 0, "etapa_nome": "Na fila", "progresso": 0,
            "pasta": "", "titulo": "", "erro": "", "log": [], "criado": time.time(),
            "tentativas": 0,
        }
        job["id"] = STORE.create(job)
        FILA.append(job)
        return job


def atualizar_linha(job, linha):
    job.setdefault("log", []).append(linha)
    if len(job["log"]) > 200:
        del job["log"][:50]
    m = re.match(r"^\[(\d)/5\]\s*(.*)", linha)
    if m:
        e = int(m.group(1))
        job["etapa"] = e
        job["etapa_nome"] = NOMES_ETAPAS.get(e, m.group(2))
        job["progresso"] = max(job["progresso"], BASE_ETAPA.get(e, job["progresso"]))
    else:
        m = re.match(r"^Projeto:\s*(.*)", linha)
        if m:
            p = Path(m.group(1).strip())
            try:
                job["pasta"] = p.resolve().relative_to(PROJETOS.resolve()).as_posix()
            except Exception:  # noqa
                job["pasta"] = ""
        else:
            m = re.match(r"^\s+titulo:\s*(.*?)\s*\(\d+ cenas\)", linha)
            if m:
                job["titulo"] = m.group(1)
            else:
                m = re.search(r"(?:voz|imagem|video) da cena (\d+)/(\d+)", linha)
                if m:
                    i, n = int(m.group(1)), max(1, int(m.group(2)))
                    if "voz da cena" in linha:
                        job["progresso"] = max(job["progresso"], int(12 + 18 * i / n))
                    else:
                        job["progresso"] = max(job["progresso"], int(30 + 25 * i / n))
                else:
                    m = re.search(r"\[(16x9|9x16)\] plano (\d+)/(\d+)", linha)
                    if m:
                        fmts = [f.strip() for f in job["formatos"].split(",") if f.strip()]
                        idx = fmts.index(m.group(1)) if m.group(1) in fmts else 0
                        frac = (idx + int(m.group(2)) / max(1, int(m.group(3)))) / max(1, len(fmts))
                        job["progresso"] = max(job["progresso"], int(55 + 40 * frac))
    persistir_job(job)


def executar(job):
    spec = get_engine(job.get("motor", "classico"))
    adapter = get_adapter(job.get("motor", "classico"))
    if not spec or adapter is None:
        job["status"], job["erro"] = "erro", "Motor visual nao possui adaptador de execucao instalado."
        persistir_job(job)
        return
    try:
        cmd = adapter.build_command(job, RAIZ, sys.executable)
    except Exception as e:  # noqa
        job["status"], job["erro"] = "erro", f"opcoes do motor invalidas: {e}"
        persistir_job(job)
        return
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    try:
        proc = subprocess.Popen(cmd, cwd=str(RAIZ), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace", env=env)
    except Exception as e:  # noqa
        job["status"], job["erro"] = "erro", f"nao consegui iniciar: {e}"
        persistir_job(job)
        return
    PROCESSOS[job["id"]] = proc
    ultima_erro = ""
    for linha in proc.stdout:
        linha = linha.rstrip("\n")
        if linha.strip():
            atualizar_linha(job, linha)
            if linha.startswith("ERRO:"):
                ultima_erro = linha[5:].strip()
    proc.wait()
    PROCESSOS.pop(job["id"], None)
    if job.get("cancelado"):
        job["status"] = "cancelado"
    elif proc.returncode == 0:
        if job["revisar"]:
            job["status"], job["etapa_nome"], job["progresso"] = "revisar", "Aguardando sua revisao", 12
        else:
            job["status"], job["etapa_nome"], job["progresso"] = "ok", "Pronto", 100
        job["erro"] = ""
    else:
        job["status"] = "erro"
        job["erro"] = ultima_erro or "o processo terminou com erro (veja o registro)"
    persistir_job(job)


def trabalhador():
    while True:
        job = None
        with LOCK:
            for j in FILA:
                if j["status"] == "pendente":
                    job = j
                    j["status"] = "rodando"
                    j["etapa_nome"] = "Iniciando"
                    j["tentativas"] = int(j.get("tentativas", 0)) + 1
                    persistir_job(j)
                    break
        if job is None:
            time.sleep(0.5)
            continue
        try:
            executar(job)
        except Exception as e:  # noqa
            job["status"], job["erro"] = "erro", str(e)
            persistir_job(job)


def cancelar(job):
    job["cancelado"] = True
    if job["status"] == "pendente":
        job["status"] = "cancelado"
        persistir_job(job)
        return
    proc = PROCESSOS.get(job["id"])
    if proc and proc.poll() is None:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
        else:
            proc.kill()
    persistir_job(job)


# ------------------------------------------------------------------- dados

def lista_canais():
    saida = []
    base = RAIZ / "canais"
    if base.exists():
        for p in sorted(base.iterdir()):
            if (p / "canal.json").exists():
                try:
                    c = cv.carregar_canal(p.name)
                    identidade = c.get("identidade", {}) if isinstance(c.get("identidade", {}), dict) else {}
                    logo_path = Path(str(identidade.get("logo_arquivo") or "identidade/logo.png"))
                    if not logo_path.is_absolute():
                        logo_path = p / logo_path
                    saida.append({"nome": p.name, "titulo": identidade.get("nome_exibicao") or c.get("nome", p.name), "nicho": c.get("nicho", ""),
                                  "duracao": c.get("duracao_alvo_segundos", 60), "logo_configurada": logo_path.is_file()})
                except SystemExit:
                    pass
    return saida


def estado_chaves():
    cfg = cv.carregar_config()
    fontes = cv.FontesDeImagem(cfg, "")
    return {"gemini": bool(cfg.get("gemini_api_key")), "imagens": list(fontes.ativos),
            "video": bool(cfg.get("pixabay_api_key"))}


def lista_videos(canal):
    """Lista entregas prontas e agrupa projetos gerados em duracoes independentes (16x9/9x16)."""
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,60}", str(canal or "")):
        return []
    base = (PROJETOS / canal).resolve()
    if PROJETOS.resolve() not in base.parents:
        return []
    saida = []
    if not base.exists():
        return saida
    folders = [p for p in sorted(base.iterdir(), reverse=True) if p.is_dir()]
    groups = {}
    for folder in folders:
        match = re.match(r"^(.*)_(16x9|9x16)$", folder.name)
        key = match.group(1) if match else folder.name
        groups.setdefault(key, []).append((folder, match.group(2) if match else None))
    for key, entries in groups.items():
        entries.sort(key=lambda item: (0 if item[1] == "16x9" else 1 if item[1] == "9x16" else 2, item[0].name))
        primary = entries[0][0]
        rot = {}
        videos = {}
        miniatura = ""
        pub = ""
        for pasta, formato_hint in entries:
            if not rot and (pasta / "roteiro.json").exists():
                try:
                    rot = json.loads((pasta / "roteiro.json").read_text(encoding="utf-8"))
                except Exception:
                    rot = {}
            if not miniatura and (pasta / "miniatura.jpg").exists():
                miniatura = f"{canal}/{pasta.name}/miniatura.jpg"
            if not pub and (pasta / "publicacao.txt").exists():
                pub = (pasta / "publicacao.txt").read_text(encoding="utf-8")
            output_dir = pasta / "saida"
            if output_dir.exists():
                for f in sorted(output_dir.glob("*.mp4")):
                    if f.name.endswith(".parcial.mp4"):
                        continue
                    chave = formato_hint or ("16x9" if f.name.endswith("_16x9.mp4") else "9x16" if f.name.endswith("_9x16.mp4") else f.stem)
                    videos[chave] = f"{canal}/{pasta.name}/saida/{f.name}"
        saida.append({
            "pasta": f"{canal}/{primary.name}", "titulo": rot.get("titulo", key),
            "alternativos": rot.get("titulos_alternativos", []), "descricao": rot.get("descricao", ""),
            "tags": rot.get("tags", []), "videos": videos, "publicacao": pub,
            "miniatura": miniatura, "pronto": bool(videos),
            "formatos_prontos": list(videos.keys()),
        })
    return saida


def caminho_seguro(rel):
    p = (PROJETOS / rel).resolve()
    if PROJETOS.resolve() not in p.parents and p != PROJETOS.resolve():
        return None
    return p


def capturar(fn, *args):
    """Roda uma funcao do pipeline e transforma 'erro()' em mensagem para a tela."""
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            return True, fn(*args)
    except SystemExit:
        texto = re.sub(r"^\s*ERRO:\s*", "", buf.getvalue().strip(), flags=re.M).strip()
        return False, texto or "falha desconhecida"
    except Exception as e:  # noqa
        return False, str(e)


def validar_projeto_video(projeto):
    """Validacao estrutural inicial do contrato intermediario de video."""
    if not isinstance(projeto, dict):
        raise ValueError("O projeto precisa ser um objeto JSON.")
    obrigatorios = ("title", "channel", "category", "engine_id", "deliverables")
    faltando = [k for k in obrigatorios if not projeto.get(k)]
    if faltando:
        raise ValueError("Campos obrigatorios ausentes: " + ", ".join(faltando))
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,60}", str(projeto["channel"])):
        raise ValueError("O campo channel deve ser o nome de uma pasta de canal valido.")
    if not (RAIZ / "canais" / str(projeto["channel"]) / "canal.json").is_file():
        raise ValueError(f"Canal '{projeto['channel']}' nao encontrado.")
    if not get_engine(str(projeto["engine_id"])):
        raise ValueError(f"Motor '{projeto['engine_id']}' nao consta no catalogo.")
    categorias_validas = {x["id"] for x in list_categories()}
    if str(projeto["category"]) not in categorias_validas:
        raise ValueError(f"Categoria '{projeto['category']}' nao consta no catalogo.")
    entregas = projeto["deliverables"]
    if not isinstance(entregas, dict) or not entregas:
        raise ValueError("deliverables deve conter pelo menos uma entrega, por exemplo long ou short.")
    formatos = {"16:9", "9:16", "1:1"}
    for nome, entrega in entregas.items():
        if not isinstance(entrega, dict):
            raise ValueError(f"A entrega '{nome}' deve ser um objeto.")
        if entrega.get("aspect_ratio") not in formatos:
            raise ValueError(f"Formato invalido na entrega '{nome}'. Use 16:9, 9:16 ou 1:1.")
        cenas = entrega.get("scenes", [])
        if not isinstance(cenas, list):
            raise ValueError(f"scenes da entrega '{nome}' deve ser uma lista.")
        for i, cena in enumerate(cenas, 1):
            if not isinstance(cena, dict) or not str(cena.get("narration", "")).strip():
                raise ValueError(f"A cena {i} da entrega '{nome}' precisa ter narration.")
    return projeto



def validar_roteiro_broadcast(roteiro):
    """Valida o roteiro JSON proprio do Broadcast News sem aplicar o schema Classico."""
    if not isinstance(roteiro, dict) or not str(roteiro.get("titulo", "")).strip():
        raise ValueError("O roteiro Broadcast News precisa ter titulo.")
    cenas = roteiro.get("cenas")
    if not isinstance(cenas, list) or len(cenas) < 4:
        raise ValueError("O roteiro Broadcast News precisa ter pelo menos quatro cenas.")
    tipos = {"headline", "stat", "flow", "timeline", "comparison", "chart", "bullets", "quote", "definition"}
    for i, cena in enumerate(cenas, 1):
        if not isinstance(cena, dict) or not str(cena.get("narracao", "")).strip():
            raise ValueError(f"A cena {i} precisa ter narracao.")
        visual = cena.get("visual")
        if not isinstance(visual, dict):
            raise ValueError(f"A cena {i} precisa ter um objeto visual.")
        if str(visual.get("type", "bullets")) not in tipos:
            raise ValueError(f"A cena {i} possui tipo visual desconhecido.")
    return roteiro

def caminho_rascunho(project_id):
    if not re.fullmatch(r"[a-f0-9-]{36}", str(project_id)):
        return None
    base = RASCUNHOS.resolve()
    destino = (RASCUNHOS / f"{project_id}.json").resolve()
    if base not in destino.parents:
        return None
    return destino


def listar_rascunhos():
    RASCUNHOS.mkdir(parents=True, exist_ok=True)
    itens = []
    for arq in sorted(RASCUNHOS.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            p = json.loads(arq.read_text(encoding="utf-8"))
            itens.append({"id": p.get("project_id", arq.stem), "title": p.get("title", arq.stem),
                          "channel": p.get("channel", ""), "category": p.get("category", ""),
                          "engine_id": p.get("engine_id", ""), "updated_at": p.get("updated_at", "")})
        except (OSError, json.JSONDecodeError):
            continue
    return itens


# --------------------------------------------------------------- servidor

class Handler(BaseHTTPRequestHandler):
    server_version = "FabricaVideos/1.0"

    def log_message(self, formato, *args):
        pass

    def _json(self, codigo, dados):
        corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def _corpo(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:  # noqa
            return {}

    def _arquivo(self, caminho, tipo=None):
        if not caminho or not caminho.exists() or not caminho.is_file():
            self.send_error(404)
            return
        tamanho = caminho.stat().st_size
        tipo = tipo or mimetypes.guess_type(str(caminho))[0] or "application/octet-stream"
        inicio, fim, codigo = 0, tamanho - 1, 200
        faixa = self.headers.get("Range")
        if faixa:
            m = re.match(r"bytes=(\d*)-(\d*)", faixa)
            if m:
                if m.group(1):
                    inicio = int(m.group(1))
                    if m.group(2):
                        fim = min(int(m.group(2)), tamanho - 1)
                elif m.group(2):
                    inicio = max(0, tamanho - int(m.group(2)))
                if inicio <= fim:
                    codigo = 206
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        if caminho.suffix.lower() in (".html", ".js", ".css"):
            self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(fim - inicio + 1))
        if codigo == 206:
            self.send_header("Content-Range", f"bytes {inicio}-{fim}/{tamanho}")
        self.end_headers()
        try:
            with open(caminho, "rb") as f:
                f.seek(inicio)
                restante = fim - inicio + 1
                while restante > 0:
                    bloco = f.read(min(1024 * 256, restante))
                    if not bloco:
                        break
                    self.wfile.write(bloco)
                    restante -= len(bloco)
        except (BrokenPipeError, ConnectionResetError):
            pass

    # ---- GET
    def do_GET(self):
        url = urlparse(self.path)
        q = parse_qs(url.query)
        if url.path in ("/", "/index.html"):
            return self._arquivo(RAIZ / "ui" / "index.html", "text/html; charset=utf-8")
        if url.path == "/api/estado":
            try:
                with LOCK:
                    fila = [dict(j, log=j.get("log", [])[-40:]) for j in FILA]
                return self._json(200, {"versao": "1.4.0-seis-melhorias", "canais": lista_canais(),
                                        "chaves": estado_chaves(), "fila": fila,
                                        "motores": engines_health()})
            except BaseException as e:  # noqa  (pega tambem o sys.exit do erro())
                import traceback
                traceback.print_exc()
                return self._json(500, {"erro": f"{type(e).__name__}: {e}"})
        if url.path == "/api/motores":
            return self._json(200, {"motores": list_engines()})
        if url.path == "/api/categorias":
            return self._json(200, {"categorias": list_categories()})
        if url.path == "/api/thumbnails":
            return self._json(200, {"templates": list_thumbnail_templates()})
        if url.path == "/api/saude":
            cfg = cv.carregar_config()
            return self._json(200, {"ok": True, "versao": "1.4.0-seis-melhorias", "python": sys.version.split()[0],
                                    "database": str(STORE.db_path), "database_exists": STORE.db_path.exists(),
                                    "ffmpeg": shutil.which("ffmpeg"), "ffprobe": shutil.which("ffprobe"),
                                    "engines": engines_health(), "jobs": len(FILA),
                                    "secrets": {"gemini": bool(cfg.get("gemini_api_key")),
                                                "pixabay": bool(cfg.get("pixabay_api_key")),
                                                "pexels": bool(cfg.get("pexels_api_key")),
                                                "cloudflare": bool(cfg.get("cloudflare_api_token"))}})
        if url.path == "/api/projetos":
            return self._json(200, {"projetos": listar_rascunhos()})
        if url.path == "/api/projeto":
            destino = caminho_rascunho((q.get("id") or [""])[0])
            if not destino or not destino.is_file():
                return self._json(404, {"erro": "rascunho nao encontrado"})
            return self._json(200, json.loads(destino.read_text(encoding="utf-8")))
        if url.path == "/api/videos":
            return self._json(200, {"videos": lista_videos((q.get("canal") or [""])[0])})
        if url.path == "/api/roteiro":
            p = caminho_seguro((q.get("pasta") or [""])[0])
            if not p or not (p / "roteiro.json").exists():
                return self._json(404, {"erro": "roteiro nao encontrado"})
            return self._json(200, json.loads((p / "roteiro.json").read_text(encoding="utf-8")))
        if url.path.startswith("/media/"):
            return self._arquivo(caminho_seguro(unquote(url.path[len("/media/"):])))
        self.send_error(404)

    # ---- POST
    def do_POST(self):
        url = urlparse(self.path)
        d = self._corpo()
        if url.path == "/api/ideias":
            canal_nome, n = str(d.get("canal", "")), max(1, min(20, int(d.get("n") or 8)))
            if not re.fullmatch(r"[a-zA-Z0-9_-]{1,60}", canal_nome) or not (RAIZ / "canais" / canal_nome / "canal.json").is_file():
                return self._json(400, {"erro": "canal invalido ou nao encontrado"})
            categoria_id = str(d.get("categoria") or "curiosidades")
            categoria = next((x for x in list_categories() if x.get("id") == categoria_id), None)
            if categoria is None:
                return self._json(400, {"erro": "categoria nao encontrada no catalogo"})
            motor = get_engine(str(d.get("motor") or "classico"))
            if motor is None:
                return self._json(400, {"erro": "motor nao encontrado no catalogo"})
            perfil = dict(cv.aplicar_modo_tema(cv.carregar_canal(canal_nome), categoria_id))
            perfil["nicho"] = (str(perfil.get("nicho", "")) + "\nCategoria editorial selecionada: " + categoria.get("name", categoria_id)
                               + ". Direcao visual: " + motor.get("name", "Classico") + ".")
            ok, r = capturar(lambda: cv.sugerir_ideias(perfil, canal_nome, n, cv.carregar_config(), categoria=categoria, motor=str(d.get("motor") or "classico")))
            return self._json(200 if ok else 400, {"ideias": r} if ok else {"erro": r})
        if url.path == "/api/criar":
            temas = [str(t).strip() for t in d.get("temas", []) if str(t).strip()]
            if not temas:
                return self._json(400, {"erro": "escolha ao menos um tema"})
            if len(temas) > 20:
                return self._json(400, {"erro": "limite de 20 temas por envio"})
            formatos_solicitados = [x.strip() for x in str(d.get("formatos") or "16x9,9x16").split(",") if x.strip()]
            if not formatos_solicitados or any(x not in ("16x9", "9x16") for x in formatos_solicitados):
                return self._json(400, {"erro": "formatos aceitos: 16x9 e 9x16"})
            duracao_longa = int(d.get("duracao_longa") or 0)
            duracao_curta = int(d.get("duracao_curta") or 0)
            duracao_comum = int(d.get("duracao") or 0)
            if "16x9" in formatos_solicitados and duracao_longa and not 300 <= duracao_longa <= 600:
                return self._json(400, {"erro": "A duracao do YouTube 16:9 deve ficar entre 5 e 10 minutos."})
            if "9x16" in formatos_solicitados and duracao_curta and not 60 <= duracao_curta <= 120:
                return self._json(400, {"erro": "A duracao do Short 9:16 deve ficar entre 1 e 2 minutos."})
            try:
                novos = []
                # Cada formato vira uma tarefa/projeto independente: roteiro, voz e montagem proprios.
                for tema in temas:
                    for formato in formatos_solicitados:
                        if formato == "16x9":
                            dur = duracao_longa or duracao_comum or 420
                        else:
                            dur = duracao_curta or duracao_comum or 90
                        opcoes_entrega = dict(d)
                        opcoes_entrega.update({"formatos": formato, "duracao": dur, "entrega_format": formato})
                        novos.append(novo_job(d.get("canal", ""), tema, opcoes_entrega))
            except ValueError as e:
                return self._json(409, {"erro": str(e)})
            return self._json(200, {"criados": [j["id"] for j in novos], "versoes_criadas": len(novos), "entregas_por_tema": len(formatos_solicitados)})
        if url.path == "/api/projetos":
            projeto = d.get("projeto") or d
            try:
                validar_projeto_video(projeto)
            except ValueError as e:
                return self._json(400, {"erro": str(e)})
            RASCUNHOS.mkdir(parents=True, exist_ok=True)
            agora = time.strftime("%Y-%m-%dT%H:%M:%S%z")
            projeto = dict(projeto)
            projeto.setdefault("schema_version", "1.0")
            projeto["project_id"] = str(uuid4())
            projeto["status"] = "draft"
            projeto["created_at"] = agora
            projeto["updated_at"] = agora
            destino = caminho_rascunho(projeto["project_id"])
            destino.write_text(json.dumps(projeto, ensure_ascii=False, indent=2), encoding="utf-8")
            return self._json(201, {"ok": True, "id": projeto["project_id"], "arquivo": str(destino)})
        if url.path == "/api/projeto":
            projeto = d.get("projeto") or {}
            destino = caminho_rascunho(projeto.get("project_id", ""))
            if not destino or not destino.is_file():
                return self._json(404, {"erro": "rascunho nao encontrado"})
            try:
                validar_projeto_video(projeto)
            except ValueError as e:
                return self._json(400, {"erro": str(e)})
            anterior = json.loads(destino.read_text(encoding="utf-8"))
            projeto = dict(projeto)
            projeto["created_at"] = anterior.get("created_at")
            projeto["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
            projeto.setdefault("status", "draft")
            destino.write_text(json.dumps(projeto, ensure_ascii=False, indent=2), encoding="utf-8")
            return self._json(200, {"ok": True, "id": projeto["project_id"]})
        if url.path in ("/api/cancelar", "/api/aprovar", "/api/repetir", "/api/remover"):
            with LOCK:
                job = next((j for j in FILA if j["id"] == int(d.get("id") or 0)), None)
                if job is None:
                    return self._json(404, {"erro": "item nao encontrado"})
                if url.path == "/api/cancelar":
                    cancelar(job)
                elif url.path == "/api/aprovar" and job["status"] == "revisar":
                    job.update(status="pendente", revisar=False, etapa_nome="Na fila", progresso=12)
                    persistir_job(job)
                elif url.path == "/api/repetir" and job["status"] in ("erro", "cancelado", "interrompido"):
                    job.update(status="pendente", erro="", cancelado=False, etapa_nome="Na fila — retomando arquivos existentes",
                               progresso=max(0, int(job.get("progresso", 0)) - 1))
                    job.setdefault("log", []).append("[RECUPERACAO] Retomada solicitada pela interface; etapas com arquivos existentes serao reaproveitadas.")
                    persistir_job(job)
                elif url.path == "/api/remover" and job["status"] not in ("rodando",):
                    FILA.remove(job)
                    STORE.remove(job["id"])
            return self._json(200, {"ok": True})
        if url.path == "/api/roteiro":
            p = caminho_seguro(d.get("pasta", ""))
            if not p or not (p / "roteiro.json").exists():
                return self._json(404, {"erro": "roteiro nao encontrado"})
            roteiro = d.get("roteiro") or {}
            rel_pasta = p.resolve().relative_to(PROJETOS.resolve()).as_posix()
            job = next((j for j in FILA if j.get("pasta") == rel_pasta), None)
            cenas = roteiro.get("cenas", []) if isinstance(roteiro, dict) else []
            possui_visual_broadcast = bool(cenas) and isinstance(cenas[0], dict) and isinstance(cenas[0].get("visual"), dict)
            is_broadcast = (job and job.get("motor") in ("broadcast_news", "broadcast_motion")) or possui_visual_broadcast
            validator = validar_roteiro_broadcast if is_broadcast else cv.validar_roteiro
            ok, r = capturar(validator, roteiro)
            if not ok:
                return self._json(400, {"erro": r})
            (p / "roteiro.json").write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
            return self._json(200, {"ok": True})
        if url.path == "/api/abrir":
            p = caminho_seguro(d.get("pasta", ""))
            if not p or not p.exists():
                return self._json(404, {"erro": "pasta nao encontrada"})
            try:
                if os.name == "nt":
                    os.startfile(str(p))  # noqa
                else:
                    subprocess.Popen(["xdg-open", str(p)])
            except Exception as e:  # noqa
                return self._json(500, {"erro": str(e)})
            return self._json(200, {"ok": True})
        self.send_error(404)


def main():
    PROJETOS.mkdir(exist_ok=True)
    RASCUNHOS.mkdir(parents=True, exist_ok=True)
    if INTERRUPTIDOS_NA_INICIALIZACAO:
        print(f"\nRecuperacao: {len(INTERRUPTIDOS_NA_INICIALIZACAO)} tarefa(s) marcada(s) como interrompida(s). Use Retomar na interface quando estiver pronto.\n")
    try:
        servidor = ThreadingHTTPServer(("127.0.0.1", PORTA), Handler)
    except OSError:
        print(f"\nA porta {PORTA} ja esta em uso. Feche a outra janela da Fabrica de videos e tente de novo.\n")
        sys.exit(1)
    threading.Thread(target=trabalhador, daemon=True).start()
    servidor.daemon_threads = True
    print(f"\nFabrica de videos rodando em http://127.0.0.1:{PORTA}")
    print("Mantenha esta janela aberta enquanto usa a interface. Feche-a para encerrar.\n")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
