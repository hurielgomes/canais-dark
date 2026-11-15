import json
from criar_animado import garantir_pergunta_final

r = {
    "categoria": "curiosidades",
    "tema": "o oceano profundo",
    "tom": "misterioso",
    "pergunta_final": "E você, teria coragem de mergulhar lá?",
    "cenas": [{"narracao": "O oceano esconde segredos. E você, teria coragem de mergulhar lá?"}],
}

r1 = garantir_pergunta_final(r, r["categoria"], r["tema"])
r2 = garantir_pergunta_final(r1, r1["categoria"], r1["tema"])  # chamada dupla de propósito

print(json.dumps(r2, ensure_ascii=False, indent=2))
