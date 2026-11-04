import json
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

from job_store import JobStore
import engine_registry
from engine_registry import get_adapter
from editorial_rules import closing_question, ensure_closing_question
import criar_video as cv
import motores.broadcast_news as broadcast_news
import app


class JobStoreTests(unittest.TestCase):
    def test_create_reload_and_mark_interrupted(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = JobStore(Path(tmp) / "jobs.sqlite3")
            job = {
                "canal": "exemplo", "tema": "Teste", "motor": "classico",
                "status": "rodando", "progresso": 42, "log": ["linha 1"],
            }
            job["id"] = store.create(job)
            loaded = store.list()
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0]["tema"], "Teste")
            self.assertEqual(store.mark_interrupted(), [job["id"]])
            restored = store.get(job["id"])
            self.assertEqual(restored["status"], "interrompido")
            self.assertEqual(restored["progresso"], 42)
            self.assertIn("linha 1", restored["log"])

    def test_pending_job_is_not_marked_interrupted(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = JobStore(Path(tmp) / "jobs.sqlite3")
            job = {"canal": "exemplo", "tema": "Pendente", "status": "pendente", "log": []}
            job["id"] = store.create(job)
            self.assertEqual(store.mark_interrupted(), [])
            self.assertEqual(store.get(job["id"])["status"], "pendente")


class EngineCatalogTests(unittest.TestCase):
    def test_classic_and_broadcast_news_engines_are_executable(self):
        self.assertTrue(engine_registry.is_engine_executable("classico"))
        self.assertTrue(engine_registry.is_engine_executable("broadcast_news"))
        for engine_id in ("isometric", "blueprint", "stickman", "character_2_5d"):
            self.assertFalse(engine_registry.is_engine_executable(engine_id), engine_id)

    def test_broadcast_news_adapter_does_not_require_google_search(self):
        adapter = get_adapter("broadcast_news")
        command = adapter.build_command({
            "canal": "exemplo", "tema": "O que e Split Payment?", "formatos": "16x9",
            "categoria": "economia", "duracao": 420, "grounding": False, "simular": False,
            "entrega_format": "16x9"
        }, Path("/app"), "python")
        self.assertIn("broadcast_news.py", command[2])
        self.assertIn("--categoria", command)
        self.assertIn("--entrega-format", command)
        self.assertNotIn("--grounding", command)

    def test_broadcast_prompt_explicitly_uses_consolidated_facts_without_search(self):
        prompt = broadcast_news.make_research_prompt(
            {"nome": "Canal", "publico": "geral", "tom": "neutro"},
            "O que e Split Payment?", 300, "economia"
        )
        self.assertIn("FATOS E PRECISAO (SEM PESQUISA WEB)", prompt)
        self.assertIn("Nao use Google Search", prompt)
        self.assertIn("conferencia manual", prompt)

    def test_categories_have_recommended_engines(self):
        categories = engine_registry.list_categories()
        self.assertTrue(categories)
        self.assertTrue(all(x.get("id") and x.get("recommended_engines") for x in categories))

    def test_classic_adapter_builds_existing_pipeline_command(self):
        adapter = get_adapter("classico")
        command = adapter.build_command({
            "canal": "exemplo", "tema": "Teste", "formatos": "16x9",
            "duracao": 60, "revisar": True, "simular": False
        }, Path("/app"), "python")
        self.assertIn("criar_video.py", command[2])
        self.assertIn("--revisar", command)

    def test_classic_adapter_passes_independent_vertical_duration_and_format(self):
        adapter = get_adapter("classico")
        command = adapter.build_command({
            "canal": "exemplo", "tema": "Teste vertical", "formatos": "9x16",
            "categoria": "what_if", "duracao": 90, "entrega_format": "9x16"
        }, Path("/app"), "python")
        self.assertIn("--duracao", command)
        self.assertEqual(command[command.index("--duracao") + 1], "90")
        self.assertEqual(command[command.index("--entrega-format") + 1], "9x16")

    def test_classic_adapter_can_target_existing_project_for_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "projetos" / "exemplo" / "2026-11-03_teste"
            project.mkdir(parents=True)
            adapter = get_adapter("classico")
            command = adapter.build_command({
                "canal": "exemplo", "tema": "Teste", "formatos": "16x9",
                "duracao": 60, "pasta": "exemplo/2026-11-03_teste"
            }, root, "python")
            self.assertIn("--projeto", command)
            self.assertIn(str(project), command)


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def get_json(self, path):
        with urlopen(self.base + path, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))

    def get_text(self, path):
        with urlopen(self.base + path, timeout=5) as response:
            return response.read().decode("utf-8")

    def post_json(self, path, payload):
        req = Request(self.base + path, data=json.dumps(payload).encode("utf-8"),
                      headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urlopen(req, timeout=5) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            if hasattr(exc, "code"):
                return exc.code, json.loads(exc.read().decode("utf-8"))
            raise

    def test_health_does_not_expose_credentials(self):
        health = self.get_json("/api/saude")
        self.assertTrue(health["ok"])
        serialized = json.dumps(health)
        self.assertNotIn("api_key_value", serialized)
        self.assertIn("database_exists", health)

    def test_motor_catalog_endpoint(self):
        result = self.get_json("/api/motores")
        ids = {x["id"] for x in result["motores"]}
        self.assertIn("classico", ids)
        self.assertIn("broadcast_news", ids)

    def test_thumbnail_template_endpoint(self):
        result = self.get_json("/api/thumbnails")
        self.assertEqual(result["templates"][0]["id"], "thumbnail_colorful_v1")
        self.assertEqual(result["templates"][0]["formats"]["16:9"]["width"], 1280)

    def test_ui_served_by_root_contains_motor_and_category_controls(self):
        html = self.get_text("/")
        self.assertIn('id="categoria"', html)
        self.assertIn('id="motores-grid"', html)
        self.assertIn('id="aba-motores"', html)
        self.assertIn('id="aba-projetos"', html)
        self.assertNotIn('id="grounding-row"', html)
        self.assertNotIn('Pesquisa Google com fontes', html)
        self.assertIn('id="duracao-16x9"', html)
        self.assertIn('id="duracao-9x16"', html)
        self.assertEqual(html.count('id="categoria"'), 1)
        self.assertIn('Ver diretrizes editoriais desta categoria', html)
        self.assertIn("carregarCatalogos()", html)

    def test_idea_suggestions_receive_selected_category(self):
        with patch.object(app.cv, "sugerir_ideias", return_value=["O que e Split Payment?"]) as mock:
            status, payload = self.post_json("/api/ideias", {
                "canal": "exemplo", "n": 1, "categoria": "economia", "motor": "broadcast_news"
            })
        self.assertEqual(status, 200)
        self.assertEqual(payload["ideias"], ["O que e Split Payment?"])
        self.assertEqual(mock.call_args.kwargs["categoria"]["id"], "economia")
        self.assertEqual(mock.call_args.kwargs["motor"], "broadcast_news")

    def test_create_rejects_long_duration_outside_configured_range(self):
        status, payload = self.post_json("/api/criar", {
            "canal": "exemplo", "temas": ["Teste de duracao"], "motor": "classico",
            "categoria": "curiosidades", "formatos": "16x9", "duracao_longa": 720
        })
        self.assertEqual(status, 400)
        self.assertIn("5 e 10 minutos", payload["erro"])

    def test_categories_expose_complete_editorial_profiles(self):
        data = self.get_json("/api/categorias")
        self.assertTrue(data["categorias"])
        for category in data["categorias"]:
            profile = category.get("editorial_profile", {})
            for field in ("objective", "tone", "structure", "fact_policy", "avoid", "visual_guidance", "closing_question"):
                self.assertIn(field, profile, (category["id"], field))

    def test_create_draft_for_planned_engine(self):
        project = {
            "title": "Teste Isometric", "channel": "exemplo", "category": "como_funciona",
            "engine_id": "isometric",
            "deliverables": {
                "youtube_long": {"aspect_ratio": "16:9", "target_duration_seconds": 300, "scenes": []},
                "short_vertical": {"aspect_ratio": "9:16", "target_duration_seconds": 90, "scenes": []}
            }
        }
        status, created = self.post_json("/api/projetos", {"projeto": project})
        self.assertEqual(status, 201)
        saved = self.get_json("/api/projeto?id=" + created["id"])
        self.assertEqual(saved["engine_id"], "isometric")
        self.assertEqual(saved["status"], "draft")

    def test_planned_engine_cannot_enter_legacy_queue(self):
        status, payload = self.post_json("/api/criar", {
            "canal": "exemplo", "temas": ["Teste"], "motor": "isometric", "categoria": "como_funciona"
        })
        self.assertEqual(status, 409)
        self.assertIn("ainda esta em preparacao", payload["erro"])

    def test_broadcast_news_can_enter_queue_without_google_search(self):
        status, payload = self.post_json("/api/criar", {
            "canal": "exemplo", "temas": ["O que e Split Payment?"],
            "motor": "broadcast_news", "categoria": "economia", "formatos": "16x9",
            "duracao_longa": 420
        })
        self.assertEqual(status, 200)
        self.assertEqual(payload["versoes_criadas"], 1)
        created = next(j for j in app.FILA if j["id"] == payload["criados"][0])
        self.assertEqual(created["motor"], "broadcast_news")
        self.assertEqual(created["duracao"], 420)
        self.assertEqual(created["entrega_format"], "16x9")
        self.assertNotIn("grounding", created)
        app.FILA.remove(created)
        app.STORE.remove(created["id"])

    def test_both_formats_create_independent_jobs_with_different_durations(self):
        status, payload = self.post_json("/api/criar", {
            "canal": "exemplo", "temas": ["Teste de entregas independentes"],
            "motor": "classico", "categoria": "curiosidades", "formatos": "16x9,9x16",
            "duracao_longa": 420, "duracao_curta": 90
        })
        self.assertEqual(status, 200)
        self.assertEqual(payload["versoes_criadas"], 2)
        created = [j for j in app.FILA if j["id"] in payload["criados"]]
        self.assertEqual({j["entrega_format"] for j in created}, {"16x9", "9x16"})
        durations = {j["entrega_format"]: j["duracao"] for j in created}
        self.assertEqual(durations, {"16x9": 420, "9x16": 90})
        for job in created:
            app.FILA.remove(job)
            app.STORE.remove(job["id"])

    def test_channel_identity_defaults_and_display_name(self):
        channel = cv.carregar_canal("exemplo")
        identity = channel["identidade"]
        self.assertEqual(identity["logo_arquivo"], "identidade/logo.png")
        self.assertIn("marca_dagua", identity)
        self.assertIn("intro", identity)
        self.assertTrue(identity["thumbnail"]["incluir_logo"])
        self.assertEqual(identity["nome_exibicao"], channel["nome"])

    def test_comment_question_is_not_duplicated_when_already_contextual(self):
        script = {"cenas": [{"narracao": "E você, o que faria? Conta nos comentários."}]}
        result = ensure_closing_question(script, "what_if", "E se isso acontecesse?")
        self.assertEqual(result["cenas"][-1]["narracao"], script["cenas"][-1]["narracao"])

    def test_ai_specific_final_question_is_preserved_in_metadata(self):
        script = {"cenas": [{"narracao": "E você, pagaria por esse serviço? Conta nos comentários o motivo."}]}
        result = ensure_closing_question(script, "economia", "Split Payment")
        self.assertEqual(result["pergunta_final"], "E você, pagaria por esse serviço?")
        self.assertEqual(result["cenas"][-1]["narracao"], script["cenas"][-1]["narracao"])

    def test_comment_question_is_appended_when_last_scene_has_no_comment_invite(self):
        script = {"cenas": [{"narracao": "E foi assim que tudo terminou."}]}
        result = ensure_closing_question(script, "what_if", "E se você ficasse mais forte?")
        final_text = result["cenas"][-1]["narracao"]
        self.assertIn("?", final_text)
        self.assertIn("comentários", final_text.lower())
        self.assertIn("pergunta_final", result)

    def test_broadcast_script_can_be_saved_from_review_dialog(self):
        project_dir = app.PROJETOS / "_test_broadcast_review"
        project_dir.mkdir(parents=True, exist_ok=True)
        try:
            (project_dir / "roteiro.json").write_text(json.dumps({"titulo": "Titulo", "cenas": []}), encoding="utf-8")
            roteiro = {
                "titulo": "Split Payment: como funciona",
                "descricao": "Explicacao jornalistica.",
                "tags": ["economia"],
                "fontes": [{"id": "S1", "title": "Fonte oficial", "url": "https://example.com"}],
                "cenas": [
                    {"narracao": f"Cena {i}.", "visual": {"type": "bullets", "items": [{"title": "Fato", "body": "Contexto"}]}}
                    for i in range(1, 5)
                ],
            }
            status, payload = self.post_json("/api/roteiro", {"pasta": "_test_broadcast_review", "roteiro": roteiro})
            self.assertEqual(status, 200, payload)
            saved = json.loads((project_dir / "roteiro.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["cenas"][0]["visual"]["type"], "bullets")
            self.assertEqual(saved["titulo"], roteiro["titulo"])
        finally:
            import shutil
            shutil.rmtree(project_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
