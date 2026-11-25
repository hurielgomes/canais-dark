"""Executa motores de roteiro usando o MyHub-Bridge quando configurado.

Este runner e chamado pelos adapters da interface. Ele preserva os motores
originais e injeta apenas a funcao de geracao de roteiro antes de chamar main().

Motores suportados:
  - broadcast_news
  - broadcast_motion (reusa broadcast_news)
  - telejornal (criar_animado.py --estilo telejornal)

Selecao do provedor:
  provedor_geracao_roteiro / provedor_texto = myhub | gemini | auto
  Em auto, usa MyHub se myhub_bridge_dir apontar para uma instalacao valida;
  caso contrario, mantem o Gemini legado.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
MOTOR_DIR = Path(__file__).resolve().parent


def _bridge_root(cfg: dict, root: Path = ROOT) -> Path:
    raw = (
        os.environ.get("MYHUB_BRIDGE_DIR")
        or cfg.get("myhub_bridge_dir")
        or "../myhub-bridge"
    )
    path = Path(os.path.expandvars(str(raw))).expanduser()
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def _resolve_provider(cfg: dict, root: Path = ROOT) -> str:
    """Resolve o provedor sem depender de bridge_disponivel (ausente em algumas versoes)."""
    provider = str(
        cfg.get("provedor_geracao_roteiro")
        or cfg.get("provedor_texto")
        or "auto"
    ).strip().lower()

    if provider not in {"myhub", "gemini", "auto"}:
        raise ValueError(
            "Provedor de roteiro invalido: "
            f"{provider!r}. Use 'myhub', 'gemini' ou 'auto'."
        )

    if provider == "auto":
        bridge_root = _bridge_root(cfg, root)
        provider = (
            "myhub"
            if (bridge_root / "main.py").is_file()
            and (bridge_root / "config.json").is_file()
            else "gemini"
        )
    return provider


def _request_myhub_json(
    cfg: dict,
    prompt: str,
    log: Callable[[str], None],
    parser: Callable[[str], dict],
    chat_scope: str,
) -> dict:
    from myhub_llm import criar_llm_myhub

    llm = criar_llm_myhub(
        cfg,
        ROOT,
        log,
        purpose="roteiro",
        expected_outputs=["json"],
        chat_scope=chat_scope,
    )
    raw = llm(prompt, True)
    result = parser(raw)
    if not isinstance(result, dict):
        raise ValueError("O MyHub retornou JSON, mas a raiz nao e um objeto.")
    if not isinstance(result.get("cenas"), list) or not result["cenas"]:
        raise ValueError("O JSON retornado pelo MyHub nao contem uma lista 'cenas' valida.")
    return result


def _patch_broadcast(engine: str) -> int:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    if str(MOTOR_DIR) not in sys.path:
        sys.path.insert(0, str(MOTOR_DIR))

    import broadcast_news as bn

    # Importar o motor Motion aplica os ajustes visuais/prompt dele sobre bn.
    # A geracao do roteiro continua sendo compartilhada com Broadcast News.
    if engine == "broadcast_motion":
        import broadcast_motion  # noqa: F401

    legacy_generate = bn.generate_script_without_search

    def generate_script(channel, topic, duration, category, config):
        provider = _resolve_provider(config, ROOT)
        if provider == "gemini":
            bn.info("   Provedor do roteiro: Gemini (configuracao selecionada).")
            return legacy_generate(channel, topic, duration, category, config)

        bn.info("   Provedor do roteiro: MyHub-Bridge.")
        prompt = bn.make_research_prompt(channel, topic, duration, category)
        try:
            script = _request_myhub_json(
                config,
                prompt,
                bn.info,
                bn.cv._parse_json,
                f"{engine}_{category}",
            )
            return script, []
        except Exception as exc:
            raise bn.BroadcastError(
                f"Falha na geracao do roteiro pelo MyHub-Bridge ({engine}): {exc}"
            ) from exc

    bn.generate_script_without_search = generate_script
    return int(bn.main() or 0)


def _patch_telejornal() -> int:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    import criar_animado as ca

    legacy_generate = ca.gerar_roteiro_gemini

    def generate_script(channel, topic, duration, style, previous, config, category="curiosidades"):
        provider = _resolve_provider(config, ROOT)
        if provider == "gemini":
            ca.cv.info("   Provedor do roteiro: Gemini (configuracao selecionada).")
            return legacy_generate(
                channel, topic, duration, style, previous, config, category
            )

        ca.cv.info("   Provedor do roteiro: MyHub-Bridge.")
        prompt = ca.montar_prompt(
            channel, topic, duration, style, previous, category
        )
        try:
            return _request_myhub_json(
                config,
                prompt,
                ca.cv.info,
                ca.cv._parse_json,
                f"animado_telejornal_{category}",
            )
        except Exception as exc:
            ca.cv.erro(f"Falha na geracao do roteiro pelo MyHub-Bridge: {exc}")
            raise  # cv.erro normalmente encerra a execucao; mantem seguranca se nao encerrar.

    ca.gerar_roteiro_gemini = generate_script
    return int(ca.main() or 0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--engine",
        required=True,
        choices=("broadcast_news", "broadcast_motion", "telejornal"),
    )
    args, engine_args = parser.parse_known_args(argv)
    if not engine_args:
        print("ERRO: faltam os argumentos do motor. Consulte o comando de execucao.")
        return 2

    # O parser especifico do motor recebe todos os argumentos originais.
    sys.argv = [sys.argv[0], *engine_args]
    if args.engine in {"broadcast_news", "broadcast_motion"}:
        return _patch_broadcast(args.engine)
    return _patch_telejornal()


if __name__ == "__main__":
    raise SystemExit(main())
