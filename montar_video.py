"""
montar_video.py - Modulo 1 do pipeline: monta videos 16:9 e 9:16
a partir de imagens + narracao, com zoom lento, fade e saida em 2 formatos.

Uso (no terminal, dentro da pasta do projeto):
    python montar_video.py projetos\\teste

A pasta do projeto precisa ter:
    cenas.json   -> lista de cenas (veja o exemplo abaixo)
    imagens      -> os arquivos citados no cenas.json
    narracao.mp3 -> opcional (.wav tambem serve)

Exemplo de cenas.json:
{
  "titulo": "video-teste",
  "narracao": "narracao.mp3",
  "cenas": [
    {"imagem": "01.png"},
    {"imagem": "02.png", "duracao": 6},
    {"imagem": "03.png"}
  ]
}
Cenas sem "duracao" dividem igualmente o tempo restante da narracao
(sem narracao, cada uma dura 5 segundos).
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

FPS = 30
ZOOM_MAX = 0.15          # 15% de zoom ao longo de cada cena
FADE = 0.6               # segundos de fade no inicio e no fim do video
DURACAO_PADRAO = 5.0     # segundos, quando nao ha narracao
FORMATOS = {
    "16x9": (1920, 1080),   # YouTube horizontal
    "9x16": (1080, 1920),   # Shorts, Reels, TikTok
}


def erro(msg):
    print(f"\nERRO: {msg}\n")
    sys.exit(1)


def checar_ffmpeg():
    for prog in ("ffmpeg", "ffprobe"):
        if shutil.which(prog) is None:
            erro(f"'{prog}' nao foi encontrado. Instale o FFmpeg e abra um novo terminal.")


def rodar(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-1500:])
        erro("o FFmpeg falhou (veja a mensagem acima).")
    return r.stdout


def duracao_arquivo(caminho):
    saida = rodar([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(caminho),
    ])
    return float(saida.strip())


def calcular_duracoes(cenas, audio):
    total_audio = duracao_arquivo(audio) if audio else None
    fixas = sum(c.get("duracao", 0) for c in cenas)
    livres = [c for c in cenas if "duracao" not in c]
    if total_audio is None:
        padrao = DURACAO_PADRAO
    else:
        restante = total_audio - fixas
        if livres and restante <= 0:
            erro("as duracoes fixas ja passam do tamanho da narracao.")
        padrao = restante / len(livres) if livres else 0
    return [float(c.get("duracao", padrao)) for c in cenas]


def renderizar_cena(img, dur, indice, w, h, destino):
    frames = max(1, round(dur * FPS))
    if indice % 2 == 0:   # alterna zoom in / zoom out para variar
        z = f"1+{ZOOM_MAX}*on/{frames}"
    else:
        z = f"1+{ZOOM_MAX}-{ZOOM_MAX}*on/{frames}"
    vf = (
        f"scale={w*2}:{h*2}:force_original_aspect_ratio=increase,"
        f"crop={w*2}:{h*2},"
        f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        f":d={frames}:s={w}x{h}:fps={FPS},format=yuv420p"
    )
    rodar([
        "ffmpeg", "-y", "-i", str(img), "-vf", vf,
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-r", str(FPS), str(destino),
    ])


def montar_formato(nome, w, h, projeto, titulo, cenas, duracoes, audio, saida):
    total = sum(duracoes)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        lista = []
        for i, (cena, dur) in enumerate(zip(cenas, duracoes)):
            img = projeto / cena["imagem"]
            if not img.exists():
                erro(f"imagem nao encontrada: {img}")
            clipe = tmp / f"clipe_{i:03d}.mp4"
            print(f"  [{nome}] cena {i+1}/{len(cenas)} ({dur:.1f}s)")
            renderizar_cena(img, dur, i, w, h, clipe)
            lista.append(f"file '{clipe.name}'")
        (tmp / "lista.txt").write_text("\n".join(lista), encoding="utf-8")

        destino = saida / f"{titulo}_{nome}.mp4"
        vf = f"fade=t=in:st=0:d={FADE},fade=t=out:st={max(0, total-FADE):.2f}:d={FADE}"
        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "lista.txt"]
        if audio:
            cmd += ["-i", str(audio.resolve())]
        cmd += ["-vf", vf]
        if audio:
            af = f"afade=t=in:st=0:d={FADE},afade=t=out:st={max(0, total-FADE):.2f}:d={FADE}"
            cmd += ["-af", af, "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.2f}"]
        cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "20",
                "-movflags", "+faststart", str(destino.resolve())]
        rodar(cmd, cwd=tmp)
        print(f"  pronto: {destino}")


def main():
    if len(sys.argv) != 2:
        erro("uso: python montar_video.py pasta_do_projeto")
    checar_ffmpeg()
    projeto = Path(sys.argv[1])
    arq = projeto / "cenas.json"
    if not arq.exists():
        erro(f"nao encontrei {arq}")
    dados = json.loads(arq.read_text(encoding="utf-8"))
    cenas = dados["cenas"]
    titulo = dados.get("titulo", "video")
    audio = None
    if dados.get("narracao"):
        audio = projeto / dados["narracao"]
        if not audio.exists():
            erro(f"narracao nao encontrada: {audio}")
    duracoes = calcular_duracoes(cenas, audio)
    saida = projeto / "saida"
    saida.mkdir(exist_ok=True)
    print(f"Montando '{titulo}': {len(cenas)} cenas, {sum(duracoes):.1f}s")
    for nome, (w, h) in FORMATOS.items():
        montar_formato(nome, w, h, projeto, titulo, cenas, duracoes, audio, saida)
    print("\nConcluido. Arquivos na pasta 'saida'.")


if __name__ == "__main__":
    main()
