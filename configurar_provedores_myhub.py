"""Ativa MyHub Bridge nas etapas de texto e direção de arte do M1.

Faz backup do config.json e altera somente as chaves de provedor, preservando
as chaves de API e todas as demais configurações existentes.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config.json"
SETTINGS = {
    "provedor_planejamento_narrativa": "myhub",
    "provedor_geracao_roteiro": "myhub",
    "provedor_refino_roteiro": "myhub",
    "m1_diretor_padrao": "myhub",
    "myhub_timeout_seconds": 900,
    "m1_myhub_timeout_seconds": 900,
}


def main() -> int:
    if not CONFIG.is_file():
        print("ERRO: config.json não encontrado. Execute este arquivo na pasta raiz da Fábrica.")
        return 1
    try:
        cfg = json.loads(CONFIG.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        print(f"ERRO: config.json está inválido na linha {exc.lineno}, coluna {exc.colno}.")
        print("Nenhum arquivo foi alterado. Corrija o JSON e execute novamente.")
        return 1
    if not isinstance(cfg, dict):
        print("ERRO: a raiz do config.json precisa ser um objeto JSON.")
        return 1

    backup = CONFIG.with_name(f"config.json.backup_myhub_{datetime.now():%Y%m%d_%H%M%S}")
    backup.write_text(CONFIG.read_text(encoding="utf-8-sig"), encoding="utf-8")
    cfg.update(SETTINGS)
    temp = CONFIG.with_suffix(".json.tmp")
    temp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # Confere o arquivo temporário antes de substituir o original.
    json.loads(temp.read_text(encoding="utf-8"))
    temp.replace(CONFIG)
    print("MyHub Bridge ativado para:")
    print(" - planejamento de narrativa")
    print(" - criação do roteiro")
    print(" - checagem, otimização e refino")
    print(" - direção de arte e recursos SVG/JSON do M1")
    print(f"Backup criado: {backup.name}")
    print("Modelo do MyHub: será usado o modelo já selecionado/salvo na conversa do Bridge.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
