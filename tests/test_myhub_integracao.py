import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "estudio"))

import criar_video as cv  # noqa: E402
import diretor_m1  # noqa: E402
import myhub_llm  # noqa: E402
from estudio.cenas2d.recursos.biblioteca import Biblioteca  # noqa: E402


def svg_cenario_ok(semente=1):
    """cenario com varias camadas/cores (nao 'liso')"""
    cores = ["#0b1030", "#1c2a5a", "#38507a", "#6a7fa8", "#20304a", "#101828", "#3a2a3a", "#5a4a5a"]
    g = "".join(f'<rect x="0" y="{i * 135}" width="1920" height="140" fill="{cores[(i + semente) % 8]}"/>' for i in range(8))
    pred = "".join(f'<rect x="{i * 95}" y="{500 - (i * 37 + semente * 11) % 260}" width="80" height="{300 + (i * 37) % 260}" fill="{cores[(i + 3 + semente) % 8]}"/>' for i in range(20))
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 1080"><g id="ceu">{g}</g><g id="predios">{pred}</g></svg>'


def svg_ok(n=30, cor="#c44"):
    formas = "".join(f'<rect x="{10 + 6 * i}" y="{20 + (i % 5) * 8}" width="14" height="30" rx="3" fill="{cor if i % 2 else "#334"}"/>' for i in range(n))
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300"><g id="corpo">{formas}</g></svg>'


class FakeBridge(BaseHTTPRequestHandler):
    jobs = []
    respostas = []         # fila de callables (job) -> (texto, [(arquivo, conteudo)])
    base = None

    def log_message(self, *a):
        pass

    def _json(self, code, obj):
        corpo = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):
        self._json(200, {"ok": True}) if self.path == "/health" else self._json(404, {})

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        job = json.loads(self.rfile.read(n))
        FakeBridge.jobs.append(job)
        fn = FakeBridge.respostas.pop(0) if FakeBridge.respostas else (lambda j: ("", []))
        texto, arquivos = fn(job)
        d = Path(FakeBridge.base) / "results" / job["id"]
        (d / "artifacts").mkdir(parents=True, exist_ok=True)
        arts = []
        for nome, conteudo in arquivos:
            (d / "artifacts" / nome).write_text(conteudo, encoding="utf-8")
            arts.append({"path": f"artifacts/{nome}", "filename": nome, "valid": True, "source": "download"})
        (d / "response.txt").write_text(texto, encoding="utf-8")
        (d / "response.json").write_text(json.dumps({"success": True, "artifacts": arts}), encoding="utf-8")
        self._json(200, {"ok": True, "result_dir": str(d)})


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(("127.0.0.1", 0), FakeBridge)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.bridge = Path(self.tmp) / "myhub-bridge"
        self.bridge.mkdir()
        (self.bridge / "main.py").write_text("# stub", encoding="utf-8")
        (self.bridge / "config.json").write_text("{}", encoding="utf-8")
        FakeBridge.jobs, FakeBridge.respostas, FakeBridge.base = [], [], str(self.bridge)
        shutil.copytree(ROOT / "biblioteca_m1", Path(self.tmp) / "bib")
        self.bib = Biblioteca(Path(self.tmp) / "bib", bloquear_pendentes=True)
        self.cfg = {"myhub_bridge_dir": str(self.bridge), "myhub_bridge_port": self.port, "m1_myhub_timeout_seconds": 180}
        self.log = []

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def roteiro(self, *falas):
        return {"titulo": "Teste", "cenas": [{"narracao": f, "imagem": "", "busca_stock": ""} for f in falas]}


class AdaptadorTests(_Base):
    def test_pasta_do_bridge_ordem_de_resolucao(self):
        os.environ.pop("MYHUB_BRIDGE_DIR", None)
        self.assertEqual(myhub_llm._bridge_root({"myhub_bridge_dir": str(self.bridge)}, ROOT), self.bridge.resolve())
        os.environ["MYHUB_BRIDGE_DIR"] = str(self.bridge)
        try:
            self.assertEqual(myhub_llm._bridge_root({"myhub_bridge_dir": "X:/outro"}, ROOT), self.bridge.resolve())     # variavel de ambiente vence
        finally:
            os.environ.pop("MYHUB_BRIDGE_DIR", None)
        self.assertTrue(myhub_llm.bridge_disponivel(self.cfg, ROOT))
        self.assertFalse(myhub_llm.bridge_disponivel({"myhub_bridge_dir": str(Path(self.tmp) / "nao_existe")}, ROOT))

    def test_json_e_svg_pelo_bridge(self):
        FakeBridge.respostas = [lambda j: ('{"cenas": []}', []), lambda j: ("", [("x.svg", svg_ok())])]
        llm = myhub_llm.criar_llm_myhub(self.cfg, ROOT, self.log.append, chat_scope="canal_projeto")
        self.assertEqual(json.loads(llm("direcao", True)), {"cenas": []})
        self.assertIn("<svg", llm("DESENHE: Tanque\ncorpo", False))
        self.assertEqual(FakeBridge.jobs[0]["purpose"], "direcao_arte")
        self.assertEqual(FakeBridge.jobs[1]["purpose"], "recursos_svg")
        self.assertIn("canal_projeto", FakeBridge.jobs[0]["chat_key"])


