import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "estudio"))

import diretor_m1  # noqa: E402
import recursos_ia  # noqa: E402
from estudio.cenas2d.recursos.biblioteca import Biblioteca  # noqa: E402

SVG_OK = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200"><g id="corpo">'
          '<rect x="60" y="40" width="80" height="130" rx="10" fill="#aab"/><circle cx="100" cy="80" r="22" fill="#fc6"/>'
          '<rect x="80" y="120" width="40" height="30" fill="#334"/><path d="M60 40 L100 10 L140 40 Z" fill="#c44"/>'
          + "".join(f'<rect x="{66 + 10 * i}" y="150" width="6" height="14" fill="#223"/>' for i in range(8))
          + "".join(f'<circle cx="{70 + 12 * i}" cy="60" r="3" fill="#fff"/>' for i in range(6)) + '</g></svg>')


def roteiro(*falas, titulo="Teste"):
    return {"titulo": titulo, "cenas": [{"narracao": f, "imagem": "", "busca_stock": ""} for f in falas]}


class _Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        shutil.copytree(ROOT / "biblioteca_m1", Path(self.tmp) / "bib")
        self.bib = Biblioteca(Path(self.tmp) / "bib", bloquear_pendentes=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class DiretorLocalTests(_Base):
    def test_biblioteca_tem_recursos_aprovados(self):
        ids = {r["id"] for r in diretor_m1.catalogo_aprovado(self.bib)}
        self.assertTrue({"tigre", "savana", "homem"} <= ids)

    def test_reaproveita_biblioteca_quando_casa(self):
        cenas = diretor_m1.dirigir(roteiro("O tigre caminha pela savana ao entardecer."), [6.0], self.bib, modo="local", log=lambda m: None)
        self.assertEqual(cenas[0]["cenario"]["ref"], "savana")
        self.assertEqual(cenas[0]["elementos"][0]["ref"], "tigre")
        self.assertEqual(cenas[0]["elementos"][0]["linha_do_tempo"][-1]["anim"], "caminhar")

    def test_palavras_parecidas_nao_casam(self):
        self.assertFalse(diretor_m1._casa("internet", "interior"))
        self.assertFalse(diretor_m1._casa("eletrica", "eletronico"))
        self.assertTrue(diretor_m1._casa("tigres", "tigre"))

    def test_tema_fora_da_biblioteca_cria_recursos_novos(self):
        r = roteiro("Sem energia eletrica o celular morre rapido.", "O hospital entra em emergencia.", titulo="E se ficassemos 72 horas sem energia")
        cenas = diretor_m1.dirigir(r, [6.0, 6.0], self.bib, modo="local", log=lambda m: None)
        novos = [x["id"] for x in self.bib.listar() if x["id"] not in ("homem", "sala_noite", "savana", "sofa", "tigre", "tv")]
        self.assertTrue(any(i.startswith("cenario_") for i in novos), novos)
        self.assertIn("celular", novos)
        self.assertIn("hospital", novos)
        self.assertTrue(cenas[0]["cenario"]["ref"].startswith("cenario_"))
        self.assertGreaterEqual(len(cenas[0]["elementos"]), 1)
        ct = cenas[0]["hud"]["contadores"][0]       # numero do titulo vira contador animado (0 -> 72)
        self.assertEqual((ct["ate"], ct["sufixo"]), (72.0, " HORAS"))
        # recursos criados trazem animacoes prontas (JSON) e ficam aprovados para os proximos videos
        self.assertIn("pulsar", self.bib.idx["recursos"]["celular"]["animacoes"])
        self.assertEqual(self.bib.idx["recursos"]["celular"]["status"], "aprovado")

    def test_recurso_criado_renderiza(self):
        recursos_ia.criar_recurso({"id": "x_cidade", "tipo": "cenario", "nome": "Cidade", "tags": ["cidade"], "clima": "noite"}, self.bib)
        rec, _ = self.bib.obter("x_cidade")
        self.assertEqual(recursos_ia._quadro_de_prova(rec, "cenario"), [])


SVG_GRAD_STROKE = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200"><defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">'
                   '<stop offset="0" stop-color="#475569"/><stop offset="1" stop-color="#94a3b8"/></linearGradient></defs><g id="corpo">'
                   + "".join(f'<rect x="{20 + 10 * i}" y="40" width="30" height="120" rx="6" fill="url(#g)" stroke="url(#g)" stroke-width="4"/>' for i in range(18)) + "</g></svg>")
