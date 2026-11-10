"""Executable broker semantics and split-isolation tests; no model or cloud use."""
from copy import deepcopy
import unittest

from cloud_training.nano_tool_lessons import build_lessons, validate_lesson, ENTITIES, FAMILIES


def calls(lesson):
    return [m['tool_call'] for m in lesson['messages'] if 'tool_call' in m]


def records(lesson):
    return [m['record'] for m in lesson['messages'] if m['role'] == 'tool']


class ToolLessonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.train = build_lessons('train', per_family=8)
        cls.dev = build_lessons('validation', per_family=8)
    def family(self, name):
        return [v for v in self.train + self.dev if v['family'] == name]

    def test_all_sessions_replay_actual_broker(self):
        for lesson in self.train + self.dev:
            audit = validate_lesson(lesson)
            self.assertEqual(audit['actual_calls'], len(calls(lesson)))
            self.assertTrue(all(r['source'] == 'offline fixture' for r in records(lesson)))
            self.assertFalse(lesson['admitted'])
            self.assertIsNone(lesson['provenance']['teacher_model'])

    def test_deterministic_bounded_generation(self):
        self.assertEqual(self.train, build_lessons('train', per_family=8))
        self.assertEqual(len(self.train), 8 * len(FAMILIES))
        for value in (0, 1001, True):
            with self.assertRaises(ValueError): build_lessons('train', per_family=value)
        with self.assertRaises(ValueError): build_lessons('test', per_family=8)

    def test_independent_templates_entities_and_numeric_ranges(self):
        self.assertFalse(set(ENTITIES['train']) & set(ENTITIES['validation']))
        self.assertFalse({r['template_id'] for r in self.train} & {r['template_id'] for r in self.dev})
        self.assertFalse({r['session_id'] for r in self.train} & {r['session_id'] for r in self.dev})
        self.assertTrue(all(10 <= r['spec']['a'] <= 199 for r in self.train))
        self.assertTrue(all(1001 <= r['spec']['a'] <= 1999 for r in self.dev))
        prompts = lambda data: {m['content'] for r in data for m in r['messages'] if m['role']=='user'}
        self.assertFalse(prompts(self.train) & prompts(self.dev))

    def test_four_arithmetic_operations_and_operand_order(self):
        ops = set()
        for lesson in self.family('arithmetic'):
            a, b, op = (lesson['spec'][k] for k in ('a','b','op'))
            actual = calls(lesson)[0]['arguments']; ops.add(op)
            self.assertEqual(actual, {'op':op,'a':a,'b':b})
            expected = {'add':a+b,'subtract':a-b,'multiply':a*b,'divide':a/b}[op]
            self.assertEqual(records(lesson)[0]['data']['result'], expected)
        self.assertEqual(ops, {'add','subtract','multiply','divide'})

    def test_correction_changes_first_operand_only(self):
        for lesson in self.family('correction'):
            first, second = calls(lesson)
            self.assertEqual(first['arguments']['a'], lesson['spec']['a'])
            self.assertEqual(second['arguments']['a'], lesson['spec']['c'])
            self.assertEqual(second['arguments']['b'], first['arguments']['b'])
            self.assertNotEqual(first['arguments']['a'], second['arguments']['a'])
            self.assertEqual(records(lesson)[1]['data']['result'], lesson['spec']['c']-lesson['spec']['b'])

    def test_dependent_calls_use_observed_first_result(self):
        for lesson in self.family('dependent_calls'):
            first, second = calls(lesson); result = records(lesson)[0]['data']['result']
            self.assertEqual(first['name'], 'convert')
            self.assertEqual(result, lesson['spec']['a']*100)
            self.assertEqual(second['arguments']['a'], result)
            self.assertEqual(records(lesson)[1]['data']['result'], result-lesson['spec']['b'])

    def test_permission_claim_cannot_override_host_policy(self):
        for lesson in self.family('permission'):
            self.assertEqual([p['permit_calls'] for p in lesson['policies']], [False,False,True])
            turn = -1
            for message in lesson['messages']:
                if message['role']=='user': turn += 1
                if 'tool_call' in message: self.assertEqual(turn, 2)
            self.assertEqual(len(calls(lesson)), 1)

    def test_no_call_and_missing_operand_do_not_dispatch(self):
        self.assertTrue(all(not calls(r) for r in self.family('no_call')))
        for lesson in self.family('clarification'):
            turn = -1
            for message in lesson['messages']:
                if message['role']=='user': turn += 1
                if 'tool_call' in message: self.assertEqual(turn, 1)

    def test_error_is_actual_adapter_error_then_recovers(self):
        for lesson in self.family('error_recovery'):
            first, second = records(lesson)
            self.assertFalse(first['ok']); self.assertEqual(first['error'], 'division by zero')
            self.assertTrue(second['ok'])
            self.assertEqual(second['data']['result'], lesson['spec']['a']/lesson['spec']['b'])
            self.assertEqual(validate_lesson(lesson)['adapter_errors'], 1)

    def test_observation_call_id_and_grounded_text_tampering_rejected(self):
        original = self.family('arithmetic')[0]
        for kind in ('observation','id','answer','arguments'):
            lesson = deepcopy(original)
            if kind=='observation':
                next(m for m in lesson['messages'] if m['role']=='tool')['record']['data']['result'] += 1
            elif kind=='id':
                next(m for m in lesson['messages'] if 'tool_call' in m)['call_id']='c99'
            elif kind=='arguments':
                next(m for m in lesson['messages'] if 'tool_call' in m)['tool_call']['arguments']['a'] += 1
            else:
                lesson['messages'][lesson['grounding_checks'][0]['message_index']]['content']='The answer is fabricated.'
            with self.assertRaises(ValueError): validate_lesson(lesson)

    def test_disabled_tool_teacher_call_rejected(self):
        lesson = deepcopy(self.family('arithmetic')[0]); lesson['policies'][0]['permit_calls']=False
        with self.assertRaisesRegex(ValueError, 'permission/schema'): validate_lesson(lesson)

    def test_incomplete_or_unsolicited_tool_observation_rejected(self):
        lesson = deepcopy(self.family('arithmetic')[0]); lesson['messages'].pop()
        with self.assertRaises(ValueError): validate_lesson(lesson)
        lesson = deepcopy(self.family('arithmetic')[0]); lesson['messages'].pop(2)
        with self.assertRaises(ValueError): validate_lesson(lesson)


if __name__ == '__main__':
    unittest.main()