class DiretorMyHubTests(_Base):
    def direcao(self, n=1, objetos=("tanque_a", "mapa_b")):
        return json.dumps({"tema": "tensao_quente", "cenas": [
            {"n": i + 1, "cenario": {"novo": {"id": "campo", "tipo": "cenario", "nome": "Campo", "tags": ["campo"], "descricao": "campo de batalha com ruinas e colinas"}},
             "clima": "alerta", "hero": {"novo": {"id": objetos[0], "tipo": "objeto", "nome": "Tanque", "tags": ["tanque"], "descricao": "tanque de guerra"}},
             "apoio": [{"novo": {"id": objetos[1], "tipo": "objeto", "nome": "Mapa", "tags": ["mapa"], "descricao": "mapa tatico"}}],
             "personagens": [], "chip": "DIA 1 · FRONTEIRA", "rotulos": [{"texto": "72 HORAS", "sub": "teste"}]} for i in range(n)]})

    def lote_resposta(self, job):
        ids = [l.split("ARQUIVO")[1].split(":")[1].split(".svg")[0].strip() for l in job["prompt"].splitlines() if l.startswith("ARQUIVO ")]
        return "", [(f"{i}.svg", svg_cenario_ok(len(i)) if i.startswith("campo") else svg_ok(40 + len(i), "#" + ("%06x" % (hash(i) % 0xFFFFFF)))) for i in ids]

    def test_direcao_e_recursos_em_lote_pelo_myhub(self):
        FakeBridge.respostas = [lambda j: (self.direcao(), []), self.lote_resposta, self.lote_resposta]
        cenas = diretor_m1.dirigir(self.roteiro("O tanque avanca pelo mapa."), [6.0], self.bib, modo="myhub", cfg=self.cfg, cv=cv,
                                   log=self.log.append, categoria="curiosidades", canal={}, chat_scope="c_p")
        self.assertTrue(any("direcao de arte: MyHub Bridge" in l for l in self.log), self.log)
        self.assertEqual(cenas[0]["tema"]["id"], "tensao_quente")
        origens = {k: v.get("origem") for k, v in self.bib.idx["recursos"].items() if k in ("tanque_a", "mapa_b") or k.startswith("campo")}
        self.assertEqual(origens["tanque_a"], "ia")
        self.assertEqual(origens["mapa_b"], "ia")
        lotes = [j for j in FakeBridge.jobs if j["purpose"] == "recursos_svg_lote"]
        self.assertEqual(len(lotes), 2)             # cenario + (tanque, mapa): 3 recursos em 2 mensagens, nao 3
        self.assertTrue(any("ARQUIVO 2" in j["prompt"] for j in lotes))
        self.assertNotIn("api_key", json.dumps(FakeBridge.jobs).lower())

    def test_lote_sem_svg_usa_reserva_sem_repetir_chamadas(self):
        FakeBridge.respostas = [lambda j: (self.direcao(), []), lambda j: ("nao consegui", []), lambda j: ("nao consegui", [])]
        diretor_m1.dirigir(self.roteiro("O tanque."), [6.0], self.bib, modo="myhub", cfg=self.cfg, cv=cv, log=self.log.append,
                           categoria="curiosidades", canal={})
        self.assertEqual(self.bib.idx["recursos"]["tanque_a"]["origem"], "procedural")
        self.assertEqual(len([j for j in FakeBridge.jobs if j["purpose"] != "direcao_arte"]), 2)        # 2 lotes, nenhuma chamada individual extra

    def test_json_com_virgula_faltando_e_recuperado_localmente(self):
        quebrado = self.direcao().replace('"clima": "alerta", "hero"', '"clima": "alerta" "hero"')
        FakeBridge.respostas = [lambda j: (quebrado, [])] + [self.lote_resposta] * 3
        diretor_m1.dirigir(self.roteiro("O tanque."), [6.0], self.bib, modo="myhub", cfg=self.cfg, cv=cv, log=self.log.append, categoria="x", canal={})
        self.assertEqual(len([j for j in FakeBridge.jobs if j["purpose"] == "direcao_arte"]), 1)       # nao precisou pedir correcao

    def test_numero_de_cenas_errado_pede_uma_correcao_e_depois_cai_no_local(self):
        FakeBridge.respostas = [lambda j: (self.direcao(n=1), []), lambda j: (self.direcao(n=1), [])]
        cenas = diretor_m1.dirigir(self.roteiro("Cena um.", "Cena dois."), [4.0, 4.0], self.bib, modo="myhub", cfg=self.cfg, cv=cv,
                                   log=self.log.append, categoria="curiosidades", canal={})
        self.assertEqual(len(cenas), 2)                                                                  # video sai mesmo assim (diretor local)
        self.assertEqual(len([j for j in FakeBridge.jobs if j["purpose"] == "direcao_arte"]), 2)       # original + UMA correcao
        self.assertTrue(any("diretor local" in l for l in self.log))

    def test_auto_usa_myhub_quando_instalado_e_local_quando_nao(self):
        FakeBridge.respostas = [lambda j: (self.direcao(), [])] + [self.lote_resposta] * 3
        diretor_m1.dirigir(self.roteiro("Fala."), [4.0], self.bib, modo="auto", cfg=self.cfg, cv=cv, log=self.log.append, categoria="x", canal={})
        self.assertTrue(any("MyHub Bridge" in l for l in self.log))
        FakeBridge.jobs.clear()
        log2 = []
        diretor_m1.dirigir(self.roteiro("Fala."), [4.0], self.bib, modo="auto", cfg={"myhub_bridge_dir": str(Path(self.tmp) / "x")}, cv=cv,
                           log=log2.append, categoria="x", canal={})
        self.assertEqual(FakeBridge.jobs, [])
        self.assertTrue(any("local" in l for l in log2))


