import io
import json
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import numpy as np

try:                                  # no PC do usuario o soundfile e real; aqui, um substituto minimo (WAV PCM16) se nao houver
    import soundfile as sf
except ImportError:
    import types
    import wave

    def _read(f, dtype="float32", always_2d=False):
        w = wave.open(f if not isinstance(f, (str, Path)) else str(f), "rb")
        n, taxa, canais = w.getnframes(), w.getframerate(), w.getnchannels()
        d = np.frombuffer(w.readframes(n), dtype="<i2").astype("float32") / 32768.0
        w.close()
        d = d.reshape(-1, canais)
        return (d if always_2d or canais > 1 else d[:, 0]), taxa

    def _write(f, data, taxa, format=None):
        d = np.asarray(data, dtype="float32")
        pcm = (np.clip(d, -1, 1) * 32767).astype("<i2")
        w = wave.open(f if not isinstance(f, (str, Path)) else str(f), "wb")
        w.setnchannels(1 if d.ndim == 1 else d.shape[1])
        w.setsampwidth(2)
        w.setframerate(int(taxa))
        w.writeframes(pcm.tobytes())
        w.close()
    sf = types.SimpleNamespace(read=_read, write=_write)
    sys.modules["soundfile"] = sf

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import criar_video as cv  # noqa: E402
import tts_voicebox as T  # noqa: E402


def wav_bytes(seg=1.0, taxa=24000):
    b = io.BytesIO()
    sf.write(b, (0.2 * np.sin(2 * np.pi * 220 * np.arange(int(seg * taxa)) / taxa)).astype("float32"), taxa, format="WAV")
    return b.getvalue()


class Fake(BaseHTTPRequestHandler):
    modo = "direto"        # direto | fila | 202
    estado = {}
    pedidos = []

    def log_message(self, *a):
        pass

    def _enviar(self, code, corpo, ctype="application/json"):
        if not isinstance(corpo, (bytes, bytearray)):
            corpo = json.dumps(corpo).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):
        if self.path == "/health":
            return self._enviar(200, {"status": "healthy"})
        if self.path == "/profiles":
            return self._enviar(200, [{"id": "p1", "name": "Minha Voz"}, {"id": "p2", "name": "Outra"}])
        if self.path == "/history/g1":
            Fake.estado["polls"] = Fake.estado.get("polls", 0) + 1
            return self._enviar(200, {"id": "g1", "status": "processing" if Fake.estado["polls"] < 2 else "completed"})
        if self.path == "/history/g1/export-audio":
            return self._enviar(200, wav_bytes(1.0), "audio/wav")
        self._enviar(404, {"detail": "nao existe"})

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        corpo = json.loads(self.rfile.read(n) or b"{}")
        if self.path != "/generate":
            return self._enviar(404, {})
        Fake.pedidos.append(corpo)
        if Fake.modo == "direto":
            return self._enviar(200, wav_bytes(1.0), "audio/wav")
        if Fake.modo == "fila":
            return self._enviar(200, {"id": "g1", "status": "queued"})
        if Fake.modo == "202":
            Fake.modo = "direto"
            return self._enviar(202, {"status": "downloading"})
        self._enviar(500, {"detail": "boom"})


class _Servidor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(("127.0.0.1", 0), Fake)
        cls.url = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def setUp(self):
        Fake.modo, Fake.estado, Fake.pedidos = "direto", {}, []
        self.canal = {"tts": {"motor": "voicebox", "url": self.url, "perfil": "minha voz", "engine": "qwen", "idioma": "pt", "intervalo_s": 0.05}}


class ClienteTests(_Servidor):
    def test_audio_direto_e_corpo_do_pedido(self):
        dados, taxa = T.narrar("Ola mundo?", self.canal)
        self.assertEqual(taxa, 24000)
        self.assertAlmostEqual(len(dados) / taxa, 1.0, places=1)
        self.assertEqual(Fake.pedidos[0], {"text": "Ola mundo?", "profile_id": "p1", "language": "pt", "engine": "qwen"})

    def test_fila_assincrona_consulta_historico(self):
        Fake.modo = "fila"
        dados, taxa = T.narrar("Texto", self.canal)
        self.assertGreater(len(dados), 1000)
        self.assertGreaterEqual(Fake.estado["polls"], 2)

    def test_http_202_modelo_baixando_espera_e_repete(self):
        Fake.modo = "202"
        self.canal["tts"]["espera_modelo_s"] = 60
        import time
        orig = time.sleep
        time.sleep = lambda s: None        # nao espera de verdade no teste
        try:
            dados, _ = T.narrar("Texto", self.canal)
        finally:
            time.sleep = orig
        self.assertEqual(len(Fake.pedidos), 2)

    def test_perfil_inexistente_lista_os_existentes(self):
        self.canal["tts"]["perfil"] = "nao existe"
        with self.assertRaises(T.VoiceboxErro) as e:
            T.narrar("x", self.canal)
        self.assertIn("Minha Voz", str(e.exception))

    def test_erro_http_vira_voiceboxerro(self):
        Fake.modo = "erro"
        with self.assertRaises(T.VoiceboxErro):
            T.narrar("x", self.canal)

    def test_servidor_fechado(self):
        canal = {"tts": {"motor": "voicebox", "url": "http://127.0.0.1:1"}}
        with self.assertRaises(T.VoiceboxErro):
            T.narrar("x", canal)

    def test_velocidade_acelera_sem_mudar_o_tom(self):
        self.canal["tts"]["velocidade"] = 1.25
        dados, taxa = T.narrar("x", self.canal)
        self.assertAlmostEqual(len(dados) / taxa, 1.0 / 1.25, delta=0.06)

    def test_instruct_so_para_perguntas(self):
        cfg = {"instruct": "tom calmo", "instruct_pergunta": "tom de pergunta, curioso"}
        self.assertEqual(T.instruct_para("Isso e possivel?", cfg), "tom de pergunta, curioso")
        self.assertEqual(T.instruct_para("Isso e possivel.", cfg), "tom calmo")


