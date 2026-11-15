"""Monta o bloco editorial do prompt respeitando a precedencia."""
from .resolver import obter_perfil

PRECEDENCIA = ("regras obrigatórias", "canal", "perfil", "categoria", "tema", "formato", "motor")


def _lista(v):
    return v if isinstance(v, list) else ([v] if v else [])


def montar_bloco_editorial(canal, categoria, resolucao, formato=None, motor=None, tema=None):
    """Texto vazio no modo legado (prompt antigo fica intacto)."""
    if not resolucao or resolucao.get("modo") != "nucleo" or not resolucao.get("perfil"):
        return ""
    canal = canal or {}
    p = obter_perfil(resolucao["perfil"])
    L = ["=== NÚCLEO EDITORIAL ===",
         "PRECEDÊNCIA (em conflito, vale o item mais alto): " + " > ".join(PRECEDENCIA) + "."]

    L.append("\n[1] REGRAS OBRIGATÓRIAS")
    L += [f"- {r}" for r in _lista(canal.get("regras"))] or ["- (nenhuma regra extra do canal)"]
    L.append("- Não invente fatos, números ou citações.")

    L.append("\n[2] IDENTIDADE DO CANAL (não pode ser alterada pelo perfil)")
    for campo in ("nome", "nicho", "publico", "tom"):
        if canal.get(campo):
            L.append(f"- {campo}: {canal[campo]}")

    L.append(f"\n[3] PERFIL NARRATIVO: {p['nome']} ({p['id']})")
    L += [f"- Tom do perfil (ajusta, não substitui o tom do canal): {p['tom']}",
          "- Estrutura: " + " → ".join(p["estrutura"]),
          f"- Aprofundamento: {p['aprofundamento']}",
          f"- Velocidade: {p['velocidade']}",
          f"- Exemplos/analogias: {p['exemplos_analogias']}",
          f"- Tensão/curiosidade: {p['tensao_curiosidade']}",
          "- Cuidados: " + "; ".join(p["cuidados"])]

    L.append("\n[ABERTURA]")
    L.append(f"- {p['abertura']}")
    L.append("- Não use fórmulas prontas como \"Você sabia\" ou \"Aposto que você não sabia\".")

    L.append("\n[ENCERRAMENTO E CTA]")
    L += [f"- {p['encerramento']}", f"- CTA: {p['cta']}"]

    if categoria:
        L.append(f"\n[4] CATEGORIA: {categoria} (complementa, não sobrescreve canal/perfil)")
    if tema:
        L.append(f"[5] TEMA: {tema}")
    if formato:
        L.append(f"[6] FORMATO: {formato}")
    if motor:
        L.append(f"[7] MOTOR: {motor} (limitações técnicas do motor continuam valendo)")
    L.append(f"\nJustificativa do perfil: {resolucao.get('justificativa', '')}")
    return "\n".join(L)
