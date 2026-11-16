"""
cenas2d_proto.py - CLI standalone do prototipo M1 (Cenas 2D em Camadas). NAO altera nenhum arquivo do projeto.

Uso:
    python cenas2d_proto.py exemplos/cenas2d_alerta_noturno.json saida.mp4 --formato 9x16
    python cenas2d_proto.py exemplos/cenas2d_alerta_noturno.json saida.mp4 --formato 16x9 --fps 30
    python cenas2d_proto.py exemplos/cenas2d_alerta_noturno.json q.png --formato 9x16 --quadro 2.5      (so um quadro)
    python cenas2d_proto.py ... --teste 3          (so os 3 primeiros segundos)   |   --metricas m.json
    python cenas2d_proto.py ... --cena 2           (so a cena 2; depois junte com ffmpeg -f concat)
"""
import argparse
import json
import resource
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from estudio.nucleo import Tela, renderizar  # noqa: E402
from estudio.estilos.cenas2d import Estilo, normalizar  # noqa: E402
from estudio.cenas2d.recursos.biblioteca import Biblioteca  # noqa: E402

FORMATOS = {"16x9": (1920, 1080), "9x16": (1080, 1920)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("roteiro")
    ap.add_argument("saida")
    ap.add_argument("--formato", default="9x16", choices=list(FORMATOS))
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--teste", type=float)
    ap.add_argument("--quadro", type=float, help="salva so o quadro do instante T (s) como PNG")
    ap.add_argument("--cena", type=int, help="renderiza so a cena N (1..n) - permite render em segmentos retomaveis")
    ap.add_argument("--metricas")
    ap.add_argument("--biblioteca", default="biblioteca_m1", help="pasta da biblioteca de recursos (criada se nao existir)")
    ap.add_argument("--registrar", action="append", default=[], help="pasta de recursos (.json/.svg) a registrar antes de renderizar (repetivel)")
    ap.add_argument("--aprovacao", default="auto", choices=["auto", "manual"], help="auto: recursos novos ja entram aprovados (producao em massa)")
    ap.add_argument("--exigir-aprovados", action="store_true", help="falha se um recurso pendente/rejeitado for usado")
    ap.add_argument("--galeria", help="gera a pagina HTML de revisao dos recursos usados (novo/reutilizado/status)")
    a = ap.parse_args()
    rot = json.loads(Path(a.roteiro).read_text(encoding="utf-8"))
    w, h = FORMATOS[a.formato]
    bib = Biblioteca(a.biblioteca, aprovacao=a.aprovacao, bloquear_pendentes=a.exigir_aprovados)
    for pasta in a.registrar:
        for r in bib.registrar_pasta(pasta):
            print(f"recurso {r.id}: {r.estado} ({r.status})" + (f"  avisos: {r.avisos}" if r.avisos else ""))
    estilo = Estilo(w, h, rot.get("preset", "alerta_noturno"), biblioteca=bib)
    cenas = []
    for c in rot["cenas"]:
        c2, avisos = normalizar(c)
        for av in avisos:
            print("aviso:", av)
        cenas.append(c2)
    if a.cena:
        cenas = [cenas[a.cena - 1]]
    inicios, acum = [], 0.0
    for c in cenas:
        inicios.append(acum)
        acum += float(c["duracao"])
    total = acum if a.teste is None else min(acum, a.teste)
    canal = rot.get("canal", "")

    def cena_em(t):
        i = max(k for k, ini in enumerate(inicios) if ini <= t + 1e-9)
        return i, t - inicios[i]

    if a.quadro is not None:
        t0 = time.time()
        tela = Tela(w, h, 1)
        i, tl = cena_em(a.quadro)
        estilo.quadro(tela, tl, cenas[i], canal)
        tela.finalizar().save(a.saida)
        print(f"quadro {a.quadro}s (cena {i + 1}) -> {a.saida}  [{time.time() - t0:.2f}s incl. preparo]")
        if a.galeria:
            bib.galeria(a.galeria, usados=bib.usos)
        return

    tempos, por_cena = [], {}
    t_ini = time.time()

    def fn(tela, t):
        i, tl = cena_em(t)
        s = time.time()
        estilo.quadro(tela, tl, cenas[i], canal)
        d = time.time() - s
        tempos.append(d)
        por_cena.setdefault(i + 1, []).append(d)

    def cb(i, n):
        if i % 60 == 0:
            print(f"  quadro {i}/{n}  ({(time.time() - t_ini):.0f}s)", flush=True)

    renderizar(fn, a.saida, w, h, a.fps, total, S=1, fn_fundo=None, callback=cb)
    tot = time.time() - t_ini
    m = {"formato": a.formato, "resolucao": f"{w}x{h}", "fps": a.fps, "duracao_s": round(total, 2),
         "quadros": len(tempos), "tempo_total_s": round(tot, 1),
         "tempo_medio_por_quadro_s": round(sum(tempos) / len(tempos), 3),
         "tempo_medio_incl_encode_s": round(tot / len(tempos), 3),
         "por_cena_s_por_quadro": {k: round(sum(v) / len(v), 3) for k, v in por_cena.items()},
         "pico_memoria_MB": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 0)}
    print(json.dumps(m, indent=1, ensure_ascii=False))
    _fecha(bib, a)
    if a.metricas:
        Path(a.metricas).write_text(json.dumps(m, indent=1, ensure_ascii=False), encoding="utf-8")


def _fecha(bib, a):
    uso = {r: dict(info, **{k: bib.idx["recursos"][r][k] for k in ("tipo", "versao", "nome")}) for r, info in bib.usos.items() if r in bib.idx["recursos"]}
    if uso or bib.problemas:
        out = Path(a.saida).with_suffix(".recursos.json")
        out.write_text(json.dumps({"recursos": uso, "avisos": sorted(set(bib.problemas))}, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"recursos usados: {len(uso)}  (novos: {sum(1 for u in uso.values() if u['estado'] != 'reutilizado')})  avisos: {len(set(bib.problemas))}  -> {out.name}")
    if a.galeria:
        bib.galeria(a.galeria, usados=bib.usos)
        print("galeria:", a.galeria)


if __name__ == "__main__":
    main()