class PronunciaTests(unittest.TestCase):
    class Dic:
        silabas = {"médico": "mé-di-co", "coração": "co-ra-ção", "você": "vo-cê", "difícil": "di-fí-cil"}

        def inserted(self, palavra, hyphen="-"):
            return self.silabas.get(palavra, palavra)

    def setUp(self):
        import pronuncia_pt
        self.P = pronuncia_pt
        self.P.definir_dicionario(self.Dic())

    def tearDown(self):
        self.P.definir_dicionario(None)

    def test_hifeniza_proparoxitona_e_preserva_oxitonas_e_pontuacao(self):
        self.assertEqual(self.P.hifenizar_proparoxitonas("O médico, de coração, disse: você!"), "O mé-di-co, de coração, disse: você!")

    def test_sem_pyphen_nao_altera_o_texto(self):
        self.P.definir_dicionario(None)
        self.assertEqual(self.P.hifenizar_proparoxitonas("O médico"), "O médico")

    def test_canal_pode_desligar(self):
        self.assertEqual(self.P.preparar_para_voz("O médico", {"tts": {"hifenizar_proparoxitonas": False}}), "O médico")
        self.assertEqual(self.P.preparar_para_voz("O médico", {}), "O mé-di-co")


class GerarVozTests(_Servidor):
    def _roteiro(self):
        return {"cenas": [{"narracao": "Primeira cena."}, {"narracao": "Segunda cena?"}]}

    class KokoroFalso:
        chamadas = 0

        def create(self, texto, voice=None, speed=1.0, lang=None):
            GerarVozTests.KokoroFalso.chamadas += 1
            return np.zeros(24000, dtype="float32"), 24000

    def _canal(self, **tts):
        c = dict(self.canal)
        c["tts"] = dict(c["tts"], **tts)
        c.update({"velocidade": 1.0, "velocidade_gancho": 1.0, "voz": "pf_dora", "idioma_tts": "pt-br"})
        return c

    def test_usa_voicebox_nas_cenas(self):
        self.KokoroFalso.chamadas = 0
        with tempfile.TemporaryDirectory() as tmp:
            cv.carregar_kokoro = lambda: self.KokoroFalso()
            narr, dur = cv.gerar_voz(self._roteiro(), Path(tmp), self._canal(), False)
            self.assertEqual(len(dur), 2)
        self.assertEqual(self.KokoroFalso.chamadas, 0)
        self.assertEqual(len(Fake.pedidos), 2)

    def test_primeira_cena_falha_usa_kokoro_no_video_todo(self):
        self.KokoroFalso.chamadas = 0
        Fake.modo = "erro"
        with tempfile.TemporaryDirectory() as tmp:
            cv.carregar_kokoro = lambda: self.KokoroFalso()
            cv.gerar_voz(self._roteiro(), Path(tmp), self._canal(), False)
        self.assertEqual(self.KokoroFalso.chamadas, 2)
        self.assertEqual(len(Fake.pedidos), 1)         # nao insiste no Voicebox a cada cena

    def test_falha_no_meio_nao_mistura_vozes(self):
        orig = Fake.do_POST
        contagem = {"n": 0}

        def post(self_):
            contagem["n"] += 1
            if contagem["n"] == 2:
                Fake.modo = "erro"
            return orig(self_)
        Fake.do_POST = post
        try:
            with tempfile.TemporaryDirectory() as tmp:
                cv.carregar_kokoro = lambda: self.KokoroFalso()
                with self.assertRaises(RuntimeError) as e:
                    cv.gerar_voz(self._roteiro(), Path(tmp), self._canal(), False)
                self.assertIn("rode de novo", str(e.exception))
                self.assertTrue((Path(tmp) / "audio" / "01.wav").exists())     # cena 1 preservada para retomar
        finally:
            Fake.do_POST = orig

    def test_sem_bloco_tts_continua_kokoro(self):
        self.KokoroFalso.chamadas = 0
        canal = {"velocidade": 1.0, "velocidade_gancho": 1.0, "voz": "pf_dora", "idioma_tts": "pt-br"}
        with tempfile.TemporaryDirectory() as tmp:
            cv.carregar_kokoro = lambda: self.KokoroFalso()
            cv.gerar_voz(self._roteiro(), Path(tmp), canal, False)
        self.assertEqual(self.KokoroFalso.chamadas, 2)
        self.assertEqual(Fake.pedidos, [])


if __name__ == "__main__":
    unittest.main()
