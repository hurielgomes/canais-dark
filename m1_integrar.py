"""
m1_integrar.py - copia do pacote M1 SOMENTE o que ainda nao existe no projeto. Nunca sobrescreve.

  python m1_integrar.py --origem C:\\caminho\\M1 --projeto C:\\caminho\\Fabrica            (simulacao)
  python m1_integrar.py --origem ... --projeto ... --aplicar                                (copia os novos)
  python m1_integrar.py --projeto ... --verificar                                           (testa imports e fontes)
  python m1_integrar.py --projeto ... --desfazer                                            (remove o que foi copiado)

--origem = pasta do M1 que corresponde a RAIZ da Fabrica (a que contem 'estudio/').
"""
import argparse
import difflib
import hashlib
import importlib
import sys
from pathlib import Path

IGNORAR_DIRS = {"__pycache__", ".git", ".venv", "saida", "node_modules"}
IGNORAR_EXT = {".pyc", ".mp4", ".wav", ".mp3"}
PROTEGIDOS = {"app.py", "criar_animado.py", "criar_video.py", "categorias.json", "motores/catalogo.json",
              "estudio/nucleo.py", "estudio/roteiro.py", "estudio/estilos/__init__.py"}
MODULOS = ["estudio.nucleo", "estudio.comum.tween", "estudio.comum.hud", "estudio.comum.legendas",
           "estudio.cenas2d.pintura", "estudio.cenas2d.rig", "estudio.cenas2d.camadas", "estudio.cenas2d.cenas",
           "estudio.cenas2d.cena_generica", "estudio.cenas2d.recursos.svgpath", "estudio.cenas2d.recursos.validar",
           "estudio.cenas2d.recursos.svg", "estudio.cenas2d.recursos.biblioteca", "estudio.estilos.cenas2d"]
FONTES = ["Inter-Black.otf", "Inter-ExtraBold.otf", "Inter-SemiBold.otf", "Inter-Medium.otf", "DejaVuSansMono-Bold.ttf"]
MANIFESTO = "m1_copiados.txt"


def sha(p):
    return hashlib.sha1(p.read_bytes()).hexdigest()


def varrer(origem):
    for p in sorted(origem.rglob("*")):
        rel = p.relative_to(origem)
        if p.is_file() and not (set(rel.parts[:-1]) & IGNORAR_DIRS) and p.suffix.lower() not in IGNORAR_EXT:
            yield p, rel


def texto(p):
    try:
        return p.read_text(encoding="utf-8").splitlines(keepends=True)
    except (UnicodeDecodeError, OSError):
        return None


def comparar(o, proj, aplicar):
    novos, iguais, conflitos = [], [], []
    pasta_dif = proj / "m1_conflitos"
    for p, rel in varrer(o):
        d = proj / rel
        if not d.exists():
            novos.append(rel)
            if aplicar:
                d.parent.mkdir(parents=True, exist_ok=True)
                d.write_bytes(p.read_bytes())
        elif sha(p) == sha(d) or (rel.name == "__init__.py" and not (texto(p) or [""])[0].strip() and len(texto(p) or []) == 0):
            iguais.append(rel)
        else:
            conflitos.append(rel)
            a, b = texto(d), texto(p)
            if aplicar and a is not None and b is not None:
                pasta_dif.mkdir(exist_ok=True)
                dif = "".join(difflib.unified_diff(a, b, f"PROJETO/{rel.as_posix()}", f"M1/{rel.as_posix()}"))
                (pasta_dif / (rel.as_posix().replace("/", "__") + ".diff")).write_text(dif, encoding="utf-8")
    if aplicar and novos:
        (proj / MANIFESTO).write_text("\n".join(r.as_posix() for r in novos), encoding="utf-8")
    return novos, iguais, conflitos


def verificar(proj):
    sys.path.insert(0, str(proj / "estudio"))
    print("\nImports:")
    for m in MODULOS:
        try:
            importlib.import_module(m)
            print(f"  ok     {m}")
        except Exception as e:  # noqa
            print(f"  FALHA  {m}: {type(e).__name__}: {e}")
    pasta = proj / "estudio" / "estudio" / "cenas2d" / "assets" / "fontes"
    print("\nFontes (estudio/cenas2d/assets/fontes):")
    for f in FONTES:
        print(f"  {'ok    ' if (pasta / f).exists() else 'FALTA '} {f}")


def desfazer(proj):
    arq = proj / MANIFESTO
    if not arq.exists():
        return print("nada a desfazer")
    for linha in arq.read_text(encoding="utf-8").splitlines():
        (proj / linha).unlink(missing_ok=True)
    arq.unlink()
    print("arquivos copiados removidos")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--origem")
    ap.add_argument("--projeto", required=True)
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--verificar", action="store_true")
    ap.add_argument("--desfazer", action="store_true")
    a = ap.parse_args()
    proj = Path(a.projeto).resolve()
    if a.desfazer:
        return desfazer(proj)
    if a.origem:
        o = Path(a.origem).resolve()
        if not (o / "estudio").is_dir():
            sys.exit("a origem precisa conter a pasta 'estudio/'")
        novos, iguais, conflitos = comparar(o, proj, a.aplicar)
        linhas = [f"# Relatorio M1 ({'APLICADO' if a.aplicar else 'SIMULACAO'})", "",
                  f"- novos: {len(novos)}", f"- identicos: {len(iguais)}", f"- CONFLITOS: {len(conflitos)}", "", "## Novos"]
        linhas += [f"- {r.as_posix()}" for r in novos]
        linhas += ["", "## Conflitos (NAO copiados)"]
        linhas += [f"- {r.as_posix()}" + ("  [PROTEGIDO]" if r.as_posix() in PROTEGIDOS else "") for r in conflitos]
        rel = "\n".join(linhas)
        print(rel)
        (proj / "m1_relatorio.md").write_text(rel, encoding="utf-8")
    if a.verificar or (a.aplicar and a.origem):
        verificar(proj)


if __name__ == "__main__":
    main()