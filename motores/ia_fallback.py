"""Tenta varias IAs em sequencia ate uma responder."""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request


def provedores(config: dict) -> list[dict]:
    cf = config.get("cloudflare_account_id")
    lista = [
        ("Groq", "groq_api_key", "https://api.groq.com/openai/v1/chat/completions",
         config.get("modelo_groq", "llama-3.3-70b-versatile")),
        ("Cerebras", "cerebras_api_key", "https://api.cerebras.ai/v1/chat/completions",
         config.get("modelo_cerebras", "llama-3.3-70b")),
        ("Mistral", "mistral_api_key", "https://api.mistral.ai/v1/chat/completions",
         config.get("modelo_mistral", "mistral-small-latest")),
        ("OpenRouter", "openrouter_api_key", "https://openrouter.ai/api/v1/chat/completions",
         config.get("modelo_openrouter", "meta-llama/llama-3.3-70b-instruct:free")),
        ("Cloudflare", "cloudflare_api_token",
         f"https://api.cloudflare.com/client/v4/accounts/{cf}/ai/v1/chat/completions",
         config.get("modelo_cloudflare_texto", "@cf/meta/llama-3.3-70b-instruct-fp8-fast")),
    ]
    ordem = config.get("ordem_ia_texto")  # ex.: ["Groq", "Cerebras"]
    if ordem:
        lista.sort(key=lambda p: ordem.index(p[0]) if p[0] in ordem else 99)
    return [{"nome": n, "chave": config[k], "url": u, "modelo": m}
            for n, k, u, m in lista
            if config.get(k) and (n != "Cloudflare" or cf)]


def extrair_json(texto: str) -> dict:
    texto = re.sub(r"^```(?:json)?\s*|\s*```$", "", texto.strip(), flags=re.I | re.M)
    ini, fim = texto.find("{"), texto.rfind("}")
    return json.loads(texto[ini:fim + 1] if ini >= 0 else texto)


def chamar(p: dict, prompt: str) -> dict:
    corpo = json.dumps({
        "model": p["modelo"],
        "messages": [
            {"role": "system", "content": "Responda somente com JSON valido."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.35,
        "max_tokens": 8000,
    }).encode("utf-8")
    req = urllib.request.Request(p["url"], data=corpo, headers={
        "Authorization": f"Bearer {p['chave']}",
        "Content-Type": "application/json",
        "User-Agent": "ProjetoDark/1.0",
    })
    with urllib.request.urlopen(req, timeout=180) as r:
        dados = json.loads(r.read().decode("utf-8"))
    return extrair_json(dados["choices"][0]["message"]["content"])


def modelo_disponivel(p: dict) -> str | None:
    """Consulta /models e escolhe um modelo de texto disponivel."""
    url = p["url"].rsplit("/chat/completions", 1)[0] + "/models"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {p['chave']}", "User-Agent": "ProjetoDark/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        ids = [m.get("id", "") for m in json.loads(r.read().decode("utf-8")).get("data", [])]
    if p["nome"] == "OpenRouter":
        ids = [i for i in ids if i.endswith(":free")]
    ruins = ("whisper", "tts", "guard", "embed", "vision", "audio", "moderation")
    ids = [i for i in ids if not any(x in i.lower() for x in ruins)]
    preferidos = ("70b", "large", "120b", "llama", "qwen", "gpt-oss", "mistral")
    for pref in preferidos:
        for i in ids:
            if pref in i.lower():
                return i
    return ids[0] if ids else None


def gerar_roteiro(prompt: str, config: dict, info=print) -> dict:
    import time
    erros = []
    for p in provedores(config):
        for tentativa in range(3):
            info(f"   tentando {p['nome']} ({p['modelo']})...")
            try:
                return chamar(p, prompt)
            except urllib.error.HTTPError as e:
                msg = e.read().decode("utf-8", "replace")[:200]
                if e.code in (400, 404) and tentativa == 0:
                    try:
                        novo = modelo_disponivel(p)
                    except Exception:
                        novo = None
                    if novo and novo != p["modelo"]:
                        info(f"   {p['nome']}: modelo indisponivel, trocando para {novo}")
                        p["modelo"] = novo
                        continue
                if e.code == 429 and tentativa < 2:
                    info(f"   {p['nome']}: limite por minuto, aguardando 20s...")
                    time.sleep(20)
                    continue
                erros.append(f"{p['nome']}: HTTP {e.code} {msg}")
            except Exception as e:
                erros.append(f"{p['nome']}: {str(e)[:200]}")
            info(f"   {erros[-1]}")
            break
    raise RuntimeError("Nenhuma IA respondeu. " + " | ".join(erros) if erros
                       else "Nenhuma chave de IA alternativa configurada.")