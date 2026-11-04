"""broadcast_news_fx.py - Broadcast News com movimento, transicoes e texto animado."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import broadcast_news as bn  # noqa: E402

cv = bn.cv
FPS = 30
TRANS = 0.45
TRANSICOES = ["fade", "slideleft", "dissolve", "wipeleft", "slideright"]

# (zoom_ini, zoom_fim, x_ini, x_fim, y_ini, y_fim)
MOV_CARTAO = [
    (1.00, 1.06, .5, .5, .5, .5),
    (1.06, 1.00, .5, .5, .5, .5),
    (1.04, 1.04, .2, .8, .5, .5),
    (1.04, 1.04, .8, .2, .5, .5),
    (1.00, 1.05, .5, .5, .3, .7),
]
MOV_FOTO = [
    (1.00, 1.20, .5, .5, .5, .5),
    (1.18, 1.18, .1, .9, .5, .5),
    (1.22, 1.00, .5, .5, .5, .5),
    (1.18, 1.18, .9, .1, .5, .5),
    (1.00, 1.18, .3, .7, .2, .8),
]


def ff(args):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r


def ff_ou_erro(args, msg):
    r = ff(args)
    if r.returncode != 0:
        raise bn.BroadcastError(msg + ": " + (r.stderr or "")[-900:])


def zoompan(frames, w, h, mov):
    z0, z1, x0, x1, y0, y1 = mov
    p = f"on/{max(1, frames - 1)}"
    return (f"zoompan=z='{z0}+({z1}-{z0})*{p}'"
            f":x='(iw-iw/zoom)*({x0}+({x1}-{x0})*{p})'"
            f":y='(ih-ih/zoom)*({y0}+({y1}-{y0})*{p})'"
            f":d={frames}:s={w}x{h}:fps={FPS}")


def criar_fundo(scene, i, total, nome, categoria, fonte, fmt, destino):
    """Cartao sem titulo e sem conteudo: so cabecalho, rodape e identidade."""
    visual = scene.get("visual") if isinstance(scene.get("visual"), dict) else {}
    vazio = {"type": "bullets", "headline": " ", "kicker": visual.get("kicker") or categoria}
    original = bn.draw_visual
    bn.draw_visual = lambda *a, **k: None
    try:
        bn.create_scene_card({"narracao": " ", "visual": vazio}, i, total, nome, categoria, fonte, fmt, destino)
    finally:
        bn.draw_visual = original


def clip_cartao(fundo, cheio, frames, w, h, mov, destino):
    zp = zoompan(frames, w, h, mov)
    fc = (f"[0:v]scale={2*w}:{2*h}:flags=lanczos,{zp},setsar=1[bg];"
          f"[1:v]scale={2*w}:{2*h}:flags=lanczos,{zp},format=rgba,"
          f"fade=t=in:st=0.25:d=0.7:alpha=1[fg];"
          f"[bg][fg]overlay=format=auto,format=yuv420p[v]")
    ff_ou_erro(["-i", str(fundo), "-i", str(cheio), "-filter_complex", fc, "-map", "[v]",
                "-frames:v", str(frames), "-r", str(FPS), "-an", "-c:v", "libx264",
                "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", str(destino)],
               "Falha ao renderizar cartao animado")


def clip_foto(foto, tarja, frames, w, h, mov, destino):
    zp = zoompan(frames, w, h, mov)
    fc = (f"[0:v]scale={2*w}:{2*h}:force_original_aspect_ratio=increase:flags=lanczos,"
          f"crop={2*w}:{2*h},{zp},setsar=1[bg];"
          f"[1:v]format=rgba,fade=t=in:st=0.1:d=0.5:alpha=1[ov];"
          f"[bg][ov]overlay=0:0:format=auto,format=yuv420p[v]")
    ff_ou_erro(["-i", str(Path(foto).resolve()), "-loop", "1", "-framerate", str(FPS),
                "-i", str(Path(tarja).resolve()), "-filter_complex", fc, "-map", "[v]",
                "-frames:v", str(frames), "-r", str(FPS), "-an", "-c:v", "libx264",
                "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", str(destino)],
               "Falha ao renderizar foto animada")


def montar(clips, limites, narracao, musica, volume, destino, nomes):
    n = len(clips)
    total = limites[-1] / FPS
    partes, anterior = [], "[0:v]"
    for k in range(1, n):
        saida = f"[x{k}]"
        partes.append(f"{anterior}[{k}:v]xfade=transition={nomes[(k - 1) % len(nomes)]}"
                      f":duration={TRANS}:offset={limites[k] / FPS:.4f}{saida}")
        anterior = saida
    fim = max(0.0, total - 0.6)
    partes.append(f"{anterior}fade=t=in:st=0:d=0.5,fade=t=out:st={fim:.2f}:d=0.6,format=yuv420p[v]")
    entradas = []
    for c in clips:
        entradas += ["-i", str(c.resolve())]
    entradas += ["-i", str(Path(narracao).resolve())]
    if musica:
        entradas += ["-stream_loop", "-1", "-i", str(Path(musica).resolve())]
        partes.append(f"[{n}:a]afade=t=in:st=0:d=0.5,afade=t=out:st={fim:.2f}:d=0.6[na]")
        partes.append(f"[{n+1}:a]volume={volume},afade=t=in:st=0:d=1.5,afade=t=out:st={fim:.2f}:d=0.6[ma]")
        partes.append("[na][ma]amix=inputs=2:duration=first:dropout_transition=0,volume=2,alimiter=limit=0.95[a]")
    else:
        partes.append(f"[{n}:a]afade=t=in:st=0:d=0.5,afade=t=out:st={fim:.2f}:d=0.6[a]")
    parcial = destino.with_name(destino.stem + ".parcial.mp4")
    r = ff([*entradas, "-filter_complex", ";".join(partes), "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.3f}", "-movflags", "+faststart", str(parcial)])
    if r.returncode != 0:
        raise bn.BroadcastError("Falha na montagem com transicoes: " + (r.stderr or "")[-900:])
    parcial.replace(destino)


def render_format_fx(script, durations, narration, project_dir, fmt, channel, category):
    w, h = bn.WIDTHS[fmt]
    saida = project_dir / "saida"
    saida.mkdir(parents=True, exist_ok=True)
    destino = saida / f"{bn.slug(script['titulo'])}_{fmt}_fx.mp4"
    trab = project_dir / "broadcast_fx" / fmt
    trab.mkdir(parents=True, exist_ok=True)
    nome_canal = str(channel.get("nome", "Canal"))
    fontes = script.get("fontes", [])
    cenas = script["cenas"]
    total = len(cenas)

    limites, acc = [0], 0.0
    for d in durations:
        acc += d
        limites.append(round(acc * FPS))
    tf = round(TRANS * FPS)

    clips = []
    for idx, cena in enumerate(cenas, 1):
        frames = limites[idx] - limites[idx - 1] + (tf if idx < total else 0)
        frames = max(frames, 4)
        clip = trab / f"clip_{idx:03d}.mp4"
        midia = bn.find_scene_media(project_dir, idx)
        if midia:
            tarja = trab / f"tarja_{idx:03d}.png"
            bn.create_media_overlay(cena, idx, total, nome_canal, category, fmt, tarja)
            info = f"   [{fmt}] cena {idx}/{total}: midia {midia.name}"
            print(info, flush=True)
            if midia.suffix.lower() in cv.EXT_VIDEO:
                bn.render_media_clip(midia, tarja, frames / FPS, w, h, clip)
            else:
                clip_foto(midia, tarja, frames, w, h, MOV_FOTO[idx % len(MOV_FOTO)], clip)
        else:
            print(f"   [{fmt}] cena {idx}/{total}: cartao animado", flush=True)
            cheio = trab / f"cena_{idx:03d}.png"
            fundo = trab / f"fundo_{idx:03d}.png"
            bn.create_scene_card(cena, idx, total, nome_canal, category, fontes, fmt, cheio)
            criar_fundo(cena, idx, total, nome_canal, category, fontes, fmt, fundo)
            clip_cartao(fundo, cheio, frames, w, h, MOV_CARTAO[idx % len(MOV_CARTAO)], clip)
        clips.append(clip)

    try:
        musica = cv.escolher_musica(channel, project_dir)
    except Exception:
        musica = ""
    volume = float(channel.get("volume_musica", 0.12))
    print(f"   [{fmt}] unindo cenas com transicoes...", flush=True)
    try:
        montar(clips, limites, narration, musica, volume, destino, TRANSICOES)
    except bn.BroadcastError:
        print("   transicoes variadas falharam; tentando apenas 'fade'...", flush=True)
        montar(clips, limites, narration, musica, volume, destino, ["fade"])
    return destino


bn.render_format = render_format_fx

if __name__ == "__main__":
    raise SystemExit(bn.main())