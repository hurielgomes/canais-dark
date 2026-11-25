"""Adaptador Fábrica -> MyHub Bridge v8.

Usa o servidor local persistente do Bridge: uma única sessão Playwright/Chromium
atende todas as etapas, sem reiniciar o navegador a cada chamada. SVG/JSON são
tratados como dados validados; nenhum código retornado pela IA é executado.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import shutil
import sys
import time
import unicodedata
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Callable, Iterable


class MyHubBridgeError(RuntimeError):
    """Falha ao localizar ou comunicar com o MyHub Bridge."""


class MyHubArtifactMissingError(MyHubBridgeError):
    """O MyHub respondeu, mas o SVG/JSON esperado não foi capturado."""
    no_retry = True


PURPOSES = {
    "planejamento": "roteiro_planejamento",
    "roteiro": "roteiro_criacao",
    "checagem": "roteiro_checagem",
    "otimizacao": "roteiro_otimizacao",
    "refino": "roteiro_refino",
    "direcao_arte": "m1_direcao_arte",
    "recursos_svg": "m1_recursos_svg",
    "recursos_svg_lote": "m1_recursos_svg_lote",
}
TEXT_PURPOSES = {"planejamento", "roteiro", "checagem", "otimizacao", "refino"}


def _bridge_root(cfg: dict, fabrica_root: Path) -> Path:
    raw = os.environ.get("MYHUB_BRIDGE_DIR") or cfg.get("myhub_bridge_dir") or "../myhub-bridge"
    path = Path(os.path.expandvars(str(raw))).expanduser()
    return path.resolve() if path.is_absolute() else (fabrica_root / path).resolve()


def _python_executable(bridge_root: Path) -> Path:
    for rel in (".venv/Scripts/python.exe", ".venv/bin/python", "venv/Scripts/python.exe", "venv/bin/python"):
        candidate = bridge_root / rel
        if candidate.is_file():
            return candidate
    return Path(sys.executable)


def _valid_svg(text: str) -> str | None:
    for match in re.finditer(r"<svg\b[\s\S]*?</svg\s*>", text or "", re.I):
        fragment = match.group(0).strip()
        try:
            root = ET.fromstring(fragment)
            if root.tag.rsplit("}", 1)[-1].lower() == "svg":
                return fragment
        except ET.ParseError:
            continue
    return None


def _artifact_contents(result_dir: Path, metadata: dict) -> list[dict]:
    out = []
    root = result_dir.resolve()
    for item in metadata.get("artifacts") or []:
        if item.get("valid") is False or not item.get("path"):
            continue
        try:
            path = (result_dir / str(item["path"])).resolve()
            path.relative_to(root)
            if not path.is_file() or path.stat().st_size > 20 * 1024 * 1024:
                continue
            content = path.read_text(encoding="utf-8-sig", errors="strict")
            suffix = path.suffix.lower()
            if suffix == ".svg":
                svg = _valid_svg(content)
                if not svg:
                    continue
                content = svg
            elif suffix == ".json":
                value = json.loads(content)
                if not isinstance(value, (dict, list)):
                    continue
            out.append({
                "filename": item.get("filename") or path.name,
                "extension": suffix,
                "content": content,
                "source": item.get("source", "code_block"),
                "valid": True,
            })
        except Exception:
            continue
    return out



def _extract_loose_svg_sidecar(text: str) -> str | None:
    """Recupera JSON de animação que aparece solto após </svg>, sem code block."""
    source = str(text or "")
    end_svg = source.lower().rfind("</svg>")
    tail = source[end_svg + len("</svg>"):] if end_svg >= 0 else source
    decoder = json.JSONDecoder()
    for index, char in enumerate(tail):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(tail[index:])
        except json.JSONDecodeError:
            continue
        if not isinstance(value, dict):
            continue
        keys = {str(key).strip().lower() for key in value}
        if keys.intersection({"partes", "animacoes", "animações", "pose_base", "camadas"}):
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return None


def _is_svg_generation_refusal(response: str, metadata: dict | None = None,
                               artifacts: list[dict] | None = None) -> bool:
    """Só classifica recusa quando não existe SVG válido na resposta/artefatos."""
    if _valid_svg(response):
        return False
    if any(item.get("extension") == ".svg" and item.get("valid", True) for item in (artifacts or [])):
        return False
    text = str(response or "").casefold()
    patterns = (
        r"n[aã]o consigo.{0,100}(?:gerar|anexar|criar|enviar).{0,100}(?:svg|arquivo|ilustra[cç][aã]o)",
        r"n[aã]o posso.{0,100}(?:gerar|anexar|criar|enviar).{0,100}(?:svg|arquivo|ilustra[cç][aã]o)",
        r"(?:para|acesse|abra).{0,50}(?:aba|ferramenta|se[cç][aã]o)?\s*(?:de\s*)?(?:gera[cç][aã]o\s*de\s*)?imagens",
        r"(?:svg|arquivos?\s+svg).{0,80}(?:n[aã]o est[aá] dispon[ií]vel|n[aã]o consigo|n[aã]o posso)",
    )
    return any(re.search(pattern, text, re.I | re.S) for pattern in patterns)


def _fresh_chat_key(chat: str, prompt: str) -> str:
    digest = hashlib.sha1(f"{chat}|{prompt}|{time.time_ns()}".encode("utf-8")).hexdigest()[:10]
    return f"{str(chat)[:78]}__fresh_{digest}"[:100]

def _choose_model(cfg: dict, purpose: str | None, json_mode: bool | None = None) -> str:
    if purpose in TEXT_PURPOSES:
        return str(cfg.get("myhub_model_texto") or cfg.get("myhub_model") or "GPT-6 Luna")
    if purpose in {"direcao_arte", "recursos_svg", "recursos_svg_lote"} or purpose is None:
        return str(cfg.get("myhub_model_artes") or cfg.get("m1_myhub_model") or cfg.get("myhub_model") or "GPT-6 Luna")
    if json_mode is False:
        return str(cfg.get("myhub_model_artes") or cfg.get("m1_myhub_model") or "GPT-6 Luna")
    return str(cfg.get("myhub_model_texto") or cfg.get("myhub_model") or "GPT-6 Luna")


def _asset_chat_key(scope: str, label: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(label).lower())
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    slug = re.sub(r"[^a-z0-9]+", "_", normalized).strip("_") or "recurso"
    project = re.sub(r"[^a-z0-9_.-]+", "_", str(scope).lower()).strip("_.-") or "projeto"
    digest = hashlib.sha1(f"{scope}|{label}".encode("utf-8")).hexdigest()[:8]
    return f"fabrica_m1__svg__{project[:24]}__{slug[:30]}_{digest}"[:100]


class _BridgeClient:
    def __init__(self, root: Path, python: Path, cfg: dict, log: Callable[[str], None], timeout: int):
        self.root, self.python, self.cfg, self.log, self.timeout = root, python, cfg, log, timeout
        self.host = str(cfg.get("myhub_bridge_host", "127.0.0.1"))
        self.port = int(cfg.get("myhub_bridge_port", 8766))
        self.base = f"http://{self.host}:{self.port}"

    def _health(self) -> bool:
        try:
            with urllib.request.urlopen(self.base + "/health", timeout=1.5) as response:
                data = json.loads(response.read().decode("utf-8"))
                return bool(data.get("ok"))
        except Exception:
            return False

    def ensure_running(self) -> None:
        if self._health():
            return
        main = self.root / "main.py"
        if not main.is_file():
            raise MyHubBridgeError(f"MyHub Bridge não encontrado: {self.root}")
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        kwargs = {"cwd": str(self.root), "env": env, "stdin": subprocess.DEVNULL,
                  "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "close_fds": True}
        if os.name == "nt":
            kwargs["creationflags"] = getattr(subprocess, "DETACHED_PROCESS", 0x00000008) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        try:
            subprocess.Popen([str(self.python), str(main), "--serve"], **kwargs)
        except OSError as exc:
            raise MyHubBridgeError(f"Não consegui iniciar a sessão persistente do Bridge: {exc}") from exc
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            if self._health():
                self.log("   MyHub Bridge: sessão persistente do navegador iniciada.")
                return
            time.sleep(0.4)
        raise MyHubBridgeError(
            "A sessão persistente do MyHub Bridge não iniciou em 40s. "
            "Execute login.bat, confira o perfil do Chromium e verifique logs/myhub-bridge.log."
        )

    def submit(self, job: dict) -> Path:
        self.ensure_running()
        body = json.dumps(job, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self.base + "/job", data=body,
            headers={"Content-Type": "application/json; charset=utf-8"}, method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout + 40) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            try:
                detail = json.loads(detail).get("error", detail)
            except Exception:
                pass
            raise MyHubBridgeError(f"Bridge HTTP {exc.code}: {str(detail)[:1500]}") from exc
        except Exception as exc:
            raise MyHubBridgeError(f"Falha de comunicação com a sessão persistente do Bridge: {exc}") from exc
        if not result.get("ok") or not result.get("result_dir"):
            raise MyHubBridgeError(str(result.get("error") or "Bridge não retornou a pasta de resultado."))
        return Path(result["result_dir"])



def bridge_disponivel(
    cfg: dict | str | Path | None = None,
    fabrica_root: str | Path | dict | None = None,
    log: Callable[[str], None] = print,
    *,
    iniciar: bool = False,
) -> bool:
    """Verifica se o MyHub Bridge está instalado e utilizável pela Fábrica.

    API de compatibilidade pública usada por módulos do pipeline:
        bridge_disponivel()
        bridge_disponivel(cfg, fabrica_root)
        bridge_disponivel(fabrica_root)

    Por padrão verifica somente se a instalação está presente (main.py e
    config.json). Isso é intencional: o pipeline consulta esta função para
    escolher entre MyHub e Gemini, inclusive ao montar o painel de status.
    O serviço é iniciado por ``_BridgeClient.submit`` quando um job real é
    enviado. Use ``iniciar=True`` apenas quando quiser forçar a checagem de
    saúde e iniciar o serviço, se necessário.
    Nunca altera config, perfil do navegador ou dados do Bridge.
    """
    # Aceita também bridge_disponivel(CAMINHO_DA_FABRICA) e a ordem
    # bridge_disponivel(CAMINHO_DA_FABRICA, cfg), por compatibilidade.
    if isinstance(cfg, (str, Path)):
        if isinstance(fabrica_root, dict):
            cfg, fabrica_root = fabrica_root, cfg
        elif fabrica_root is None:
            fabrica_root, cfg = cfg, None

    settings: dict = dict(cfg) if isinstance(cfg, dict) else {}
    root = Path(fabrica_root or Path(__file__).resolve().parent).expanduser().resolve()

    # Quando a chamada antiga não passa cfg, tenta carregar apenas a
    # configuração local da Fábrica; se não existir, usa os defaults seguros.
    if not settings:
        for candidate in (root / "config.json", root / "configuracao.json"):
            try:
                if candidate.is_file():
                    loaded = json.loads(candidate.read_text(encoding="utf-8-sig"))
                    if isinstance(loaded, dict):
                        settings = loaded
                        break
            except Exception:
                continue

    try:
        bridge_root = _bridge_root(settings, root)
        if not (bridge_root / "main.py").is_file():
            return False
        if not (bridge_root / "config.json").is_file():
            return False

        host = str(settings.get("myhub_bridge_host", "127.0.0.1"))
        try:
            port = int(settings.get("myhub_bridge_port", 8766))
        except (TypeError, ValueError):
            port = 8766
        base = f"http://{host}:{port}"

        def health_ok() -> bool:
            try:
                with urllib.request.urlopen(base + "/health", timeout=1.5) as response:
                    data = json.loads(response.read().decode("utf-8"))
                    return bool(data.get("ok"))
            except Exception:
                return False

        if not iniciar:
            # Os chamadores atuais usam a função para detectar uma instalação
            # configurada, não para iniciar Chromium durante a consulta.
            return True
        if health_ok():
            return True

        timeout = max(45, int(settings.get("m1_myhub_timeout_seconds", 900)))
        client = _BridgeClient(bridge_root, _python_executable(bridge_root), settings, log, timeout)
        client.ensure_running()
        return health_ok()
    except Exception as exc:
        try:
            log(f"   MyHub Bridge indisponível: {exc}")
        except Exception:
            pass
        return False


def _prefer_json_artifact(response: str, artifacts: list[dict], json_mode: bool, outputs: Iterable[str], log: Callable[[str], None]) -> str:
    """Quando o MyHub abre JSON no code pane lateral, usa o artefato validado.

    O texto normal da mensagem pode ser somente um resumo curto (ex.:
    'Roteiro completo em JSON...'), enquanto o conteúdo real está em artifacts/.
    """
    expects_json = any(str(item).lower().lstrip(".") == "json" for item in outputs)
    if not json_mode or not expects_json:
        return response
    item = next((artifact for artifact in artifacts if artifact.get("extension") == ".json" and artifact.get("valid", True)), None)
    if not item:
        return response
    content = str(item.get("content", "")).strip()
    if content:
        log("   MyHub Bridge: JSON estruturado recuperado como artefato validado.")
        return content
    return response

def criar_llm_myhub(
    cfg: dict,
    fabrica_root: Path,
    log: Callable[[str], None] = print,
    *,
    purpose: str | None = None,
    chat_key: str | None = None,
    expected_outputs: Iterable[str] | None = None,
    chat_scope: str | None = None,
):
    fabrica_root = Path(fabrica_root).resolve()
    bridge_root = _bridge_root(cfg, fabrica_root)
    if not (bridge_root / "main.py").is_file() or not (bridge_root / "config.json").is_file():
        raise MyHubBridgeError(f"MyHub Bridge incompleto ou não encontrado: {bridge_root}")
    python = _python_executable(bridge_root)
    timeout_key = "myhub_timeout_seconds" if purpose else "m1_myhub_timeout_seconds"
    timeout = max(180, int(cfg.get(timeout_key, cfg.get("m1_myhub_timeout_seconds", 900))))
    bridge = _BridgeClient(bridge_root, python, cfg, log, timeout)
    requests_dir = fabrica_root / "data" / "myhub_requests"
    requests_dir.mkdir(parents=True, exist_ok=True)

    scope = ""
    if chat_scope:
        normalized = unicodedata.normalize("NFKD", str(chat_scope).lower())
        normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        scope = re.sub(r"[^a-z0-9_.-]+", "_", normalized).strip("_.-")[:36]

    def submit(prompt: str, *, stage: str, chat: str, outputs: list[str], model: str,
               capture_all_downloads: bool = False) -> tuple[Path, dict]:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("A Fábrica tentou enviar um prompt vazio ao MyHub.")
        job_id = f"fabrica_{stage}_{os.getpid()}_{time.time_ns() % 10**12:012d}"
        job = {
            "id": job_id,
            "project": "fabrica_videos",
            "purpose": stage,
            "chat_key": chat,
            "model": model,
            "prompt": prompt,
            "expected_outputs": outputs,
            "metadata": {
                "caller": "Fábrica de Vídeos",
                "pipeline_stage": purpose or stage,
                "capture_all_downloads": bool(capture_all_downloads),
            },
        }
        log(f"   MyHub Bridge: enviando {stage} ({chat}) — modelo {model}")
        result_dir = bridge.submit(job)
        meta_path, text_path = result_dir / "response.json", result_dir / "response.txt"
        if not meta_path.is_file() or not text_path.is_file():
            raise MyHubBridgeError(f"Bridge não criou response.json/response.txt em {result_dir}")
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            raise MyHubBridgeError(f"response.json inválido: {exc}") from exc
        if not meta.get("success"):
            raise MyHubBridgeError("Bridge não confirmou sucesso no MyHub.")
        return result_dir, meta

    def submit_svg_with_refusal_retry(prompt: str, *, stage: str, chat: str, outputs: list[str],
                                      model: str, capture_all_downloads: bool = False):
        """Tenta uma vez no mesmo chat e, se persistir a recusa, em chat novo.

        Quando uma tentativa recusada é superada, move seu diretório de resultado
        para results/_tentativas_recusadas, preservando os logs sem deixar pastas
        sem SVG misturadas aos resultados finais do pipeline.
        """
        attempts = [(chat, "tentativa inicial"), (chat, "repetição no mesmo chat")]
        attempts.append((_fresh_chat_key(chat, prompt), "repetição em conversa nova"))
        last = None
        refused_dirs: list[Path] = []

        def archive_refused_dirs(keep_last: bool = False) -> None:
            pending = refused_dirs[:-1] if keep_last and refused_dirs else list(refused_dirs)
            for rejected_dir in pending:
                try:
                    if not rejected_dir.is_dir():
                        continue
                    archive_root = rejected_dir.parent / "_tentativas_recusadas"
                    archive_root.mkdir(parents=True, exist_ok=True)
                    destination = archive_root / rejected_dir.name
                    if destination.exists():
                        destination = archive_root / f"{rejected_dir.name}_{time.time_ns() % 10**9:09d}"
                    shutil.move(str(rejected_dir), str(destination))
                    log(f"   MyHub Bridge: tentativa recusada arquivada em {destination.name}.")
                except Exception as exc:
                    log(f"   MyHub Bridge: não foi possível arquivar tentativa recusada: {exc}")

        for number, (attempt_chat, label) in enumerate(attempts, start=1):
            result_dir, meta = submit(
                prompt, stage=stage, chat=attempt_chat, outputs=outputs, model=model,
                capture_all_downloads=capture_all_downloads,
            )
            response_text = (result_dir / "response.txt").read_text(encoding="utf-8-sig").strip()
            found_artifacts = _artifact_contents(result_dir, meta)
            last = (result_dir, meta, response_text, found_artifacts)
            if not _is_svg_generation_refusal(response_text, meta, found_artifacts):
                archive_refused_dirs()
                return last
            refused_dirs.append(result_dir)
            if number == 1:
                log("   MyHub Bridge: o MyHub recusou o SVG e abriu/indicou Geração de Imagens; repetindo no mesmo chat.")
            elif number == 2:
                log("   MyHub Bridge: a recusa persistiu; abrindo uma conversa nova e repetindo uma última vez.")
            else:
                log("   MyHub Bridge: recusa persistente também na conversa nova; recurso será ignorado e seguirá o fallback procedural.")
                archive_refused_dirs(keep_last=True)
        return last

    def llm(prompt: str, json_mode: bool = True) -> str:
        if purpose:
            stage = PURPOSES.get(purpose, purpose)
            chat = chat_key or f"fabrica__{stage}" + (f"__{scope}" if scope else "")
            outputs = list(expected_outputs) if expected_outputs is not None else ["json"]
            model = _choose_model(cfg, purpose, json_mode)
        else:
            stage = "direcao_arte" if json_mode else "recursos_svg"
            chat = chat_key or f"fabrica_m1__{stage}" + (f"__{scope}" if scope else "")
            if stage == "recursos_svg" and not chat_key:
                match = re.search(r"(?mi)^\s*DESENHE:\s*([^\r\n]+)", prompt or "")
                if match:
                    chat = _asset_chat_key(scope or "projeto", match.group(1).strip())
            outputs = list(expected_outputs) if expected_outputs is not None else (["json"] if json_mode else ["svg", "json_sidecar"])
            model = _choose_model(cfg, stage, json_mode)
        if stage in {"recursos_svg", "m1_recursos_svg", "m1_recursos_svg_lote"}:
            result_dir, meta, response, artifacts = submit_svg_with_refusal_retry(
                prompt, stage=stage, chat=chat, outputs=outputs, model=model,
            )
            if _is_svg_generation_refusal(response, meta, artifacts):
                raise MyHubArtifactMissingError(
                    "O MyHub recusou a geração de SVG mesmo após duas tentativas no chat original "
                    "e uma tentativa em uma conversa nova. O recurso deve seguir o fallback procedural."
                )
        else:
            result_dir, meta = submit(prompt, stage=stage, chat=chat, outputs=outputs, model=model)
            response = (result_dir / "response.txt").read_text(encoding="utf-8-sig").strip()
            artifacts = _artifact_contents(result_dir, meta)

        # Em respostas estruturadas, prioriza o JSON real capturado no code pane.
        response = _prefer_json_artifact(response, artifacts, json_mode, outputs, log)

        if stage in {"recursos_svg", "m1_recursos_svg", "m1_recursos_svg_lote"}:
            # Preserve o texto original antes de priorizar o SVG salvo como artefato.
            # O JSON do rig pode estar solto logo após </svg>, sem ser bloco de código.
            original_response = response
            svg = next((a["content"] for a in artifacts if a["extension"] == ".svg" and a.get("source") in {"download", "myhub_code_block_download", "myhub_code_panel_download"}), None)
            if not svg:
                svg = next((a["content"] for a in artifacts if a["extension"] == ".svg"), None)
            if not svg:
                svg = _valid_svg(original_response)
            if not svg:
                rejected = meta.get("rejected_artifacts") or []
                names = ", ".join(str(x.get("filename", "arquivo")) for x in rejected[:3])
                raise MyHubArtifactMissingError(
                    "O MyHub terminou, mas não retornou SVG íntegro." + (f" Arquivos rejeitados: {names}." if names else "")
                )
            response = svg
            wants_sidecar = any(str(x).lower().lstrip(".") in {"json_sidecar", "sidecar"} for x in outputs)
            if wants_sidecar:
                side = next((a["content"] for a in artifacts if a["extension"] == ".json" and a.get("valid", True)), None)
                if not side:
                    side = _extract_loose_svg_sidecar(original_response)
                if side:
                    response += "\n" + side
                    log("   MyHub Bridge: JSON de animação/rig preservado junto ao SVG.")
        if not response:
            raise MyHubBridgeError("O MyHub retornou uma resposta vazia.")
        log(f"   MyHub Bridge: resposta recebida ({len(response)} caracteres; {len(artifacts)} artefatos válidos)")
        return response

    def request_artifacts(prompt: str, *, chat: str, outputs: Iterable[str] = ("svg",),
                          capture_all_downloads: bool = True, model: str | None = None) -> dict:
        """Solicita um lote de arquivos e devolve conteúdo dos anexos válidos + resposta."""
        stage = "recursos_svg_lote"
        selected_model = model or _choose_model(cfg, stage, False)
        result_dir, meta, response, artifacts = submit_svg_with_refusal_retry(
            prompt, stage=stage, chat=chat, outputs=list(outputs), model=selected_model,
            capture_all_downloads=capture_all_downloads,
        )
        refused = _is_svg_generation_refusal(response, meta, artifacts)
        if refused:
            meta = dict(meta)
            meta["svg_refusal_retries_exhausted"] = True
            artifacts = []
        log(f"   MyHub Bridge: lote recebido ({len(artifacts)} arquivos válidos; {len(response)} caracteres de texto)"
            + (" — recusa persistente, fallback procedural será usado." if refused else ""))
        return {"text": response, "artifacts": artifacts, "metadata": meta, "result_dir": str(result_dir)}

    llm.request_artifacts = request_artifacts  # type: ignore[attr-defined]
    llm.batch_scope = scope or "projeto"  # type: ignore[attr-defined]
    llm.model_texto = str(cfg.get("myhub_model_texto") or cfg.get("myhub_model") or "GPT-6 Luna")  # type: ignore[attr-defined]
    llm.model_artes = str(cfg.get("myhub_model_artes") or cfg.get("m1_myhub_model") or "GPT-6 Luna")  # type: ignore[attr-defined]
    return llm
