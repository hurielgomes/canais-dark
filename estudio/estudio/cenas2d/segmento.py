"""
segmento.py - renderiza UMA cena do M1 em um MP4 sem audio (segmento). Seguro para rodar em processos paralelos
(nao importa criar_video; so Pillow + FFmpeg). O pipeline (criar_cenas2d.py) concatena os segmentos e mistura o audio.

    renderizar_segmento({"cena": {...}, "w": 1080, "h": 1920, "fps": 24, "n": 180, "destino": "cena_01.mp4",
                         "biblioteca": "biblioteca_m1", "canal": {...}})   ->  {"ok": True, "avisos": [...], "usos": {...}}
"""
import subprocess
import time
from pathlib import Path


def renderizar_segmento(args):
    try:
        return _renderizar(args)
    except Exception as e:      # noqa: BLE001 - o processo-pai decide o que fazer
        return {"ok": False, "erro": f"{type(e).__name__}: {e}", "avisos": [], "usos": {}}


def _renderizar(a):
    from ..estilos.cenas2d import Estilo, normalizar
    from ..nucleo import Tela
    from .recursos.biblioteca import Biblioteca

    w, h, fps, n = int(a["w"]), int(a["h"]), int(a["fps"]), int(a["n"])
    destino = Path(a["destino"])
    tmp = destino.with_name(destino.stem + ".parcial.mp4")
    log = destino.with_suffix(".log")
    bib = Biblioteca(a["biblioteca"], aprovacao="auto", bloquear_pendentes=True)
    cena, avisos_norm = normalizar(a["cena"])
    est = Estilo(w, h, a.get("preset", "alerta_noturno"), bib)
    tela = Tela(w, h, 1)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps),
           "-i", "-", "-an", "-c:v", "libx264", "-preset", a.get("preset_x264", "veryfast"), "-crf", str(a.get("crf", 19)),
           "-pix_fmt", "yuv420p", str(tmp)]
    t0 = time.time()
    with open(log, "wb") as lg:
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=lg)
        try:
            for k in range(n):
                est.quadro(tela, k / fps, cena, a.get("canal") or {})
                p.stdin.write(tela.img.tobytes())
        finally:
            try:
                p.stdin.close()
            except OSError:
                pass
            rc = p.wait()
    if rc != 0:
        return {"ok": False, "erro": f"ffmpeg falhou (codigo {rc}); veja {log.name}", "avisos": [], "usos": {}}
    tmp.replace(destino)
    log.unlink(missing_ok=True)
    avisos = sorted(set(list(avisos_norm) + list(bib.problemas)))
    return {"ok": True, "avisos": avisos, "usos": {k: dict(v) for k, v in bib.usos.items()}, "segundos": round(time.time() - t0, 1)}


def quadro_png(cena, w, h, t, biblioteca, destino, canal=None, preset="alerta_noturno"):
    """salva um quadro (para a miniatura). Retorna o caminho."""
    from ..estilos.cenas2d import Estilo, normalizar
    from ..nucleo import Tela
    from .recursos.biblioteca import Biblioteca
    bib = Biblioteca(biblioteca, aprovacao="auto", bloquear_pendentes=True)
    c, _ = normalizar(cena)
    tela = Tela(w, h, 1)
    Estilo(w, h, preset, bib).quadro(tela, t, c, canal or {})
    tela.img.save(str(destino))
    return destino
