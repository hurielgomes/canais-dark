"""
estudio.py - cria um video a partir de um roteiro JSON.

Uso:
    python estudio.py exemplos/telejornal_dolar.json saida.mp4
    python estudio.py exemplos/telejornal_dolar.json saida_vertical.mp4 --formato 9x16
    python estudio.py exemplos/telejornal_dolar.json teste.mp4 --teste 5      (so os 5 primeiros segundos)
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from estudio.roteiro import carregar, renderizar_roteiro  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("roteiro")
    ap.add_argument("saida")
    ap.add_argument("--formato", default="16x9", choices=["16x9", "9x16"])
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--teste", type=float, help="renderiza so os primeiros N segundos")
    ap.add_argument("--rapido", action="store_true", help="menos suavizacao (mais rapido, bordas menos lisas)")
    a = ap.parse_args()
    total = renderizar_roteiro(carregar(a.roteiro), a.saida, a.formato, a.fps, a.teste, S=1 if a.rapido else 2)
    print(f"pronto: {a.saida} ({total:.1f}s)")


if __name__ == "__main__":
    main()
