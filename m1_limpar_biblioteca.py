"""Remove da biblioteca M1 os recursos de RESERVA (origem 'procedural') criados automaticamente.

Uso:  python m1_limpar_biblioteca.py            (mostra o que seria removido)
      python m1_limpar_biblioteca.py --aplicar  (remove)
Recursos curados e desenhados por IA nao sao tocados.
"""
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent / "biblioteca_m1"


def main():
    aplicar = "--aplicar" in sys.argv
    ip = RAIZ / "index.json"
    d = json.loads(ip.read_text(encoding="utf-8"))
    alvo = [k for k, e in d["recursos"].items() if e.get("origem") == "procedural"]
    print(f"{len(alvo)} recurso(s) procedural(is): {', '.join(alvo) or '-'}")
    if not aplicar:
        print("(simulacao - use --aplicar para remover)")
        return
    for k in alvo:
        for f in RAIZ.glob(f"recursos/*/{k}.v*.*"):
            f.unlink()
        d["recursos"].pop(k, None)
    ip.write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding="utf-8")
    print("removidos.")


if __name__ == "__main__":
    main()
