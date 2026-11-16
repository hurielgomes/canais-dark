"""Gerencia a biblioteca M1.
Uso:
  py m1_recursos.py listar
  py m1_recursos.py aprovar <ref> [<ref> ...] | --todos
  py m1_recursos.py rejeitar <ref> "motivo"
  py m1_recursos.py galeria [caminho.html]
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "estudio"))
from estudio.cenas2d.recursos.biblioteca import Biblioteca  # noqa: E402


def main(args):
    if not args or args[0] not in ("listar", "aprovar", "rejeitar", "galeria"):
        print(__doc__)
        return 1
    bib = Biblioteca(RAIZ / "biblioteca_m1")
    cmd, resto = args[0], args[1:]
    existentes = bib.idx["recursos"]

    if cmd == "listar":
        for e in bib.listar():
            print(f"{e['id']:<14}{e['status']:<10}{e['tipo']:<12}v{e['versao']}  {e.get('nome', '')}")
        return 0

    if cmd == "aprovar":
        refs = bib.pendentes() if resto == ["--todos"] else resto
        if not refs:
            print("Nada a aprovar.")
            return 1
        for r in refs:
            if r not in existentes:
                print(f"ERRO: '{r}' nao existe na biblioteca.")
                return 1
        for r in refs:
            bib.aprovar(r)
            print(f"aprovado: {r}")
        return 0

    if cmd == "rejeitar":
        if not resto or resto[0] not in existentes:
            print("Informe um recurso existente: py m1_recursos.py rejeitar <ref> \"motivo\"")
            return 1
        bib.rejeitar(resto[0], " ".join(resto[1:]))
        print(f"rejeitado: {resto[0]}")
        return 0

    destino = Path(resto[0]) if resto else RAIZ / "biblioteca_m1" / "galeria.html"
    destino.parent.mkdir(parents=True, exist_ok=True)
    bib.galeria(destino)
    print(f"galeria: {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
