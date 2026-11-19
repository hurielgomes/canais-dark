"""recursos_ativos.py - ativos procedurais DETALHADOS (varias partes + animacoes por JSON).

Servem de reserva quando a IA nao esta disponivel/falha. Cada funcao devolve (svg, sidecar, tipo, nome, tags).
O sidecar traz pivos e animacoes proprias (soldado caminha, canhao recua, radar varre, bandeira ondula...).
"""


def _s(vb, corpo, defs=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vb[0]} {vb[1]}" width="{vb[0]}" height="{vb[1]}">'
            f'<defs>{defs}</defs>{corpo}</svg>')


def _g(i, a, b):
    return f'<linearGradient id="{i}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{a}"/><stop offset="1" stop-color="{b}"/></linearGradient>'


def _gh(i, a, b):
    return f'<linearGradient id="{i}" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{a}"/><stop offset="1" stop-color="{b}"/></linearGradient>'


def _halo(cx, cy, r, cor, a=0.2, n=4):
    return "".join(f'<circle cx="{cx}" cy="{cy}" r="{r * (1 + k * .45):.0f}" fill="{cor}" opacity="{a / (k + 1):.3f}"/>' for k in range(n))


def soldado(_cor="#4b5d3a"):
    defs = _g("cam", "#5d7347", "#34432a") + _g("pele", "#e6b894", "#c48e68") + _g("cap", "#566b40", "#2f3d25") + _g("bota", "#2a2a2a", "#0d0d0d")
    corpo = (
        '<g id="perna_e"><rect x="108" y="300" width="40" height="150" rx="14" fill="url(#cam)"/><rect x="108" y="352" width="40" height="22" fill="#2b3822" opacity="0.6"/>'
        '<path d="M100 440 H152 L158 480 Q158 492 146 492 H96 Q94 470 100 440 Z" fill="url(#bota)"/><rect x="100" y="440" width="52" height="8" fill="#111"/></g>'
        '<g id="perna_d"><rect x="154" y="300" width="40" height="150" rx="14" fill="url(#cam)"/><rect x="154" y="332" width="40" height="22" fill="#2b3822" opacity="0.6"/>'
        '<path d="M148 440 H200 L206 480 Q206 492 194 492 H144 Q142 470 148 440 Z" fill="url(#bota)"/><rect x="148" y="440" width="52" height="8" fill="#111"/></g>'
        '<g id="tronco"><path d="M92 172 Q150 150 208 172 L218 312 H82 Z" fill="url(#cam)"/>'
        '<path d="M92 172 Q150 150 208 172 L204 190 Q150 174 96 190 Z" fill="#7d9460" opacity="0.5"/>'
        '<rect x="82" y="290" width="136" height="20" fill="#241f18"/><rect x="140" y="292" width="20" height="16" fill="#c9a84a"/>'
        '<rect x="96" y="214" width="42" height="38" rx="5" fill="#2e3d26"/><rect x="162" y="214" width="42" height="38" rx="5" fill="#2e3d26"/>'
        '<rect x="96" y="214" width="42" height="8" fill="#41552f"/><rect x="162" y="214" width="42" height="8" fill="#41552f"/>'
        '<path d="M110 178 L150 300 L170 300 L130 176 Z" fill="#1d1a14" opacity="0.8"/>'
        '<ellipse cx="128" cy="262" rx="12" ry="7" fill="#3c4d2f"/><ellipse cx="180" cy="236" rx="9" ry="12" fill="#26331e"/></g>'
        '<g id="braco_e"><rect x="62" y="176" width="36" height="128" rx="17" fill="url(#cam)"/><circle cx="80" cy="312" r="15" fill="url(#pele)"/>'
        '<rect x="62" y="236" width="36" height="9" fill="#26331e"/></g>'
        '<g id="arma"><rect x="168" y="238" width="118" height="16" rx="4" fill="#1c1c1f"/><rect x="262" y="232" width="44" height="8" fill="#2a2a2e"/>'
        '<path d="M168 240 H146 Q140 240 140 250 V272 H168 Z" fill="#3a2d20"/><rect x="204" y="254" width="12" height="26" fill="#17171a"/>'
        '<rect x="190" y="232" width="30" height="7" fill="#303034"/></g>'
        '<g id="braco_d"><rect x="202" y="176" width="36" height="110" rx="17" fill="url(#cam)"/><rect x="202" y="228" width="36" height="9" fill="#26331e"/>'
        '<path d="M210 286 L262 252" stroke="#34432a" stroke-width="30" stroke-linecap="round" fill="none"/><circle cx="268" cy="248" r="14" fill="url(#pele)"/></g>'
        '<g id="cabeca"><rect x="136" y="132" width="28" height="30" fill="#c48e68"/><ellipse cx="150" cy="112" rx="38" ry="42" fill="url(#pele)"/>'
        '<path d="M108 108 Q108 56 150 54 Q192 56 192 108 Q150 92 108 108 Z" fill="url(#cap)"/><path d="M104 108 Q150 90 196 108 L198 118 Q150 100 102 118 Z" fill="#2a3722"/>'
        '<path d="M120 64 Q150 48 180 64" stroke="#8aa06b" stroke-width="5" fill="none" opacity="0.6"/>'
        '<circle cx="168" cy="118" r="4" fill="#1b1b1b"/><circle cx="140" cy="118" r="4" fill="#1b1b1b"/><path d="M146 138 Q158 144 168 136" stroke="#7a4a36" stroke-width="3" fill="none"/>'
        '<path d="M114 124 Q116 150 138 152" stroke="#1f2a1a" stroke-width="4" fill="none"/></g>')
    side = {"partes": {"perna_e": {"pivo": [128, 302]}, "perna_d": {"pivo": [174, 302]}, "braco_e": {"pivo": [80, 184]},
                       "braco_d": {"pivo": [220, 184]}, "cabeca": {"pivo": [150, 160]}, "tronco": {"pivo": [150, 310]}, "arma": {"pivo": [168, 246]}},
            "animacoes": {
                "parado": {"dur": 4.0, "loop": True, "faixas": {"tronco": {"sy": [[0, 1], [2, 1.012], [4, 1]]}, "cabeca": {"rot": [[0, 0], [2, 1.5], [4, 0]]}}},
                "alerta": {"dur": 1.6, "loop": True, "faixas": {"cabeca": {"rot": [[0, -6], [0.8, 6], [1.6, -6]]}, "braco_d": {"rot": [[0, -4], [0.8, 4], [1.6, -4]]}}},
                "apontar": {"dur": 2.0, "loop": False, "faixas": {"braco_d": {"rot": [[0, 0], [0.5, -35, "out_cubic"], [2, -35]]}, "arma": {"rot": [[0, 0], [0.5, -35, "out_cubic"], [2, -35]]}}}}}
    return _s((330, 500), corpo, defs), side, "personagem", "Soldado", ["soldado", "exercito", "militar", "tropa"]


