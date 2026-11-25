from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import myhub_llm

SVG = '<svg xmlns="http://www.w3.org/2000/svg" id="personagem_teste" viewBox="0 0 20 20"><circle cx="10" cy="10" r="8"/></svg>'
REFUSAL = 'Não consigo anexar arquivos SVG diretamente por este chat. Para gerar as ilustrações, acesse Imagens.'

class MyHubV15CompatibilityTests(unittest.TestCase):
    def _bridge(self, root: Path) -> Path:
        bridge = root / 'myhub-bridge'
        bridge.mkdir()
        (bridge / 'main.py').write_text('# bridge entry', encoding='utf-8')
        (bridge / 'config.json').write_text('{}', encoding='utf-8')
        return bridge

    def test_bridge_disponivel_signature_used_by_canais_dark(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bridge = self._bridge(root)
            self.assertTrue(myhub_llm.bridge_disponivel({'myhub_bridge_dir': str(bridge)}, root, lambda _: None))

    def test_bridge_disponivel_does_not_start_service_for_status_or_auto_selection(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bridge = self._bridge(root)
            with patch.object(myhub_llm._BridgeClient, 'ensure_running') as start:
                ok = myhub_llm.bridge_disponivel({'myhub_bridge_dir': str(bridge)}, root, lambda _: None)
            self.assertTrue(ok)
            start.assert_not_called()

    def test_bridge_disponivel_false_if_required_files_missing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertFalse(myhub_llm.bridge_disponivel({'myhub_bridge_dir': str(root / 'missing')}, root, lambda _: None))

    def test_optional_start_mode_checks_health_and_starts_once(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bridge = self._bridge(root)
            attempts = {'n': 0}
            class Resp:
                def __enter__(self): return self
                def __exit__(self, *_): return False
                def read(self): return b'{"ok":true}'
            def fake_urlopen(*args, **kwargs):
                attempts['n'] += 1
                if attempts['n'] == 1:
                    raise OSError('not started')
                return Resp()
            with patch.object(myhub_llm._BridgeClient, 'ensure_running') as start, patch('myhub_llm.urllib.request.urlopen', side_effect=fake_urlopen):
                ok = myhub_llm.bridge_disponivel({'myhub_bridge_dir': str(bridge)}, root, lambda _: None, iniciar=True)
            self.assertTrue(ok)
            start.assert_called_once()

    def test_loose_animation_json_after_svg_is_extracted(self):
        side = {'partes': [{'id':'cabeca','pivo':[4,5]}], 'animacoes': {'parado': {'duracao': 1.0}}}
        raw = SVG + '\n' + json.dumps(side, ensure_ascii=False, indent=2)
        got = myhub_llm._extract_loose_svg_sidecar(raw)
        self.assertEqual(json.loads(got), side)

    def test_explicit_refusal_but_not_temporary_toast(self):
        self.assertTrue(myhub_llm._is_svg_generation_refusal(REFUSAL, {}, []))
        self.assertFalse(myhub_llm._is_svg_generation_refusal('Ocorreu um erro na pesquisa, tente perguntar novamente.', {}, []))
        self.assertFalse(myhub_llm._is_svg_generation_refusal(SVG + '\n' + REFUSAL, {}, []))

    def test_retry_sequence_same_chat_then_new_chat(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); bridge = self._bridge(root); calls=[]
            def fake_submit(_client, job):
                calls.append(dict(job)); folder=root/f'result_{len(calls)}'; folder.mkdir()
                (folder/'response.txt').write_text(REFUSAL if len(calls)<3 else SVG, encoding='utf-8')
                (folder/'response.json').write_text(json.dumps({'success': True, 'artifacts': []}), encoding='utf-8')
                return folder
            logs=[]
            with patch.object(myhub_llm._BridgeClient, 'ensure_running', lambda self: None), patch.object(myhub_llm._BridgeClient, 'submit', fake_submit):
                llm=myhub_llm.criar_llm_myhub({'myhub_bridge_dir':str(bridge),'m1_myhub_timeout_seconds':300}, root, logs.append, chat_key='original')
                result=llm('DESENHE: personagem_teste', False)
            self.assertEqual(result, SVG)
            self.assertEqual(len(calls),3)
            self.assertEqual(calls[0]['chat_key'], 'original')
            self.assertEqual(calls[1]['chat_key'], 'original')
            self.assertNotEqual(calls[2]['chat_key'], 'original')

    def test_persistent_refusal_is_reported_after_three_attempts(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); bridge=self._bridge(root); calls=[]
            def fake_submit(_client, job):
                calls.append(dict(job)); folder=root/f'refusal_{len(calls)}'; folder.mkdir()
                (folder/'response.txt').write_text(REFUSAL, encoding='utf-8')
                (folder/'response.json').write_text(json.dumps({'success':True,'artifacts':[]}), encoding='utf-8')
                return folder
            with patch.object(myhub_llm._BridgeClient,'ensure_running',lambda self:None), patch.object(myhub_llm._BridgeClient,'submit',fake_submit):
                llm=myhub_llm.criar_llm_myhub({'myhub_bridge_dir':str(bridge),'m1_myhub_timeout_seconds':300},root,lambda _:None,chat_key='original')
                with self.assertRaises(myhub_llm.MyHubArtifactMissingError) as ctx:
                    llm('DESENHE: personagem_teste',False)
            self.assertTrue(ctx.exception.no_retry)
            self.assertEqual(len(calls),3)

    def test_adapter_preserves_loose_sidecar_after_selecting_svg(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); bridge=self._bridge(root)
            side={'partes':[{'id':'corpo'}],'animacoes':{'parado':{'duracao':1}}}
            raw=SVG+'\n'+json.dumps(side,ensure_ascii=False)
            def fake_submit(_client,_job):
                folder=root/'result_side'; folder.mkdir(exist_ok=True)
                (folder/'response.txt').write_text(raw,encoding='utf-8')
                (folder/'response.json').write_text(json.dumps({'success':True,'artifacts':[]}),encoding='utf-8')
                return folder
            with patch.object(myhub_llm._BridgeClient,'ensure_running',lambda self:None), patch.object(myhub_llm._BridgeClient,'submit',fake_submit):
                llm=myhub_llm.criar_llm_myhub({'myhub_bridge_dir':str(bridge),'m1_myhub_timeout_seconds':300},root,lambda _:None,chat_key='original')
                result=llm('DESENHE: personagem_teste',False)
            svg, side_text=result.split('\n',1)
            self.assertEqual(svg,SVG)
            self.assertEqual(json.loads(side_text),side)

if __name__ == '__main__':
    unittest.main(verbosity=2)
