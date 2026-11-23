"""tts_voicebox.py - narracao pelo Voicebox (servidor local, gratuito) no lugar do Kokoro.

Ativacao (no canais/<canal>/canal.json):
    "tts": {"motor": "voicebox", "engine": "qwen", "perfil": "Minha Voz", "idioma": "pt"}
Sem o campo "tts" (ou com "motor": "kokoro") tudo continua como antes.

O Voicebox precisa estar aberto (servidor em http://127.0.0.1:17493). Este cliente aceita as variacoes conhecidas da API:
  - /generate devolvendo o audio direto, OU um JSON com o id da geracao (fila assincrona)  -> consulta /history/{id}
    e baixa em /history/{id}/export-audio;
  - HTTP 202 enquanto o modelo ainda esta sendo baixado -> espera e tenta de novo.
Nada de rede externa: so conversa com o localhost.
"""
import json
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

URL_PADRAO = "http://127.0.0.1:17493"
PRONTO = {"completed", "complete", "done", "ready", "success", "succeeded", "finished", "ok"}
FALHA = {"failed", "error", "cancelled", "canceled"}


class VoiceboxErro(RuntimeError):
    pass


def _cfg(canal):
    t = dict((canal or {}).get("tts") or {})
    t.setdefault("url", URL_PADRAO)
    t["url"] = str(t["url"]).rstrip("/")
    return t