def tanque(_c="#4b5d3a"):
    defs = _g("casco", "#6a8050", "#2f3d26") + _g("torre", "#78905a", "#38472c") + _g("esteira", "#2d2d33", "#0f0f12")
    corpo = (
        '<g id="esteiras"><rect x="30" y="170" width="350" height="64" rx="32" fill="url(#esteira)"/>'
        + "".join(f'<circle cx="{66 + 46 * i}" cy="203" r="19" fill="#4a4a54" stroke="#17171b" stroke-width="5"/><circle cx="{66 + 46 * i}" cy="203" r="6" fill="#1b1b20"/>' for i in range(7))
        + '<rect x="30" y="168" width="350" height="8" fill="#51515c" opacity="0.5"/></g>'
        '<g id="casco"><path d="M38 170 L60 122 H350 L378 170 Z" fill="url(#casco)"/><path d="M60 122 H350 L356 132 H54 Z" fill="#9db27d" opacity="0.5"/>'
        '<rect x="96" y="136" width="70" height="20" rx="3" fill="#2a3621" opacity="0.8"/><rect x="290" y="134" width="40" height="26" rx="3" fill="#2a3621" opacity="0.8"/>'
        '<path d="M70 150 L100 140 L130 156 L90 164 Z" fill="#3b4a2e" opacity="0.7"/><path d="M230 150 L270 140 L300 158 L250 166 Z" fill="#2c3822" opacity="0.7"/></g>'
        '<g id="canhao"><rect x="250" y="86" width="150" height="16" rx="4" fill="#2b2f2a"/><rect x="382" y="82" width="26" height="24" rx="3" fill="#1c1f1b"/><rect x="250" y="88" width="150" height="4" fill="#5d6a58" opacity="0.7"/></g>'
        '<g id="torre"><path d="M120 122 L140 82 Q205 66 270 82 L292 122 Z" fill="url(#torre)"/><path d="M140 82 Q205 66 270 82 L266 90 Q205 76 144 90 Z" fill="#a9be8a" opacity="0.5"/>'
        '<ellipse cx="180" cy="86" rx="22" ry="8" fill="#232c1c"/><rect x="214" y="70" width="6" height="22" fill="#1a1a1a"/><circle cx="217" cy="68" r="6" fill="#d9453a"/>'
        '<path d="M150 108 H260" stroke="#27331f" stroke-width="3"/></g>'
        '<g id="clarao"><path d="M410 94 L450 70 L434 94 L458 100 L432 106 L446 128 L410 104 Z" fill="#ffb02e"/><path d="M410 94 L436 84 L428 96 L440 100 L426 104 L412 100 Z" fill="#fff3c0"/>'
        + _halo(420, 94, 40, "#ffb02e", 0.25, 3) + '</g>')
    side = {"partes": {"canhao": {"pivo": [260, 94]}, "torre": {"pivo": [205, 122]}, "casco": {"pivo": [205, 170]}, "esteiras": {"pivo": [205, 234]}, "clarao": {"pivo": [410, 94]}},
            "pose_base": {"clarao": {"op": 0}},
            "animacoes": {
                "parado": {"dur": 3.0, "loop": True, "faixas": {"casco": {"ty": [[0, 0], [1.5, -1.5], [3, 0]]}, "esteiras": {"ty": [[0, 0], [1.5, -1], [3, 0]]}}},
                "atirar": {"dur": 1.4, "loop": False, "faixas": {"canhao": {"tx": [[0, 0], [0.06, -18], [0.9, 0, "out_cubic"]]},
                                                                  "clarao": {"op": [[0, 0], [0.03, 1], [0.28, 0]], "sx": [[0, 0.6], [0.1, 1.2], [0.3, 1]]},
                                                                  "casco": {"tx": [[0, 0], [0.06, -5], [0.9, 0]]}}},
                "rodar": {"dur": 0.5, "loop": True, "faixas": {"casco": {"ty": [[0, 0], [0.25, -2.5], [0.5, 0]]}}}}}
    return _s((470, 250), corpo, defs), side, "objeto", "Tanque de guerra", ["tanque", "blindado", "veiculo", "combate"]


