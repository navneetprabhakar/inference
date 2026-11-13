"""Verify web adaptation preserves raw answers, failures, tool policy and retries."""
import unittest
from types import SimpleNamespace
from cloud_training.nano_chat_http import WebChat
from serve_chat import Sessions, RequestError


class FakeChat:
    def __init__(self, result):
        self.result = result
        self.broker = SimpleNamespace(trace=[])
        self.calls = []

    def turn(self, message, *, policy):
        self.calls.append((message, policy))
        return self.result


class WebTests(unittest.TestCase):
    def test_raw_text_policy_and_retry(self):
        fake = FakeChat({'status':'complete', 'assistant_text':'Raw model text.', 'events':[]})
        sessions = Sessions(lambda:WebChat(fake), {})
        token = sessions.open()['session']
        result = sessions.turn(token, 'one', 'Hello', False)
        self.assertEqual(result['answer'], 'Raw model text.')
        self.assertEqual(fake.calls[0][1], {'permit_calls':False,'allowed_names':[]})
        self.assertEqual(sessions.turn(token, 'one', 'Hello', False), result)
        self.assertEqual(len(fake.calls), 1)
        with self.assertRaises(RequestError):
            sessions.turn(token, 'one', 'Different', False)

    def test_tools_and_invalid_action_remain_visible(self):
        record = {'name':'calculate', 'ok':True, 'data':{'result':54}}
        fake = FakeChat({'status':'error', 'assistant_text':None,
                        'error_code':'invalid_model_action', 'detail':'incomplete output',
                        'reset_required':True, 'events':[
                            {'kind':'broker_decision','decision':{'dispatched':True},'record':record},
                            {'kind':'model_action','parsed':{'kind':'invalid','error':'incomplete'}}]})
        result = WebChat(fake).turn('Calculate', permit_calls=True)
        self.assertIsNone(result['answer'])
        self.assertEqual(result['trace'], [record])
        self.assertIn('Start a new chat', result['failure'])
        self.assertEqual(result['frame_origins'], ['own-model/raw'])
        self.assertEqual(fake.calls[0][1]['allowed_names'], ['calculate','convert'])


if __name__ == '__main__':
    unittest.main()
