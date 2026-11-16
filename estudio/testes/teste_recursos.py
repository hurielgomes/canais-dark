"""
Testes do M1 generico (unittest, sem dependencias externas):  python -m unittest testes.teste_recursos -v   (de dentro de estudio/)
Cobrem: parser SVG, validacao/seguranca, biblioteca (dedupe, versao, aprovacao) e tolerancia a erros na cena.
"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from estudio.cenas2d.recursos import svgpath  # noqa: E402
from estudio.cenas2d.recursos.biblioteca import Biblioteca  # noqa: E402
from estudio.cenas2d.recursos.svg import importar_svg  # noqa: E402
from estudio.cenas2d.recursos.validar import RecursoInvalido, validar_recurso  # noqa: E402
from estudio.estilos.cenas2d import Estilo  # noqa: E402
from estudio.nucleo import Tela  # noqa: E402

POC = RAIZ / "exemplos" / "recursos_poc"
INV = RAIZ / "exemplos" / "recursos_invalidos"
OBJ_MIN = {"id": "caixa1", "tipo": "objeto", "caixa": [0, 0, 100, 100], "base": [50, 100],
           "partes": [{"id": "a", "pivo": [50, 50], "formas": [{"t": "rect", "x": 10, "y": 10, "w": 80, "h": 80, "fill": "#3366ff"}]}]}


class TestParser(unittest.TestCase):
    def test_comandos(self):
        s = svgpath.parse("M10 10 L20 10 H30 V30 C 30 40 20 40 10 30 S 0 20 10 10 Q 20 0 30 10 T 40 10 A 5 5 0 0 1 50 10 z")
        self.assertTrue(s[0][1])
        self.assertGreater(len(s[0][0]), 20)

    def test_relativos_e_implicitos(self):
        s = svgpath.parse("m 10 10 l 10 0 0 10 -10 0 z")
        self.assertEqual(len(s[0][0]), 5)

    def test_invalido(self):
        for d in ("M 10 10 Q Q 50", "M 1 2 X 3", "M 1 2 L abc"):
            with self.assertRaises(svgpath.CaminhoInvalido):
                svgpath.parse(d)

    def test_limites(self):
        with self.assertRaises(svgpath.CaminhoInvalido):
            svgpath.parse("M 0 0 " + "L 1 1 " * 30000)


class TestValidacao(unittest.TestCase):
    def test_minimo_ok(self):
        rec, av = validar_recurso(dict(OBJ_MIN))
        self.assertEqual(rec["id"], "caixa1")

    def test_arquivos_invalidos(self):
        for nome in ("json_caminho_invalido", "json_ciclo", "json_numeros_absurdos"):
            with self.assertRaises(RecursoInvalido, msg=nome):
                validar_recurso(json.loads((INV / f"{nome}.json").read_text()))

    def test_codigo_nunca_e_executado(self):
        d = json.loads((INV / "json_com_codigo.json").read_text())
        try:
            rec, av = validar_recurso(d)
        except RecursoInvalido:
            return                          # rejeitado tambem e aceitavel
        self.assertTrue(any("desconhecido" in a for a in av))     # campos extras ignorados
        self.assertNotIn("exec", rec)

    def test_svg_inseguros(self):
        for nome in ("svg_com_script", "svg_com_entidade", "svg_href_externo"):
            with self.assertRaises(RecursoInvalido, msg=nome):
                importar_svg((INV / f"{nome}.svg").read_bytes(), nome)

    def test_svg_tv_ok(self):
        rec, av = importar_svg((POC / "tv.svg").read_bytes(), "tv", "objeto", json.loads((POC / "tv.anim.json").read_text()))
        rec, av = validar_recurso(rec)
        self.assertIn("ligar", rec["animacoes"])
        self.assertIn("tv_conteudo", [p["id"] for p in rec["partes"]])


class TestBiblioteca(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_dedupe_versao_aprovacao(self):
        b = Biblioteca(self.dir, aprovacao="manual")
        r1 = b.registrar(dict(OBJ_MIN))
        self.assertEqual((r1.estado, r1.status), ("novo", "pendente"))
        self.assertEqual(b.registrar(dict(OBJ_MIN)).estado, "reutilizado")                 # mesmo conteudo
        outro = dict(OBJ_MIN, id="caixa_clone")
        self.assertEqual(b.registrar(outro).estado, "reutilizado")                          # mesmo desenho, outro id -> reaproveita
        v2 = json.loads(json.dumps(OBJ_MIN)); v2["partes"][0]["formas"][0]["fill"] = "#ff0000"
        self.assertEqual(b.registrar(v2).estado, "nova_versao")
        b.aprovar("caixa1")
        self.assertEqual(b.idx["recursos"]["caixa1"]["status"], "aprovado")
        b.rejeitar("caixa1", "feio")
        b2 = Biblioteca(self.dir)                                                           # persistencia
        self.assertEqual(b2.idx["recursos"]["caixa1"]["status"], "rejeitado")
        with self.assertRaises(RecursoInvalido):
            b2.obter("caixa1")

    def test_bloqueio_de_pendentes(self):
        b = Biblioteca(self.dir, aprovacao="manual", bloquear_pendentes=True)
        b.registrar(dict(OBJ_MIN))
        with self.assertRaises(RecursoInvalido):
            b.rig("caixa1")


class TestCenaTolerante(unittest.TestCase):
    def test_erros_nao_derrubam_o_render(self):
        d = tempfile.mkdtemp()
        try:
            b = Biblioteca(d)
            b.registrar_pasta(POC)
            cena = {"modelo": "generica", "duracao": 3.0,
                    "cenario": {"ref": "savana"},
                    "elementos": [
                        {"id": "ok", "ref": "tigre", "escala": 0.8, "pos": [0.5, 0.8], "linha_do_tempo": [{"t": 0, "anim": "voar"}]},   # animacao inexistente
                        {"id": "fantasma", "ref": "dragao", "pos": [0.2, 0.8]},                                                           # recurso inexistente
                        {"id": "mal", "arquivo": str(INV / "svg_com_script.svg"), "pos": [0.8, 0.8]},                                     # svg inseguro
                        {"id": "def_inline", "def": OBJ_MIN, "pos": [0.65, 0.8], "escala": 1.0}]}                                          # recurso novo por JSON
            est = Estilo(960, 540, biblioteca=b)
            tela = Tela(960, 540, 1)
            est.quadro(tela, 1.0, cena, "")
            self.assertEqual(tela.img.size, (960, 540))
            msgs = " | ".join(b.problemas)
            self.assertIn("voar", msgs)
            self.assertIn("dragao", msgs)
            self.assertIn("mal", msgs)
            self.assertIn("caixa1", b.usos)
        finally:
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