def aviao(_c="#8fa0b8"):
    defs = _g("fus", "#c5d0e0", "#5d6a82") + _g("asa", "#7e8da6", "#3d475c")
    corpo = (
        '<g id="chama">' + _halo(36, 100, 26, "#ff9a3a", 0.35, 3) + '<path d="M70 92 L8 100 L70 108 Z" fill="#ffb02e"/><path d="M70 95 L30 100 L70 105 Z" fill="#fff3c0"/></g>'
        '<g id="asas"><path d="M170 100 L250 20 L290 20 L250 100 Z" fill="url(#asa)"/><path d="M170 106 L250 186 L290 186 L250 106 Z" fill="url(#asa)"/>'
        '<path d="M96 100 L60 60 L84 60 L128 100 Z" fill="url(#asa)"/><path d="M96 100 L60 140 L84 140 L128 100 Z" fill="url(#asa)"/>'
        '<rect x="262" y="22" width="22" height="6" fill="#d9453a"/><rect x="262" y="178" width="22" height="6" fill="#d9453a"/></g>'
        '<g id="corpo"><path d="M60 92 Q60 84 90 82 L300 92 Q380 100 398 103 Q380 108 300 114 L90 120 Q60 118 60 110 Z" fill="url(#fus)"/>'
        '<path d="M90 86 L300 94 Q360 99 384 102 L300 98 L90 92 Z" fill="#f2f6ff" opacity="0.6"/><path d="M180 112 H300" stroke="#3d475c" stroke-width="3" opacity="0.6"/>'
        '<path d="M250 90 Q290 70 330 94 Z" fill="#7fd0ff" opacity="0.85"/><path d="M262 88 Q290 76 316 92" stroke="#fff" stroke-width="3" fill="none" opacity="0.7"/>'
        '<circle cx="176" cy="104" r="9" fill="#2b3446"/><circle cx="176" cy="104" r="5" fill="#d9453a"/>'
        '<path d="M110 100 H170" stroke="#2b3446" stroke-width="3"/><rect x="330" y="100" width="40" height="3" fill="#2b3446" opacity="0.5"/></g>')
    side = {"animacoes": {"voar": {"dur": 3.0, "loop": True, "faixas": {"corpo": {"ty": [[0, 0], [1.5, -10], [3, 0]], "rot": [[0, 0], [1.5, -1.5], [3, 0]]},
                                                                      "asas": {"ty": [[0, 0], [1.5, -10], [3, 0]], "rot": [[0, 0], [1.5, -1.5], [3, 0]]},
                                                                      "chama": {"ty": [[0, 0], [1.5, -10], [3, 0]], "op": [[0, 1], [0.3, 0.6], [0.6, 1], [3, 1]]}}}}}
    return _s((410, 206), corpo, defs), side, "objeto", "Caca de combate", ["aviao", "caca", "aeronave", "aereo", "aerea"]


def missil(_c="#d9453a"):
    defs = _g("mc", "#e8edf5", "#6b7686")
    corpo = (
        '<g id="chama">' + _halo(30, 60, 24, "#ff9a3a", 0.35, 3) + '<path d="M70 48 L4 60 L70 72 Z" fill="#ffb02e"/><path d="M70 52 L28 60 L70 68 Z" fill="#fff3c0"/></g>'
        '<g id="corpo"><path d="M70 40 H300 Q372 44 396 60 Q372 76 300 80 H70 Z" fill="url(#mc)"/><path d="M300 40 Q372 44 396 60 Q372 76 300 80 Z" fill="#d9453a"/>'
        '<rect x="140" y="40" width="14" height="40" fill="#d9453a"/><rect x="170" y="40" width="6" height="40" fill="#1f2530"/><rect x="214" y="40" width="40" height="8" fill="#3d475c" opacity="0.6"/>'
        '<path d="M70 40 L40 12 L92 40 Z" fill="#7a8599"/><path d="M70 80 L40 108 L92 80 Z" fill="#7a8599"/><path d="M290 40 L276 20 L316 40 Z" fill="#7a8599"/><path d="M290 80 L276 100 L316 80 Z" fill="#7a8599"/>'
        '<path d="M80 46 H290" stroke="#fff" stroke-width="3" opacity="0.55"/></g>')
    side = {"animacoes": {"voar": {"dur": 0.8, "loop": True, "faixas": {"chama": {"sx": [[0, 1], [0.2, 1.25], [0.4, 0.9], [0.8, 1]], "op": [[0, 1], [0.4, 0.65], [0.8, 1]]}}}}}
    return _s((410, 120), corpo, defs), side, "objeto", "Missil", ["missil", "misseis", "projetil", "foguete"]


