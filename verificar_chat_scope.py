from pathlib import Path
import inspect
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "estudio"))

try:
    import diretor_m1
    assinatura = inspect.signature(diretor_m1.dirigir)
    print("Modulo carregado:", Path(diretor_m1.__file__).resolve())
    print("Assinatura:", assinatura)
    if "chat_scope" not in assinatura.parameters:
        print("ERRO: o diretor carregado nao aceita chat_scope.")
        raise SystemExit(1)
    print("OK: diretor_m1 aceita chat_scope e esta pronto para o MyHub Bridge.")
except Exception as exc:
    print("Falha ao verificar o diretor M1:", repr(exc))
    raise SystemExit(2)
