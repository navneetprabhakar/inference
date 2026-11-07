"""Small CPU regressions for public-only custody; no protected files or student."""
import json
from pathlib import Path
import tempfile
import unittest

from protect_grounded_public import ROOT, candidate_content, digest, public_index, screen, structured_calls
from protect_split import signature


def case(turns):
    return [('test', [dict(id='synthetic', turns=turns)])]


def turn(user, calls, policy=None):
    return dict(user=user, calls=calls, policy=policy or dict(permit_calls=True),
                answer=dict(mode='manual', rubric='test-only'))


def call(op, a, b):
    return dict(name='calculate', arguments=dict(op=op, a=a, b=b))


class PublicCustodyTests(unittest.TestCase):
    def test_text_and_commutative_signature(self):
        first = call('add', 173, 284)
        index, calls, counts = public_index(case([turn('Archive the violet folio beside the copper cabinet.', [first])]))
        self.assertTrue(index.matches('Archive the violet folio beside the copper cabinet.'))
        self.assertIn(signature(call('add', 284, 173)), calls)
        self.assertFalse(index.matches('An unrelated orchard needs irrigation.'))
        self.assertEqual(counts['expected_call_occurrences'], 1)

    def test_observed_fixture_drives_same_turn_dependency(self):
        first = call('add', 173, 284)
        second = call('multiply', {'ref': dict(turn=0, call=0, field='result')}, 3)
        _, calls, _ = public_index(case([turn('A synthetic chained fixture.', [first, second],
            dict(permit_calls=True, fixture_for=first, fixture=dict(result=911)))]))
        self.assertIn(signature(call('multiply', 911, 3)), calls)
        self.assertNotIn(signature(call('multiply', 457, 3)), calls)

    def test_cross_turn_proposal_reference_after_error(self):
        first = call('divide', 173, 0)
        next_call = call('divide', {'ref': dict(turn=0, call=0, field='proposal_argument:a')}, 5)
        _, calls, counts = public_index(case([turn('A failing synthetic division.', [first]),
                                             turn('A repaired synthetic division.', [next_call])]))
        self.assertIn(signature(call('divide', 173, 5)), calls)
        self.assertEqual(counts['turns'], 2)

    def test_unresolvable_result_fails_closed(self):
        first = call('divide', 173, 0)
        second = call('add', {'ref': dict(turn=0, call=0, field='result')}, 5)
        with self.assertRaises(ValueError):
            public_index(case([turn('Invalid result dependency.', [first, second])]))

    def test_both_full_and_selected_chat_are_screenable(self):
        history = [dict(role='user', text='Selected user sentence.'),
                   dict(role='assistant', text='Selected assistant sentence.')]
        texts, actual = candidate_content(dict(text='Full original parent.',
                                               selected_history_json=json.dumps(history)), 'chat')
        self.assertIn('Full original parent.', texts)
        self.assertIn('Selected assistant sentence.', texts)
        self.assertEqual(actual, history)

    def test_all_nested_tool_proposals_are_found(self):
        a, b = call('subtract', 173, 284), call('multiply', 32, 17)
        original = dict(history=[dict(role='assistant', call=a), dict(role='assistant', call=b)])
        texts, history = candidate_content(dict(original_lesson_json=json.dumps(original)), 'tool')
        self.assertEqual(set(structured_calls(history)), {signature(a), signature(b)})
        self.assertIn(json.dumps(original), texts)

    def test_builder_self_check_cannot_admit_to_screen(self):
        with tempfile.TemporaryDirectory(prefix='custody-test-', dir=ROOT/'data') as tmp:
            p = Path(tmp)
            (p/'candidates.sqlite').write_bytes(b'not a database')
            (p/'candidate-manifest.json').write_text('{}')
            proof = dict(state='PASS_builder_self_check', failures=[], verified_rows=1,
                         database_sha256=digest(p/'candidates.sqlite'),
                         manifest_sha256=digest(p/'candidate-manifest.json'))
            (p/'candidate-verification.json').write_text(json.dumps(proof))
            with self.assertRaisesRegex(ValueError, 'independent candidate verification'):
                screen(p, 'tool')
            self.assertFalse((p/'public-development-custody.json').exists())

    def test_completed_receipt_is_never_overwritten(self):
        with tempfile.TemporaryDirectory(prefix='custody-test-', dir=ROOT/'data') as tmp:
            p = Path(tmp)
            receipt = p/'public-development-custody.json'
            receipt.write_text('preserve this evidence')
            with self.assertRaises(FileExistsError):
                screen(p, 'tool')
            self.assertEqual(receipt.read_text(), 'preserve this evidence')

    def test_oversize_original_parent_fails_closed(self):
        with self.assertRaises(ValueError):
            candidate_content(dict(text='x'*(1024**2+1), selected_history_json='[]'), 'chat')


if __name__ == '__main__':
    unittest.main()