def navio(_c="#6b7a90"):
    defs = _g("casco", "#5f6f86", "#1f2736") + _g("sup", "#aab6c8", "#58667c")
    corpo = (
        '<g id="agua"><path d="M0 214 Q40 200 80 214 T160 214 T240 214 T320 214 T400 214 T440 214 V240 H0 Z" fill="#1d3b63" opacity="0.8"/></g>'
        '<g id="casco"><path d="M20 150 H400 L368 214 H62 Z" fill="url(#casco)"/><rect x="40" y="164" width="340" height="6" fill="#d9453a" opacity="0.8"/>'
        + "".join(f'<circle cx="{92 + 30 * i}" cy="182" r="4" fill="#ffd37a" opacity="0.85"/>' for i in range(9)) + '</g>'
        '<g id="superestrutura"><rect x="140" y="104" width="150" height="46" fill="url(#sup)"/><rect x="176" y="70" width="84" height="36" fill="url(#sup)"/>'
        '<rect x="190" y="78" width="56" height="12" fill="#7fd0ff" opacity="0.8"/><rect x="156" y="116" width="14" height="10" fill="#2b3446"/><rect x="186" y="116" width="14" height="10" fill="#2b3446"/>'
        '<rect x="216" y="116" width="14" height="10" fill="#2b3446"/><rect x="246" y="116" width="14" height="10" fill="#2b3446"/>'
        '<rect x="214" y="30" width="6" height="42" fill="#3d475c"/><path d="M196 44 H240 L232 52 H204 Z" fill="#7a8599"/><circle cx="217" cy="28" r="5" fill="#d9453a"/></g>'
        '<g id="canhao"><rect x="296" y="124" width="60" height="9" rx="3" fill="#2b2f36"/><ellipse cx="300" cy="130" rx="22" ry="12" fill="#58667c"/></g>')
    side = {"partes": {"agua": {"pivo": [220, 240]}, "casco": {"pivo": [220, 214]}, "superestrutura": {"pivo": [220, 214]}, "canhao": {"pivo": [220, 214]}},
            "animacoes": {"parado": {"dur": 4.0, "loop": True, "faixas": {k: {"rot": [[0, -1.4], [2, 1.4], [4, -1.4]], "ty": [[0, 0], [2, -3], [4, 0]]} for k in ("casco", "superestrutura", "canhao")}}}}
    return _s((440, 240), corpo, defs), side, "objeto", "Navio de guerra", ["navio", "marinha", "naval", "fragata"]


def bandeira(_c="#2fa84f"):
    corpo = (
        '<g id="mastro"><rect x="26" y="20" width="10" height="330" rx="4" fill="#cfd5df"/><circle cx="31" cy="18" r="9" fill="#e8c14a"/></g>'
        '<g id="pano"><rect x="36" y="36" width="290" height="190" fill="#1f9d4f"/><path d="M181 50 L312 131 L181 212 L50 131 Z" fill="#ffd21f"/>'
        '<circle cx="181" cy="131" r="52" fill="#2548a8"/><path d="M130 122 Q181 104 232 132 L231 144 Q181 120 131 136 Z" fill="#ffffff"/>'
        '<rect x="36" y="36" width="290" height="190" fill="#000" opacity="0.08"/><path d="M36 36 H326 L300 56 H36 Z" fill="#fff" opacity="0.14"/></g>')
    side = {"partes": {"pano": {"pivo": [36, 131]}, "mastro": {"pivo": [31, 350]}},
            "animacoes": {"ondular": {"dur": 2.2, "loop": True, "faixas": {"pano": {"sx": [[0, 1], [1.1, 0.93], [2.2, 1]], "rot": [[0, 0], [1.1, 1.8], [2.2, 0]]}}},
                          "parado": {"dur": 2.2, "loop": True, "faixas": {"pano": {"sx": [[0, 1], [1.1, 0.96], [2.2, 1]]}}}}}
    return _s((340, 360), corpo), side, "objeto", "Bandeira do Brasil", ["bandeira", "brasil", "nacional", "pais"]


