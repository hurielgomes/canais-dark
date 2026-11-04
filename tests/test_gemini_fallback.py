import sys
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import criar_video as cv

class FakeModels:
    def __init__(self, behavior):
        self.behavior = behavior
        self.calls = []
    def generate_content(self, model, contents, config):
        self.calls.append(model)
        result = self.behavior(model, len([x for x in self.calls if x == model]))
        if isinstance(result, Exception):
            raise result
        return result

class TestGeminiFallback(unittest.TestCase):
    def setUp(self):
        self.original_sleep = cv.time.sleep
        cv.time.sleep = lambda _: None
    def tearDown(self):
        cv.time.sleep = self.original_sleep

    def test_503_switches_to_first_fallback(self):
        def behavior(model, attempt):
            if model == 'gemini-3.8-flash':
                return RuntimeError('503 UNAVAILABLE high demand')
            return SimpleNamespace(text='ok')
        models = FakeModels(behavior)
        response = cv.gerar_conteudo_texto_com_fallback(
            SimpleNamespace(models=models),
            {'modelo_texto':'gemini-3.8-flash','modelos_texto_fallback':['gemini-3.6-flash']},
            'prompt','json','test'
        )
        self.assertEqual(response.text, 'ok')
        self.assertEqual(models.calls.count('gemini-3.8-flash'), 3)
        self.assertEqual(models.calls[-1], 'gemini-3.6-flash')

    def test_auth_error_does_not_fallback(self):
        def behavior(model, attempt):
            return RuntimeError('403 PERMISSION_DENIED')
        models = FakeModels(behavior)
        with self.assertRaisesRegex(RuntimeError, '403'):
            cv.gerar_conteudo_texto_com_fallback(
                SimpleNamespace(models=models),
                {'modelo_texto':'gemini-3.8-flash','modelos_texto_fallback':['gemini-3.6-flash']},
                'prompt','json','test'
            )
        self.assertEqual(models.calls, ['gemini-3.8-flash'])

if __name__ == '__main__':
    unittest.main()