def _req(url, metodo="GET", corpo=None, timeout=30):
    data = json.dumps(corpo).encode("utf-8") if corpo is not None else None
    req = urllib.request.Request(url, data=data, method=metodo, headers={"Content-Type": "application/json"} if data is not None else {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read()
    except urllib.error.HTTPError as e:
        return e.code, (e.headers.get("Content-Type", "") if e.headers else ""), e.read()
    except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as e:
        raise VoiceboxErro(f"nao consegui falar com o Voicebox em {url} ({e}). Abra o Voicebox e tente de novo.")


def _json(corpo):
    try:
        return json.loads(corpo.decode("utf-8", "ignore") or "null")
    except ValueError:
        return None


def _eh_wav(corpo):
    return corpo[:4] == b"RIFF" or corpo[:4] == b"fLaC" or corpo[:3] == b"ID3" or corpo[:4] == b"OggS"


def garantir_servidor(cfg, log=print):
    """health check; se o servidor estiver fechado e 'exe' estiver configurado, abre o Voicebox e espera"""
    try:
        code, _, _ = _req(cfg["url"] + "/health", timeout=5)
        if code < 500:
            return
    except VoiceboxErro:
        exe = cfg.get("exe")
        if not exe or not Path(exe).exists():
            raise
        log("   abrindo o Voicebox...")
        subprocess.Popen([str(exe)], close_fds=True)
        fim = time.time() + float(cfg.get("espera_servidor_s", 120))
        while time.time() < fim:
            time.sleep(3)
            try:
                code, _, _ = _req(cfg["url"] + "/health", timeout=5)
                if code < 500:
                    return
            except VoiceboxErro:
                continue
        raise VoiceboxErro("o Voicebox nao respondeu a tempo depois de aberto")


def _lista_perfis(cfg):
    code, _, corpo = _req(cfg["url"] + "/profiles", timeout=30)
    if code >= 400:
        raise VoiceboxErro(f"nao consegui listar os perfis de voz (HTTP {code})")
    js = _json(corpo)
    if isinstance(js, dict):
        js = js.get("profiles") or js.get("items") or js.get("data") or []
    return [p for p in (js or []) if isinstance(p, dict)]


def achar_perfil(cfg):
    if cfg.get("perfil_id"):
        return str(cfg["perfil_id"])
    nome = str(cfg.get("perfil") or "").strip().casefold()
    perfis = _lista_perfis(cfg)
    if not perfis:
        raise VoiceboxErro("o Voicebox nao tem nenhum perfil de voz. Crie um no app (clone ou voz de preset).")
    if not nome:
        return str(perfis[0].get("id"))
    for p in perfis:
        if str(p.get("name", "")).strip().casefold() == nome:
            return str(p["id"])
    raise VoiceboxErro(f"perfil '{cfg.get('perfil')}' nao encontrado. Perfis existentes: {', '.join(str(p.get('name')) for p in perfis)}")


def _id_da_geracao(js):
    if isinstance(js, dict):
        for k in ("id", "generation_id", "history_id", "gen_id"):
            if js.get(k):
                return str(js[k])
        for k in ("generation", "data", "result"):
            if isinstance(js.get(k), dict):
                r = _id_da_geracao(js[k])
                if r:
                    return r
    return None


def _baixar(cfg, js, base_url):
    """tenta obter os bytes do audio a partir da resposta JSON"""
    for k in ("audio_path", "path", "file", "file_path"):
        v = js.get(k) if isinstance(js, dict) else None
        if v and Path(str(v)).exists():
            return Path(str(v)).read_bytes()
    for k in ("audio_url", "url", "audio"):
        v = js.get(k) if isinstance(js, dict) else None
        if isinstance(v, str) and v:
            code, _, corpo = _req(v if v.startswith("http") else base_url + (v if v.startswith("/") else "/" + v), timeout=120)
            if code == 200 and _eh_wav(corpo):
                return corpo
    return None


def gerar_wav_bytes(texto, cfg, perfil_id, instruct=None, log=print):
    corpo_req = {"text": texto, "profile_id": perfil_id, "language": cfg.get("idioma", "pt"), "engine": cfg.get("engine", "qwen")}
    for k_cfg, k_api in (("modelo", "model_size"), ("seed", "seed")):
        if cfg.get(k_cfg) not in (None, ""):
            corpo_req[k_api] = cfg[k_cfg]
    if instruct:
        corpo_req["instruct"] = instruct
    limite = float(cfg.get("timeout_s", 1800))
    t0 = time.time()
    while True:
        code, ctype, corpo = _req(cfg["url"] + "/generate", "POST", corpo_req, timeout=limite)
        if code == 202 and not _eh_wav(corpo) and (_json(corpo) or {}).get("status") in (None, "downloading", "model_downloading", "loading"):
            if time.time() - t0 > float(cfg.get("espera_modelo_s", 1800)):
                raise VoiceboxErro("o modelo de voz ainda esta sendo baixado/carregado; tente de novo em alguns minutos")
            log("   Voicebox: baixando/carregando o modelo de voz, aguardando...")
            time.sleep(10)
            continue
        break
    if code >= 400:
        raise VoiceboxErro(f"Voicebox recusou a geracao: HTTP {code} {corpo[:300].decode('utf-8', 'ignore')}")
    if ctype.lower().startswith("audio/") or _eh_wav(corpo):
        return corpo
    js = _json(corpo)
    if not isinstance(js, dict):
        raise VoiceboxErro("resposta inesperada do Voicebox (nem audio nem JSON)")
    direto = _baixar(cfg, js, cfg["url"])
    gid = _id_da_geracao(js)
    if direto and not gid:
        return direto
    if not gid:
        raise VoiceboxErro(f"a resposta do Voicebox nao traz o id da geracao: {str(js)[:200]}")
    # fila assincrona: consulta o historico ate ficar pronto
    while time.time() - t0 < limite:
        code, _, corpo = _req(f"{cfg['url']}/history/{gid}", timeout=30)
        h = _json(corpo) if code < 400 else None
        st = str((h or js).get("status", "")).lower() if isinstance(h or js, dict) else ""
        if st in FALHA:
            raise VoiceboxErro(f"a geracao falhou no Voicebox: {str((h or js).get('error') or (h or js).get('detail') or st)[:200]}")
        if st in PRONTO or not st:
            code, _, wav = _req(f"{cfg['url']}/history/{gid}/export-audio", timeout=120)
            if code == 200 and _eh_wav(wav):
                return wav
            if isinstance(h, dict):
                alt = _baixar(cfg, h, cfg["url"])
                if alt:
                    return alt
        time.sleep(float(cfg.get("intervalo_s", 1.5)))
    raise VoiceboxErro("tempo esgotado esperando o Voicebox gerar a voz (aumente tts.timeout_s se o PC for lento)")


def _ler_audio(wav_bytes):
    import io

    import numpy as np
    import soundfile as sf
    dados, taxa = sf.read(io.BytesIO(wav_bytes), dtype="float32", always_2d=True)
    return np.ascontiguousarray(dados.mean(axis=1), dtype=np.float32), int(taxa)


def _ajustar_velocidade(dados, taxa, v):
    """acelera/desacelera SEM mudar o tom (ffmpeg atempo); v=1.0 nao faz nada"""
    if abs(v - 1.0) < 0.02:
        return dados
    import numpy as np
    import soundfile as sf
    filtros = []
    r = float(v)
    while r > 2.0:
        filtros.append("atempo=2.0")
        r /= 2.0
    while r < 0.5:
        filtros.append("atempo=0.5")
        r /= 0.5
    filtros.append(f"atempo={r:.4f}")
    with tempfile.TemporaryDirectory() as tmp:
        a, b = Path(tmp) / "a.wav", Path(tmp) / "b.wav"
        sf.write(str(a), dados, taxa)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(a), "-filter:a", ",".join(filtros), str(b)], check=True)
        out, _ = sf.read(str(b), dtype="float32", always_2d=True)
    return np.ascontiguousarray(out.mean(axis=1), dtype=np.float32)


def instruct_para(texto, cfg):
    """instrucao de entrega (so o Qwen CustomVoice usa): pergunta recebe tom proprio"""
    if str(texto).strip().endswith("?") and cfg.get("instruct_pergunta"):
        return cfg["instruct_pergunta"]
    return cfg.get("instruct")


def narrar(texto, canal, gancho=False, log=print):
    """-> (amostras float32 mono, taxa). Levanta VoiceboxErro se algo falhar (quem chama decide o fallback)."""
    cfg = _cfg(canal)
    garantir_servidor(cfg, log)
    perfil = achar_perfil(cfg)
    wav = gerar_wav_bytes(texto, cfg, perfil, instruct_para(texto, cfg), log)
    dados, taxa = _ler_audio(wav)
    vel = float(cfg.get("velocidade", 1.0)) * (float(cfg.get("velocidade_gancho", 1.0)) if gancho else 1.0)
    return _ajustar_velocidade(dados, taxa, vel), taxa