def radar(_c="#3ddc84"):
    corpo = (
        '<g id="painel"><circle cx="150" cy="150" r="140" fill="#06140d" stroke="#2c5a3f" stroke-width="8"/>'
        + "".join(f'<circle cx="150" cy="150" r="{r}" fill="none" stroke="#3ddc84" stroke-width="2" opacity="0.5"/>' for r in (35, 70, 105))
        + '<path d="M150 14 V286 M14 150 H286" stroke="#3ddc84" stroke-width="2" opacity="0.4"/></g>'
        '<g id="varredura"><path d="M150 150 L150 12 A138 138 0 0 1 252 56 Z" fill="#3ddc84" opacity="0.28"/><path d="M150 150 L150 12" stroke="#b6ffd2" stroke-width="3"/></g>'
        '<g id="alvos"><circle cx="196" cy="98" r="7" fill="#ff5a4a"/><circle cx="104" cy="196" r="6" fill="#ff5a4a"/><circle cx="214" cy="190" r="5" fill="#ffd21f"/>'
        + _halo(196, 98, 14, "#ff5a4a", 0.3, 2) + '</g>')
    side = {"partes": {"varredura": {"pivo": [150, 150]}, "painel": {"pivo": [150, 150]}, "alvos": {"pivo": [150, 150]}},
            "animacoes": {"varrer": {"dur": 3.0, "loop": True, "faixas": {"varredura": {"rot": [[0, 0], [3, 360]]}, "alvos": {"op": [[0, 1], [1.5, 0.45], [3, 1]]}}},
                          "parado": {"dur": 3.0, "loop": True, "faixas": {"varredura": {"rot": [[0, 0], [3, 360]]}}}}}
    return _s((300, 300), corpo), side, "objeto", "Radar", ["radar", "defesa", "satelite", "monitoramento", "vigilancia"]


def mapa(_c="#4a8cff"):
    defs = _g("pn", "#142340", "#0a1428")
    corpo = (
        '<g id="painel"><rect x="10" y="10" width="330" height="280" rx="14" fill="url(#pn)" stroke="#3a5a99" stroke-width="5"/>'
        + "".join(f'<path d="M{10 + 33 * i} 10 V290" stroke="#2c4a80" stroke-width="1.5" opacity="0.6"/>' for i in range(1, 10))
        + "".join(f'<path d="M10 {10 + 28 * i} H340" stroke="#2c4a80" stroke-width="1.5" opacity="0.6"/>' for i in range(1, 10)) + '</g>'
        '<g id="territorio"><path d="M120 70 L180 52 L238 70 L268 110 L252 160 L226 196 L196 236 L158 252 L128 224 L96 186 L82 140 L96 98 Z" fill="#2f6bd9" opacity="0.85" stroke="#7fb0ff" stroke-width="3"/>'
        '<path d="M130 100 L180 88 L226 106 L240 140 L212 176 L170 190 L128 160 Z" fill="#4a8cff" opacity="0.6"/></g>'
        '<g id="alvos"><circle cx="196" cy="120" r="7" fill="#ff5a4a"/><circle cx="150" cy="170" r="7" fill="#ff5a4a"/><circle cx="214" cy="190" r="6" fill="#ffd21f"/>'
        + _halo(196, 120, 16, "#ff5a4a", 0.3, 3) + _halo(150, 170, 16, "#ff5a4a", 0.3, 3) + '</g>'
        '<g id="rota"><path d="M60 250 Q130 200 196 120" stroke="#ff5a4a" stroke-width="4" stroke-dasharray="12 8" fill="none"/><path d="M196 120 L180 128 L184 112 Z" fill="#ff5a4a"/></g>')
    side = {"animacoes": {"pulsar": {"dur": 1.4, "loop": True, "faixas": {"alvos": {"op": [[0, 1], [0.7, 0.35], [1.4, 1]]}}}}}
    return _s((350, 300), corpo, defs), side, "objeto", "Mapa tatico", ["mapa", "territorio", "fronteira", "estrategia", "regiao"]


def explosao(_c="#ff9a3a"):
    def estrela(cx, cy, r1, r2, n, cor, rot=0):
        import math
        pts = []
        for i in range(n * 2):
            r = r1 if i % 2 == 0 else r2
            a = math.pi * i / n + rot
            pts.append(f"{cx + r * math.cos(a):.0f},{cy + r * math.sin(a):.0f}")
        return f'<polygon points="{" ".join(pts)}" fill="{cor}"/>'
    corpo = ('<g id="brilho">' + _halo(150, 150, 100, "#ff9a3a", 0.3, 4) + '</g>'
             '<g id="fumaca"><circle cx="90" cy="86" r="46" fill="#2a2630" opacity="0.8"/><circle cx="150" cy="60" r="52" fill="#34303c" opacity="0.8"/><circle cx="214" cy="86" r="44" fill="#2a2630" opacity="0.8"/></g>'
             '<g id="fogo">' + estrela(150, 160, 124, 66, 11, "#e8421e") + estrela(150, 160, 98, 54, 10, "#ff9a3a", 0.2) + estrela(150, 160, 66, 36, 9, "#ffd23a", 0.4) + '</g>'
             '<g id="nucleo"><circle cx="150" cy="160" r="30" fill="#fff6c8"/></g>')
    side = {"partes": {k: {"pivo": [150, 170]} for k in ("brilho", "fumaca", "fogo", "nucleo")},
            "animacoes": {"parado": {"dur": 1.2, "loop": True, "faixas": {"fogo": {"sx": [[0, 1], [0.6, 1.08], [1.2, 1]], "sy": [[0, 1], [0.6, 1.08], [1.2, 1]], "rot": [[0, 0], [1.2, 6]]},
                                                                  "nucleo": {"op": [[0, 1], [0.4, 0.6], [1.2, 1]]}, "brilho": {"op": [[0, 1], [0.6, 0.6], [1.2, 1]]}}}}}
    return _s((300, 300), corpo), side, "objeto", "Explosao", ["explosao", "bomba", "ataque", "detonacao", "bombardeio"]


