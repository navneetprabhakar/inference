import contextlib
import sys
import tempfile
import threading
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import local_ui

class LocalUIContextTests(unittest.TestCase):
    def engine(self):
        engine = local_ui.Engine()
        engine.load = lambda key: None
        engine.resource_guard = lambda: None
        engine.gpu_guard = contextlib.nullcontext
        engine.loaded_signature = ('baseline', 'fixture', 'a' * 64)
        return engine

    def test_tool_result_is_retained_for_followup(self):
        seen = []
        outputs = iter(['<|tool_call|>{"name":"calculate","arguments":{"expression":"6*7"}}', '42', 'The previous result was 42.'])
        def generate(model, tokenizer, messages, **kwargs):
            seen.append([dict(m) for m in messages])
            return {'output': next(outputs), 'stop': 'eos'}
        fake = types.SimpleNamespace(generate=generate, parse_call=lambda s: {'name': 'calculate'}, execute=lambda c: {'value': 42}, system=lambda: 'fixture tools')
        with patch.dict(sys.modules, {'sft_common': fake}):
            engine = self.engine()
            first = engine.chat('baseline', [{'role': 'user', 'content': 'Calculate 6*7'}], True, threading.Event())
            self.assertEqual([m['role'] for m in first['messages']], ['user', 'assistant', 'tool', 'assistant'])
            engine.chat('baseline', first['messages'] + [{'role': 'user', 'content': 'What was the result?'}], True, threading.Event())
        self.assertEqual(seen[2][3], {'role': 'tool', 'content': '{"value":42}'})

    def test_invalid_call_notice_is_not_model_answer(self):
        def invalid(s): raise ValueError('invalid JSON')
        fake = types.SimpleNamespace(generate=lambda *a, **k: {'output': '<|tool_call|>bad', 'stop': 'eos'}, parse_call=invalid, execute=lambda c: self.fail('must not execute'), system=lambda: 'tools')
        with patch.dict(sys.modules, {'sft_common': fake}):
            result = self.engine().chat('baseline', [{'role': 'user', 'content': 'Calculate'}], True, threading.Event())
        self.assertEqual(result['reply'], '<|tool_call|>bad')
        self.assertTrue(result['notice'])
        self.assertNotIn(result['notice'], [m['content'] for m in result['messages']])

    def test_digest_mismatch_rejected_before_model_load(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'model.safetensors').write_bytes(b'wrong weights')
            with patch.object(local_ui, 'ROOT', root), patch.object(local_ui, 'model_registry', return_value=({'test': {'path': '.', 'sha256': '0' * 64}}, 'test')):
                with self.assertRaisesRegex(RuntimeError, 'digest differs'):
                    local_ui.Engine().load('test')

    def test_gpu_guard_prevents_overlapping_inference(self):
        with tempfile.TemporaryDirectory() as d, patch.object(local_ui, 'ROOT', Path(d)):
            first, second = local_ui.Engine(), local_ui.Engine()
            with first.gpu_guard():
                with self.assertRaisesRegex(RuntimeError, 'GPU guard'):
                    with second.gpu_guard(): self.fail('lock acquired twice')
            with second.gpu_guard(): pass

if __name__ == '__main__': unittest.main()