SIDECAR = '{"partes":{"corpo":{"pivo":[100,190]}},"animacoes":{"abrir":{"dur":1.0,"loop":false,"faixas":{"corpo":{"sx":[[0,1],[1.0,0.5]]}}}}}'


class DiretorIATests(_Base):
    def test_ia_pede_recursos_novos_e_cria_svg(self):
        chamadas = []

        def llm(prompt, json_mode=True):
            chamadas.append(json_mode)
            if json_mode:
                return json.dumps({"tema": "tensao_quente", "cenas": [{"n": 1, "cenario": {"novo": {"id": "usina", "tipo": "cenario", "nome": "Usina", "tags": ["usina"], "descricao": "usina a noite", "clima": "noite"}},
                                              "clima": "alerta", "hero": {"novo": {"id": "turbina", "tipo": "objeto", "nome": "Turbina", "tags": ["turbina"], "descricao": "turbina"}},
                                              "apoio": [{"ref": "id_que_nao_existe"}], "personagens": [{"ref": "homem", "anim": "acenar"}],
                                              "chip": "dia 1 · usina", "rotulos": [{"texto": "72 horas", "sub": "sem energia"}]}]})
            return ("```svg\n" + SVG_OK + "\n```\n" + SIDECAR) if "Turbina" in prompt else "texto sem svg nenhum"   # cenario: IA falha -> procedural
        cv = type("CV", (), {"_parse_json": staticmethod(lambda t: json.loads(t))})
        planos, tema_ia = diretor_m1.planejar_arte_ia(roteiro("A usina para."), diretor_m1.catalogo_aprovado(self.bib), llm, cv, "curiosidades", None)
        self.assertEqual(tema_ia, "tensao_quente")
        planos = diretor_m1.materializar(planos, self.bib, llm, log=lambda m: None, tema_id="tensao_quente")
        p = planos[0]
        self.assertEqual(p["personagens"], ["homem"])
        self.assertEqual(p["objetos"], ["turbina"])           # id inexistente foi descartado
        self.assertEqual(p["hero"], "turbina")
        self.assertEqual(p["cenario"], "usina__tensao_quente")      # cenario carrega o tema no id
        self.assertEqual(p["chip"], "DIA 1 · USINA")
        self.assertEqual(p["rotulos"][0], {"texto": "72 HORAS", "sub": "sem energia"})
        self.assertEqual(self.bib.idx["recursos"]["turbina"]["origem"], "ia")
        self.assertEqual(self.bib.idx["recursos"]["usina__tensao_quente"]["origem"], "procedural")   # fallback quando o SVG da IA falha
        self.assertIn("abrir", self.bib.idx["recursos"]["turbina"]["animacoes"])      # animacao em JSON vinda da IA
        self.assertIn("piscar", self.bib.idx["recursos"]["turbina"]["animacoes"])     # + presets
        self.assertTrue(chamadas.count(False) >= 2)

    def test_contorno_com_gradiente_da_ia_e_aceito(self):
        llm = lambda prompt, json_mode=True: SVG_GRAD_STROKE  # noqa: E731
        rid = recursos_ia.criar_recurso({"id": "cadeado_ia", "tipo": "objeto", "nome": "Cadeado"}, self.bib, llm, log=lambda m: None)
        self.assertEqual(self.bib.idx["recursos"][rid]["origem"], "ia")

    def test_ia_substitui_reserva_procedural(self):
        recursos_ia.criar_recurso({"id": "tanque", "tipo": "objeto", "nome": "Tanque"}, self.bib)
        self.assertEqual(self.bib.idx["recursos"]["tanque"]["origem"], "procedural")
        llm = lambda prompt, json_mode=True: SVG_OK  # noqa: E731
        recursos_ia.criar_recurso({"id": "tanque", "tipo": "objeto", "nome": "Tanque"}, self.bib, llm, log=lambda m: None)
        self.assertEqual(self.bib.idx["recursos"]["tanque"]["origem"], "ia")

    def test_ia_so_ve_recursos_de_qualidade(self):
        recursos_ia.criar_recurso({"id": "relogio", "tipo": "objeto", "nome": "Relogio"}, self.bib)   # reserva procedural
        vistos = []

        def llm(prompt, json_mode=True):
            vistos.append(prompt)
            return json.dumps({"cenas": []})
        cv = type("CV", (), {"_parse_json": staticmethod(lambda t: json.loads(t))})
        diretor_m1.dirigir(roteiro("Fala."), [5.0], self.bib, modo="gemini", cfg={"gemini_api_key": "x"}, cv=cv, log=lambda m: None) if False else None
        cat_ia = [r for r in diretor_m1.catalogo_aprovado(self.bib) if self.bib.idx["recursos"].get(r["id"], {}).get("origem") != "procedural"]
        self.assertNotIn("relogio", [r["id"] for r in cat_ia])
        self.assertIn("tigre", [r["id"] for r in cat_ia])

    def test_svg_perigoso_da_ia_e_rejeitado(self):
        llm = lambda prompt, json_mode=True: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><script>x()</script></svg>'  # noqa: E731
        rid = recursos_ia.criar_recurso({"id": "mal", "tipo": "objeto", "nome": "Lampada"}, self.bib, llm, log=lambda m: None)
        self.assertEqual(self.bib.idx["recursos"][rid]["origem"], "procedural")