def dinheiro(_c="#e8c14a"):
    defs = _g("ouro", "#ffe27a", "#b8860b")
    pilha = "".join(f'<ellipse cx="{cx}" cy="{cy}" rx="52" ry="16" fill="url(#ouro)" stroke="#8a6508" stroke-width="3"/><rect x="{cx - 52}" y="{cy}" width="104" height="10" fill="#c99a14"/>'
                    f'<ellipse cx="{cx}" cy="{cy + 10}" rx="52" ry="16" fill="#9a7210"/><ellipse cx="{cx}" cy="{cy}" rx="52" ry="16" fill="url(#ouro)" stroke="#8a6508" stroke-width="3"/>'
                    for cx, cy in ((100, 168), (100, 150), (100, 132), (100, 114), (172, 176), (172, 158)))
    corpo = '<g id="brilho">' + _halo(130, 130, 70, "#ffd23a", 0.22, 3) + '</g><g id="moedas">' + pilha + '</g>'
    return _s((240, 210), corpo, defs), None, "objeto", "Dinheiro", ["dinheiro", "economia", "moeda", "orcamento", "custo", "pib", "preco", "inflacao"]


def grafico(_c="#e8353d"):
    defs = _g("pn", "#142340", "#0a1428")
    barras = "".join(f'<rect x="{34 + 52 * i}" y="{40 + 22 * i}" width="38" height="{190 - 22 * i}" rx="4" fill="{"#e8353d" if i > 1 else "#ffb02e"}"/>' for i in range(5))
    corpo = ('<g id="painel"><rect x="8" y="8" width="300" height="250" rx="14" fill="url(#pn)" stroke="#3a5a99" stroke-width="5"/>'
             + "".join(f'<path d="M20 {50 + 40 * i} H296" stroke="#2c4a80" stroke-width="1.5" opacity="0.6"/>' for i in range(5)) + '</g>'
             f'<g id="barras">{barras}</g><g id="seta"><path d="M30 60 L250 190" stroke="#ff5a4a" stroke-width="7" stroke-linecap="round" fill="none"/><path d="M262 198 L232 196 L244 172 Z" fill="#ff5a4a"/></g>')
    side = {"animacoes": {"pulsar": {"dur": 1.4, "loop": True, "faixas": {"seta": {"op": [[0, 1], [0.7, 0.4], [1.4, 1]]}}}}}
    return _s((316, 268), corpo, defs), side, "objeto", "Grafico em queda", ["grafico", "queda", "recessao", "crise", "mercado", "bolsa"]


ATIVOS = {"soldado": soldado, "tanque": tanque, "aviao": aviao, "missil": missil, "navio": navio, "bandeira": bandeira,
          "radar": radar, "mapa": mapa, "explosao": explosao, "dinheiro": dinheiro, "grafico": grafico}

# radical da palavra no texto -> ativo
CHAVES_ATIVO = {
    "soldad": "soldado", "exercit": "soldado", "militar": "soldado", "tropa": "soldado", "combatente": "soldado", "recrut": "soldado", "infantaria": "soldado",
    "tanque": "tanque", "blindad": "tanque", "artilharia": "tanque",
    "aviao": "aviao", "avioes": "aviao", "caca": "aviao", "aerea": "aviao", "aereo": "aviao", "aeronave": "aviao", "aeronautica": "aviao", "bombardeiro": "aviao",
    "missil": "missil", "misseis": "missil", "foguete": "missil", "projetil": "missil",
    "navio": "navio", "naval": "navio", "marinha": "navio", "fragata": "navio", "porta-avioes": "navio", "submarino": "navio",
    "bandeira": "bandeira", "brasil": "bandeira", "nacional": "bandeira",
    "radar": "radar", "satelite": "radar", "defesa": "radar", "vigilancia": "radar", "monitor": "radar",
    "mapa": "mapa", "territor": "mapa", "fronteira": "mapa", "estrateg": "mapa", "invasao": "mapa", "invad": "mapa",
    "explos": "explosao", "bomba": "explosao", "bombardeio": "explosao", "ataque": "explosao", "atac": "explosao", "detona": "explosao",
    "dinheiro": "dinheiro", "economia": "dinheiro", "economic": "dinheiro", "moeda": "dinheiro", "orcamento": "dinheiro", "custo": "dinheiro", "inflacao": "dinheiro", "pib": "dinheiro",
    "bolsa": "grafico", "mercado": "grafico", "recessao": "grafico", "queda": "grafico", "grafico": "grafico",
}


