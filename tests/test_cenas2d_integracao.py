"""Testes da integracao do M1 (character_2_5d / criar_cenas2d.py). Rodar na raiz: python -m unittest tests.test_cenas2d_integracao -v"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "estudio"))

import engine_registry  # noqa: E402
from estudio.cenas2d import diretor  # noqa: E402
from estudio.cenas2d.recursos.biblioteca import Biblioteca  # noqa: E402


class TestRegistroDoMotor(unittest.TestCase):
    def test_motor_esta_ativo_e_instancia(self):
        self.assertTrue(engine_registry.is_engine_executable("character_2_5d"))
        a = engine_registry.get_adapter("character_2_5d")
        self.assertEqual(a.engine_id, "character_2_5d")
        self.assertTrue(a.supports_independent_deliverables)

    def test_comando_e_validacao(self):
        a = engine_registry.get_adapter("character_2_5d")
        cmd = a.build_command({"canal": "exemplo", "tema": "Tigres", "formatos": "9x16", "entrega_format": "9x16",
                               "duracao": 60, "categoria": "ciencia", "simular": True}, RAIZ, "python")
        self.assertEqual(Path(cmd[2]).name, "criar_cenas2d.py")
        for esperado in ("--entrega-format", "9x16", "--duracao", "60", "--simular", "--categoria", "ciencia"):
            self.assertIn(esperado, cmd)
        with self.assertRaises(ValueError):                 # a UI espera ValueError (nao lista de erros)
            a.validate_job({"canal": "exemplo", "tema": "", "formatos": "9x16"})
        with self.assertRaises(ValueError):
            a.validate_job({"canal": "exemplo", "tema": "x", "formatos": "1x1"})

    def test_retomada_so_aceita_pasta_dentro_de_projetos(self):
        a = engine_registry.get_adapter("character_2_5d")
        with self.assertRaises(ValueError):
            a.build_command({"canal": "exemplo", "tema": "x", "formatos": "9x16", "pasta": "../fora"}, RAIZ, "python")


class TestDiretorLocal(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.bib = Biblioteca(self.dir / "bib", aprovacao="auto")
        poc = RAIZ / "estudio" / "exemplos" / "recursos_poc"
        self.bib.registrar_pasta(poc)
        self.kits = diretor.carregar_kits(RAIZ / "biblioteca_m1" / "kits.json")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_kits_existem_e_sao_utilizaveis_com_recursos_aprovados(self):
        self.assertGreaterEqual(len(self.kits), 3)
        for k in self.kits:
            self.assertTrue(diretor.kit_usavel(k, self.bib)[0], k["id"])

    def test_kit_com_recurso_pendente_e_ignorado(self):
        b = Biblioteca(self.dir / "bib2", aprovacao="manual")
        b.registrar_pasta(RAIZ / "estudio" / "exemplos" / "recursos_poc")
        ok, falta = diretor.kit_usavel(self.kits[0], b)
        self.assertFalse(ok)
        self.assertTrue(all(s == "pendente" for _, s in falta))

    def test_escolha_por_palavras_e_fallback_neutro(self):
        k, _ = diretor.escolher_kit(self.kits, diretor.tokens("Os tigres estao em extincao"), 0)
        self.assertEqual(k["id"], "tigre_savana")
        k, motivo = diretor.escolher_kit(self.kits, diretor.tokens("Piramides do Egito"), 0)
        self.assertTrue(k.get("neutro"), motivo)

    def test_variedade_nao_repete_kit_e_usa_ambiente_do_tema(self):
        toks = diretor.tokens("Os tigres vivem na floresta")
        k1, _ = diretor.escolher_kit(self.kits, toks, 0, None, diretor.tokens("Tigres em extincao"))
        k2, motivo = diretor.escolher_kit(self.kits, toks, 1, k1["id"], diretor.tokens("Tigres em extincao"))
        self.assertEqual(k1["id"], "tigre_savana")
        self.assertNotEqual(k2["id"], k1["id"])
        self.assertEqual(k2["id"], "ambiente_savana", motivo)         # ambiente neutro coerente com o tema

    def test_instanciar_estica_o_tempo_e_define_legenda(self):
        k = next(x for x in self.kits if x["id"] == "tigre_savana")
        cena = diretor.instanciar(k, 7.0 * 1.5, [{"ini": 0, "fim": 1, "texto": "x"}], ["x"])
        self.assertEqual(cena["modelo"], "generica")
        self.assertAlmostEqual(cena["duracao"], 10.5)
        self.assertAlmostEqual(cena["elementos"][0]["mover"][-1]["t"], 5.3 * 1.5, places=2)
        # fator limitado: cena muito longa nao estica alem de 1.8x
        longa = diretor.instanciar(k, 70.0, [], [])
        self.assertAlmostEqual(longa["elementos"][0]["mover"][-1]["t"], 5.3 * 1.8, places=2)

    def test_cena_externa_nao_aceita_recurso_inline(self):
        self.assertEqual(diretor.validar_cena_externa({"elementos": [{"ref": "tigre"}]}), [])
        self.assertTrue(diretor.validar_cena_externa({"elementos": [{"def": {"id": "x"}}]}))
        self.assertTrue(diretor.validar_cena_externa({"elementos": [{"arquivo": "/etc/passwd"}]}))

    def test_destaques_e_legenda(self):
        self.assertEqual(diretor.destaques_de("Em 1998, 40% dos tigres sumiram")[:2], ["1998", "40%"])
        tr = diretor.trechos_legenda("um dois tres quatro cinco seis", 6.0, 0.35, 3)
        self.assertEqual(len(tr), 2)
        self.assertLessEqual(tr[-1]["fim"], 6.0 - 0.35 + 1e-6)


class TestBibliotecaPortavel(unittest.TestCase):
    def test_indice_com_barras_invertidas_do_windows(self):
        d = Path(tempfile.mkdtemp())
        try:
            b = Biblioteca(d, aprovacao="auto")
            b.registrar(RAIZ / "estudio" / "exemplos" / "recursos_poc" / "tigre.json")
            idx = json.loads((d / "index.json").read_text(encoding="utf-8"))
            self.assertNotIn("\\", idx["recursos"]["tigre"]["arquivo"])
            idx["recursos"]["tigre"]["arquivo"] = idx["recursos"]["tigre"]["arquivo"].replace("/", "\\")   # como gerado no Windows
            (d / "index.json").write_text(json.dumps(idx), encoding="utf-8")
            rec, _ = Biblioteca(d).obter("tigre")
            self.assertEqual(rec["id"], "tigre")
        finally:
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
