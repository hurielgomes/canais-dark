import json, pathlib

erros = 0
for p in pathlib.Path(".").rglob("*.json"):
    try:
        json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        erros += 1
        print(p, "=>", e)
        linhas = p.read_text(encoding="utf-8").splitlines()
        for i in range(15, min(len(linhas), 22)):
            print(f"  {i+1:>3}: {linhas[i]}")

print("OK, nenhum erro." if not erros else f"{erros} arquivo(s) com erro.")