# ------------------------------------------------------------------ kit didatico: objetos cujo ESTADO muda (como o termometro da referencia)
def termometro(_c="#e8353d"):
    defs = _g("tb", "#1a2540", "#0c1428") + _g("mer", "#ff6a5a", "#c4202a")
    ticks = "".join(f'<rect x="{104 if i % 2 else 100}" y="{70 + 26 * i}" width="{18 if i % 2 else 28}" height="3" fill="#9fb0d8" opacity="0.8"/>' for i in range(11))
    corpo = ('<g id="brilho">' + _halo(100, 352, 62, "#ff4a4a", 0.32, 4) + '</g>'
             '<g id="tubo"><rect x="72" y="40" width="56" height="300" rx="28" fill="url(#tb)" stroke="#8fa3d6" stroke-width="5"/>'
             '<rect x="80" y="52" width="8" height="260" rx="4" fill="#fff" opacity="0.18"/>' + ticks + '</g>'
             '<g id="mercurio"><rect x="86" y="70" width="28" height="272" rx="14" fill="url(#mer)"/></g>'
             '<g id="bulbo"><circle cx="100" cy="352" r="40" fill="#8fa3d6"/><circle cx="100" cy="352" r="33" fill="url(#mer)"/><circle cx="88" cy="340" r="9" fill="#fff" opacity="0.4"/></g>')
    side = {"partes": {"mercurio": {"pivo": [100, 342]}, "bulbo": {"pivo": [100, 352]}, "brilho": {"pivo": [100, 352]}},
            "animacoes": {"parado": {"dur": 1.0, "loop": True, "faixas": {"mercurio": {"sy": [[0, 0.22], [1, 0.22]]}}},
                          "subir": {"dur": 2.4, "loop": False, "faixas": {"mercurio": {"sy": [[0, 0.22], [2.4, 1.0, "out_cubic"]]}, "brilho": {"op": [[0, 0.5], [2.4, 1.0]]}}},
                          "descer": {"dur": 2.4, "loop": False, "faixas": {"mercurio": {"sy": [[0, 1.0], [2.4, 0.12, "out_cubic"]]}}}}}
    return _s((200, 410), corpo, defs), side, "objeto", "Termometro", ["termometro", "temperatura", "calor", "febre", "aquecimento", "esquenta"]


def medidor(_c="#ffb02e"):
    defs = _g("pn", "#142340", "#0a1428")
    seg = "".join(f'<path d="{d}" stroke="{cor}" stroke-width="22" fill="none" stroke-linecap="butt"/>' for d, cor in (
        ("M40 190 A110 110 0 0 1 96 92", "#3ddc84"), ("M96 92 A110 110 0 0 1 204 92", "#ffd21f"), ("M204 92 A110 110 0 0 1 260 190", "#ff4a4a")))
    corpo = ('<g id="painel"><path d="M10 200 A140 140 0 0 1 290 200 Z" fill="url(#pn)" stroke="#3a5a99" stroke-width="5"/>' + seg + '</g>'
             '<g id="ponteiro"><path d="M150 190 L146 100 L150 90 L154 100 Z" fill="#f2f6ff" stroke="#9fb0d8" stroke-width="2"/></g>'
             '<g id="eixo"><circle cx="150" cy="192" r="14" fill="#e8353d" stroke="#fff" stroke-width="4"/></g>')
    side = {"partes": {"ponteiro": {"pivo": [150, 190]}},
            "animacoes": {"parado": {"dur": 1.0, "loop": True, "faixas": {"ponteiro": {"rot": [[0, -62], [1, -62]]}}},
                          "subir": {"dur": 2.0, "loop": False, "faixas": {"ponteiro": {"rot": [[0, -62], [1.4, 66, "out_cubic"], [1.7, 58], [2.0, 66]]}}},
                          "descer": {"dur": 2.0, "loop": False, "faixas": {"ponteiro": {"rot": [[0, 60], [2.0, -62, "out_cubic"]]}}}}}
    return _s((300, 215), corpo, defs), side, "objeto", "Medidor", ["medidor", "risco", "pressao", "indice"]


def relogio_didatico(_c="#e8c14a"):
    marc = "".join(f'<rect x="118" y="26" width="4" height="{16 if i % 3 == 0 else 8}" fill="#2a2f40" transform="rotate({i * 30} 120 120)"/>' for i in range(12))
    corpo = ('<g id="brilho">' + _halo(120, 120, 92, "#ffd37a", 0.2, 3) + '</g>'
             '<g id="face"><circle cx="120" cy="120" r="102" fill="#f3f1ea" stroke="#e8c14a" stroke-width="10"/><circle cx="120" cy="120" r="92" fill="none" stroke="#cfc8b4" stroke-width="2"/>' + marc + '</g>'
             '<g id="ponteiro_h"><rect x="115" y="62" width="10" height="64" rx="5" fill="#2a2f40"/></g>'
             '<g id="ponteiro_m"><rect x="117" y="36" width="6" height="90" rx="3" fill="#2a2f40"/><rect x="118" y="30" width="4" height="30" fill="#d9453a"/></g>'
             '<g id="eixo"><circle cx="120" cy="120" r="9" fill="#d9453a"/></g>')
    side = {"partes": {"ponteiro_h": {"pivo": [120, 120]}, "ponteiro_m": {"pivo": [120, 120]}},
            "animacoes": {"parado": {"dur": 1.0, "loop": True, "faixas": {"ponteiro_m": {"rot": [[0, 0], [1, 0]]}}},
                          "passar": {"dur": 3.0, "loop": False, "faixas": {"ponteiro_m": {"rot": [[0, 0], [3.0, 720, "in_out"]]}, "ponteiro_h": {"rot": [[0, 0], [3.0, 60, "in_out"]]}}}}}
    return _s((240, 240), corpo), side, "objeto", "Relogio", ["relogio", "cronometro", "prazo", "contagem"]


