"""Mutation tests for exact memory-credit evidence binding; no corpus/cloud writes."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).with_name('selection_memory_integrity.py')
spec = importlib.util.spec_from_file_location('selection_memory_integrity', MODULE)
memory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(memory)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


class MemoryMutationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.messages = [m for i in range(4) for m in (
            {'role': 'user', 'content': f'User turn {i+1}'},
            {'role': 'assistant', 'content': f'Assistant turn {i+1}'})]
        self.q = {'support_turn': 1, 'probe_turn': 4, 'focus': 'A supplied earlier fact'}

    def put(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
        return {'path': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

    def source(self, probe=None, explicit=False):
        record = {'group': 'case', 'content_sha256': digest(self.messages),
                  'decision': 'accept', 'memory_annotation_valid': True}
        if explicit:
            record['recall_probe'] = copy.deepcopy(probe)
            record['valid'] = True
        return self.put('review.json', {'reviews': [record]})

    def fixture(self, original=None, selected=None, credit=False, explicit_source=False):
        turns = [{'user': self.messages[i]['content'], 'assistant': self.messages[i+1]['content']}
                 for i in range(0, len(self.messages), 2)]
        raw = self.put('generation.raw.json', {'conversations': [
            {'group': 'case', 'turns': turns, 'recall_probe': copy.deepcopy(original)}]})
        row = {'group': 'case', 'messages': copy.deepcopy(self.messages),
               'generation': {'raw_artifact': raw['path'], 'raw_sha256': raw['sha256']},
               'memory_probe_credit': credit, 'recall_probe': copy.deepcopy(selected)}
        entry = {'group': 'case', 'messages_sha256': digest(self.messages),
                 'credit': credit, 'recall_probe': copy.deepcopy(selected),
                 'original_generated_annotation': copy.deepcopy(original),
                 'reason': 'Explicit reviewed decision.',
                 'source_receipts': [self.source(selected, explicit_source)] if credit else []}
        self.bind(row, entry)
        return row, entry

    def bind(self, row, entry):
        row['memory_evidence_receipt'] = self.put('memory.json', {'entries': [entry]})

    def fails(self, row, pattern=None):
        with self.assertRaisesRegex(memory.MemoryIntegrityError, pattern or '.'):
            memory.verify_memory(row, self.root)

    def test_valid_unchanged_generated_probe(self):
        row, _ = self.fixture(self.q, self.q, True)
        self.assertTrue(memory.verify_memory(row, self.root)['credit'])

    def test_explicit_no_credit_is_valid(self):
        row, _ = self.fixture()
        self.assertFalse(memory.verify_memory(row, self.root)['credit'])

    def test_row_credit_flip_is_rejected(self):
        row, _ = self.fixture()
        row['memory_probe_credit'] = True
        self.fails(row, 'credit differs')

    def test_row_probe_mutation_is_rejected(self):
        row, _ = self.fixture(self.q, self.q, True)
        row['recall_probe']['focus'] = 'Invented focus'
        self.fails(row, 'probe differs')

    def test_fabricated_null_to_memory_without_evidence(self):
        row, entry = self.fixture(None, self.q, True)
        entry['source_receipts'] = []
        self.bind(row, entry)
        self.fails(row, 'requires hash-bound')

    def test_nonmemory_na_verdict_cannot_authorize_new_probe(self):
        row, _ = self.fixture(None, self.q, True)
        self.fails(row, 'explicit valid annotation')

    def test_new_probe_requires_explicit_exact_annotation_audit(self):
        row, _ = self.fixture(None, self.q, True, explicit_source=True)
        self.assertTrue(memory.verify_memory(row, self.root)['credit'])

    def test_corrected_focus_generic_review_is_insufficient(self):
        corrected = dict(self.q, focus='A different focused fact')
        row, _ = self.fixture(self.q, corrected, True)
        self.fails(row, 'explicit valid annotation')

    def test_corrected_focus_exact_audit_passes(self):
        corrected = dict(self.q, focus='A different focused fact')
        row, _ = self.fixture(self.q, corrected, True, explicit_source=True)
        self.assertTrue(memory.verify_memory(row, self.root)['credit'])

    def test_wrong_focus_in_correction_audit_rejected(self):
        corrected = dict(self.q, focus='A different focused fact')
        row, entry = self.fixture(self.q, corrected, True, explicit_source=True)
        entry['source_receipts'] = [self.source(self.q, explicit=True)]
        self.bind(row, entry)
        self.fails(row, 'explicit valid annotation')

    def test_original_annotation_cannot_be_forged(self):
        row, entry = self.fixture(None, self.q, True, explicit_source=True)
        entry['original_generated_annotation'] = copy.deepcopy(self.q)
        self.bind(row, entry)
        self.fails(row, 'Original annotation differs')

    def test_stale_memory_receipt_rejected(self):
        row, _ = self.fixture()
        (self.root / 'memory.json').write_text('{}')
        self.fails(row, 'Stale receipt')

    def test_stale_source_receipt_rejected(self):
        row, _ = self.fixture(self.q, self.q, True)
        (self.root / 'review.json').write_text('{}')
        self.fails(row, 'Stale receipt')

    def test_stale_generation_rejected(self):
        row, _ = self.fixture()
        (self.root / 'generation.raw.json').write_text('{}')
        self.fails(row, 'Stale receipt')

    def test_nonempty_uncredited_probe_rejected(self):
        row, entry = self.fixture(self.q, self.q, False)
        self.fails(row, 'Uncredited probe must be null')

    def test_missing_explicit_row_null_rejected(self):
        row, _ = self.fixture()
        del row['recall_probe']
        self.fails(row, 'Explicit selected probe')

    def test_gap_and_indices_rejected(self):
        for q in (dict(self.q, support_turn=2), dict(self.q, support_turn=0),
                  dict(self.q, probe_turn=5), dict(self.q, support_turn=True),
                  dict(self.q, focus=' ')):
            with self.subTest(q=q):
                row, _ = self.fixture(q, q, True, explicit_source=True)
                self.fails(row)

    def test_rejected_source_cannot_authorize_probe(self):
        row, entry = self.fixture(self.q, self.q, True)
        bad = {'reviews': [{'group': 'case', 'messages_sha256': digest(self.messages),
                            'decision': 'reject', 'memory_annotation_valid': True}]}
        entry['source_receipts'] = [self.put('review.json', bad)]
        self.bind(row, entry)
        self.fails(row, 'valid memory review')

    def legacy(self, credit=True):
        row, entry = self.fixture(None, self.q if credit else None, credit)
        original = {'last_supporting_turn': 1, 'probe_turn': 4, 'probe_focus': self.q['focus']}
        old = {'group': 'case', 'messages': self.messages}
        snapshot = self.root / 'baseline.jsonl'
        snapshot.write_text(json.dumps(old) + '\n')
        selection = {'source_snapshot': 'baseline.jsonl',
                     'source_payload_sha256': hashlib.sha256(snapshot.read_bytes()).hexdigest(),
                     'entries': [{'group': 'case', 'messages_sha256': digest(self.messages), 'decision': 'accept'}],
                     'annotation_decisions': [{'group': 'case', 'messages_sha256': digest(self.messages),
                       'valid': True, 'dialogue_selected': True, 'original_annotation': original,
                       'latest_support_turn': 1, 'probe_turn': 4, 'narrow_focus': self.q['focus']}]}
        selected = self.put('pinned-selection.json', selection)
        row['fresh_selection_receipt'] = selected
        entry['original_generated_annotation'] = original
        entry['source_receipts'] = [selected] if credit else []
        self.bind(row, entry)
        return row, entry, selection

    def test_pinned_legacy_receipt_used_not_mutable_current(self):
        row, _, _ = self.legacy()
        self.put('worker-c/selection-receipt.json', {'entries': []})
        self.assertTrue(memory.verify_memory(row, self.root)['credit'])

    def test_legacy_annotation_cannot_be_changed_with_entry(self):
        row, entry, _ = self.legacy()
        row['recall_probe']['focus'] = 'Fabricated legacy focus'
        entry['recall_probe'] = copy.deepcopy(row['recall_probe'])
        self.bind(row, entry)
        self.fails(row, 'pinned annotation decision')

    def test_legacy_selected_exclude_rejected(self):
        row, entry, selection = self.legacy(False)
        selection['entries'][0]['decision'] = 'exclude'
        row['fresh_selection_receipt'] = self.put('pinned-selection.json', selection)
        self.fails(row, 'does not accept exact content')

    def test_legacy_invalid_credit_rejected(self):
        row, entry, selection = self.legacy()
        selection['annotation_decisions'][0]['valid'] = False
        ref = self.put('pinned-selection.json', selection)
        row['fresh_selection_receipt'] = ref
        entry['source_receipts'] = [ref]
        self.bind(row, entry)
        self.fails(row, 'no valid memory credit')

    def test_legacy_snapshot_mutation_rejected(self):
        row, _, _ = self.legacy()
        (self.root / 'baseline.jsonl').write_text('{}\n')
        self.fails(row)


if __name__ == '__main__':
    unittest.main()