class ProvedoresRoteiroTests(_Base):
    def test_auto_resolve_pelo_bridge_instalado(self):
        old = cv.RAIZ
        try:
            self.assertEqual(cv._provedor_texto_etapa(dict(self.cfg, provedor_geracao_roteiro="auto"), "roteiro"), "myhub")
            self.assertEqual(cv._provedor_texto_etapa({"myhub_bridge_dir": str(Path(self.tmp) / "x"), "provedor_geracao_roteiro": "auto"}, "roteiro"), "gemini")
            self.assertEqual(cv._provedor_texto_etapa({"provedor_geracao_roteiro": "gemini"}, "roteiro"), "gemini")
            with self.assertRaises(ValueError):
                cv._provedor_texto_etapa({"provedor_geracao_roteiro": "xyz"}, "roteiro")
        finally:
            cv.RAIZ = old

    def test_etapas_de_roteiro_usam_chats_proprios(self):
        FakeBridge.respostas = [lambda j: ('{"ok": 1}', [])] * 3
        llm = myhub_llm.criar_llm_myhub(self.cfg, ROOT, self.log.append, purpose="checagem", expected_outputs=["json"], chat_scope="c_p")
        llm("p", True)
        self.assertEqual(FakeBridge.jobs[0]["purpose"], "roteiro_checagem")
        self.assertIn("roteiro_checagem", FakeBridge.jobs[0]["chat_key"])


class AdaptadorMotorTests(_Base):
    def test_motor_usa_o_provedor_salvo_pela_interface(self):
        from motores.adapters.character_2_5d import Character25DEngine
        (Path(self.tmp) / "config.json").write_text(json.dumps({"m1_diretor_padrao": "myhub"}), encoding="utf-8")
        cmd = Character25DEngine().build_command({"canal": "c", "tema": "T", "formatos": "9x16"}, Path(self.tmp), "python")
        self.assertEqual(cmd[cmd.index("--diretor") + 1], "myhub")
        cmd = Character25DEngine().build_command({"canal": "c", "tema": "T", "formatos": "9x16", "diretor": "local"}, Path(self.tmp), "python")
        self.assertEqual(cmd[cmd.index("--diretor") + 1], "local")


if __name__ == "__main__":
    unittest.main()