def _barras(cresce):
    cores = ("#3ddc84", "#7fd0ff", "#ffd21f", "#ff9a3a", "#ff4a4a") if cresce else ("#ff4a4a", "#ff7a3a", "#ffb02e", "#ff9a3a", "#e8353d")
    alvo = (0.2, 0.4, 0.58, 0.78, 1.0) if cresce else (1.0, 0.78, 0.55, 0.34, 0.16)
    base_y, hmax = 232, 190
    barras = "".join(f'<g id="b{i + 1}"><rect x="{34 + 52 * i}" y="{base_y - hmax}" width="38" height="{hmax}" rx="5" fill="{cores[i]}"/>'
                     f'<rect x="{34 + 52 * i}" y="{base_y - hmax}" width="10" height="{hmax}" rx="4" fill="#fff" opacity="0.18"/></g>' for i in range(5))
    corpo = (f'<g id="painel"><rect x="8" y="8" width="300" height="246" rx="14" fill="#0c1428" stroke="#3a5a99" stroke-width="5"/>'
             + "".join(f'<path d="M22 {44 + 38 * i} H294" stroke="#2c4a80" stroke-width="1.5" opacity="0.6"/>' for i in range(5)) + '</g>' + barras)
    f_ini, f_fim = {}, {}
    ini = (alvo[0] * 0 + 0.06) if cresce else 1.0
    nome = "crescer" if cresce else "desabar"
    fx = {}
    for i in range(5):
        t0 = 0.15 + 0.28 * i
        fx[f"b{i + 1}"] = {"sy": [[0, ini], [t0, ini], [t0 + 0.7, alvo[i], "out_cubic"]]}
    side = {"partes": {f"b{i + 1}": {"pivo": [53 + 52 * i, base_y]} for i in range(5)},
            "animacoes": {"parado": {"dur": 1.0, "loop": True, "faixas": {f"b{i + 1}": {"sy": [[0, ini], [1, ini]]} for i in range(5)}},
                          nome: {"dur": 2.6, "loop": False, "faixas": fx}}}
    return (_s((316, 262), corpo), side, "objeto", "Barras crescendo" if cresce else "Barras desabando",
            (["barras", "crescimento", "aumento", "cresce"] if cresce else ["barras", "queda", "colapso", "desaba", "despenca", "perda"]))


def barras_crescendo(_c=None):
    return _barras(True)


def barras_caindo(_c=None):
    return _barras(False)


def alvo(_c="#ff4a4a"):
    aneis = "".join(f'<circle cx="120" cy="120" r="{r}" fill="none" stroke="#ff4a4a" stroke-width="{7 if k % 2 == 0 else 4}" opacity="0.9"/>' for k, r in enumerate((100, 72, 44)))
    corpo = ('<g id="brilho">' + _halo(120, 120, 80, "#ff4a4a", 0.2, 3) + '</g>'
             '<g id="aneis">' + aneis + '</g>'
             '<g id="mira"><path d="M120 4 V64 M120 176 V236 M4 120 H64 M176 120 H236" stroke="#f2f6ff" stroke-width="6" stroke-linecap="round"/></g>'
             '<g id="centro"><circle cx="120" cy="120" r="12" fill="#ff4a4a"/></g>')
    side = {"partes": {k: {"pivo": [120, 120]} for k in ("aneis", "mira", "centro", "brilho")},
            "animacoes": {"parado": {"dur": 1.0, "loop": True, "faixas": {"aneis": {"sx": [[0, 1], [1, 1]]}}},
                          "mirar": {"dur": 1.6, "loop": False, "faixas": {"aneis": {"sx": [[0, 1.7], [1.0, 1.0, "out_cubic"]], "sy": [[0, 1.7], [1.0, 1.0, "out_cubic"]]},
                                                                  "mira": {"rot": [[0, 45], [1.0, 0, "out_cubic"]], "sx": [[0, 1.3], [1.0, 1.0]], "sy": [[0, 1.3], [1.0, 1.0]]},
                                                                  "centro": {"sx": [[0, 1], [1.2, 1.5], [1.6, 1]], "sy": [[0, 1], [1.2, 1.5], [1.6, 1]]}}}}}
    return _s((240, 240), corpo), side, "objeto", "Alvo", ["alvo", "mira", "objetivo"]


KIT = {"termometro": termometro, "medidor": medidor, "relogio": relogio_didatico, "barras_crescendo": barras_crescendo,
       "barras_caindo": barras_caindo, "alvo": alvo}
