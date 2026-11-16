"""
m1_recursos.py - gerencia a biblioteca de recursos do M1 (nao altera nada fora da pasta da biblioteca).

    python m1_recursos.py registrar PASTA_OU_ARQUIVO [--biblioteca DIR] [--aprovacao manual]
    python m1_recursos.py listar [--status pendente]
    python m1_recursos.py aprovar ID  |  rejeitar ID "motivo"
    python m1_recursos.py galeria saida.html [ID ...]       (previas de todos ou dos IDs indicados)
    python m1_recursos.py previa ID saida.png
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from estudio.cenas2d.recursos.biblioteca import Biblioteca  # noqa: E402
from estudio.cenas2d.recursos.validar import RecursoInvalido  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["registrar", "listar", "aprovar", "rejeitar", "galeria", "previa"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--biblioteca", default="biblioteca_m1")
    ap.add_argument("--aprovacao", default="auto", choices=["auto", "manual"])
    ap.add_argument("--status")
    a = ap.parse_args()
    bib = Biblioteca(a.biblioteca, aprovacao=a.aprovacao)
    if a.cmd == "registrar":
        for alvo in a.args:
            p = Path(alvo)
            try:
                res = bib.registrar_pasta(p) if p.is_dir() else [bib.registrar(p)]
            except (RecursoInvalido, ValueError, OSError) as e:
                print(f"REJEITADO {alvo}: {e}")
                continue
            for r in res:
                print(f"{r.id}: {r.estado} ({r.status})" + (f"  avisos: {r.avisos}" if r.avisos else ""))
        for pr in bib.problemas:
            print("PROBLEMA:", pr)
    elif a.cmd == "listar":
        for r in bib.listar(a.status):
            print(f"{r['id']:<16} v{r['versao']} {r['tipo']:<10} {r['status']:<10} anims: {', '.join(r['animacoes']) or '-'}")
    elif a.cmd == "aprovar":
        bib.aprovar(a.args[0]); print("aprovado:", a.args[0])
    elif a.cmd == "rejeitar":
        bib.rejeitar(a.args[0], a.args[1] if len(a.args) > 1 else ""); print("rejeitado:", a.args[0])
    elif a.cmd == "galeria":
        ids = a.args[1:] or [r["id"] for r in bib.listar()]
        bib.galeria(a.args[0], usados={i: {"estado": "reutilizado", "status": bib.idx["recursos"][i]["status"]} for i in ids})
        print("galeria:", a.args[0])
    elif a.cmd == "previa":
        bib.previa(a.args[0]).save(a.args[1]); print("previa:", a.args[1])


if __name__ == "__main__":
    main()