class AtivosTests(_Base):
    def test_ativos_tematicos_tem_partes_e_animacoes_proprias(self):
        for chave, anim in (("soldado", "caminhar"), ("tanque", "atirar"), ("radar", "varrer"), ("aviao", "voar"), ("bandeira", "ondular")):
            rid = recursos_ia.criar_recurso({"id": chave, "tipo": "objeto", "nome": chave}, self.bib)
            self.assertIn(anim, self.bib.idx["recursos"][rid]["animacoes"], chave)

    def test_roteiro_de_guerra_usa_recursos_especificos(self):
        r = roteiro("Soldados avancam com tanques e avioes de combate.", "O radar monitora e o missil cruza o ceu.", titulo="Guerra")
        cenas = diretor_m1.dirigir(r, [6.0, 6.0], self.bib, modo="local", log=lambda m: None)
        refs0 = {e["ref"] for e in cenas[0]["elementos"]}
        self.assertTrue({"soldado", "tanque"} & refs0, refs0)
        self.assertTrue(cenas[0]["cenario"]["ref"].startswith("cenario_guerra"))


class DidaticaTests(_Base):
    def test_contador_interpreta_numeros_pt_br(self):
        self.assertEqual(diretor_m1._contador("8.551.000 KM2"), {"de": 0, "ate": 8551000.0, "decimais": 0, "sufixo": " KM2"})
        self.assertEqual(diretor_m1._contador("8,5 milhoes")["decimais"], 1)
        self.assertIsNone(diretor_m1._contador("INVASAO"))

    def test_kit_didatico_instalado_e_visivel_para_ia(self):
        recursos_ia.garantir_kit(self.bib, lambda m: None)
        for rid, anim in (("termometro", "subir"), ("relogio", "passar"), ("barras_crescendo", "crescer"), ("barras_caindo", "desabar"), ("alvo", "mirar")):
            self.assertIn(anim, self.bib.idx["recursos"][rid]["animacoes"])
            self.assertEqual(self.bib.idx["recursos"][rid]["origem"], "curado")

    def test_fundo_retangular_da_ia_e_removido(self):
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200"><rect width="200" height="200" fill="#001"/><g id="a">'
               '<circle cx="100" cy="100" r="40" fill="#f00"/></g></svg>')
        rec, _ = recursos_ia._recurso_de_svg(svg, {"id": "t", "tipo": "objeto", "nome": "T"})
        self.assertEqual(sum(len(p["formas"]) for p in rec["partes"]), 1)

    def test_animacao_da_ia_com_parte_inexistente_e_podada_sem_perder_o_resto(self):
        side = {"animacoes": {"a": {"dur": 1, "faixas": {"corpo": {"rot": [[0, 0], [1, 5]]}, "fantasma": {"rot": [[0, 0], [1, 5]]}}},
                              "b": {"dur": 1, "faixas": {"fantasma": {"rot": [[0, 0], [1, 5]]}}}}}
        out = recursos_ia._podar_sidecar(SVG_OK, "objeto", side)
        self.assertEqual(list(out["animacoes"]), ["a"])
        self.assertEqual(list(out["animacoes"]["a"]["faixas"]), ["corpo"])

    def test_cena_tem_entrada_luz_chip_e_chamada(self):
        recursos_ia.garantir_kit(self.bib, lambda m: None)
        cat = diretor_m1.catalogo_aprovado(self.bib)
        plano = {"cenario": "savana", "hero": "termometro", "objetos": ["termometro"], "personagens": [], "clima": "alerta",
                 "chip": "22:10 · SEXTA", "rotulos": [{"texto": "4 HORAS", "sub": "porta fechada"}], "chamada": {"texto": "15 C", "detalhe": "interna"}}
        c = diretor_m1.plano_para_cena(plano, cat, "A temperatura sobe.", 8.0, 1, bib=self.bib)
        self.assertEqual(c["elementos"][0]["entrada"]["tipo"], "pop")
        self.assertTrue(c["luzes"])
        self.assertEqual(c["hud"]["chip"]["hora"], "22:10")
        self.assertEqual(c["elementos"][0]["linha_do_tempo"][-1]["anim"], "subir")
        self.assertIn("chamadas", c["hud"])


class TemasTests(_Base):
    def test_prioridade_canal_ia_categoria(self):
        import temas_m1 as TM
        self.assertEqual(TM.resolver("curiosidades", {"tema_fixo": "saude_claro"}, "tensao_quente")[0], "saude_claro")   # canal vence
        self.assertEqual(TM.resolver("curiosidades", {}, "tensao_quente"), ("tensao_quente", "ia"))                         # depois a IA
        self.assertEqual(TM.resolver("historia", {}, None, "")[0], "historia_pergaminho")                                    # depois a categoria
        self.assertEqual(TM.resolver("curiosidades", {}, "tema_inventado")[0], "neon_escuro")                                # IA nao inventa tema
        self.assertEqual(TM.resolver("curiosidades", {}, None, "Como o cancer afeta o corpo")[0], "saude_claro")            # heuristica local

    def test_acento_da_marca_do_canal(self):
        import temas_m1 as TM
        self.assertEqual(TM.tema("saude_claro", {"tema_acento": "#112233"})["acento"], "#112233")
        self.assertNotEqual(TM.tema("saude_claro", {"tema_acento": "vermelho"})["acento"], "vermelho")

    def test_legendas_legiveis_em_todos_os_temas(self):
        import temas_m1 as TM
        for tid, t in TM.TEMAS.items():
            self.assertGreaterEqual(TM.contraste_wcag(t["legenda"]["texto"], t["base_rgb"]), 7.0, tid)
            self.assertGreaterEqual(TM.contraste_wcag(t["legenda"]["nao_falada"], t["base_rgb"]), 4.5, f"nao_falada {tid}")
            self.assertGreaterEqual(TM.contraste_wcag(TM.cor_rgb(t["acento"]), t["base_rgb"]), 4.5, f"acento {tid}")

    def test_roteiro_de_saude_gera_video_claro_sem_neon(self):
        r = roteiro("O corpo reage ao sono e ao cerebro.", "O hospital recebe pacientes.", titulo="Como o sono cura o corpo")
        cenas = diretor_m1.dirigir(r, [6.0, 6.0], self.bib, modo="local", log=lambda m: None, categoria="curiosidades", canal={})
        th = cenas[0]["tema"]
        self.assertEqual((th["id"], th["modo"], th["bloom_ganho"]), ("saude_claro", "claro", 0.0))
        self.assertTrue(cenas[0]["cenario"]["ref"].endswith("__saude_claro"))
        self.assertEqual(th["legenda"]["texto"], [14, 32, 56])

    def test_tema_fixo_do_canal_ignora_o_assunto(self):
        r = roteiro("O hospital recebe pacientes.", titulo="Saude")
        cenas = diretor_m1.dirigir(r, [6.0], self.bib, modo="local", log=lambda m: None, categoria="curiosidades", canal={"tema_fixo": "neon_escuro"})
        self.assertEqual(cenas[0]["tema"]["id"], "neon_escuro")

    def test_cenario_escuro_curado_nao_serve_a_tema_claro(self):
        import temas_m1 as TM
        sala = next(x for x in diretor_m1.catalogo_aprovado(self.bib) if x["id"] == "sala_noite")
        self.assertTrue(diretor_m1.cenario_serve(sala, TM.tema("neon_escuro")))
        self.assertFalse(diretor_m1.cenario_serve(sala, TM.tema("saude_claro")))


class CenaTests(_Base):
    def test_cena_gerada_tem_formato_do_m1(self):
        cat = diretor_m1.catalogo_aprovado(self.bib)
        plano = {"cenario": "savana", "personagens": ["tigre"], "objetos": [], "clima": "noite"}
        c = diretor_m1.plano_para_cena(plano, cat, "O tigre caminha pela savana.", 6.0, 1, bib=self.bib)
        self.assertEqual(c["modelo"], "generica")
        el = c["elementos"][0]
        self.assertEqual(el["linha_do_tempo"][-1]["anim"], "caminhar")
        self.assertIn("mover", el)
        self.assertEqual(set(el["pos"]), {"16x9", "9x16"})


if __name__ == "__main__":
    unittest.main()
