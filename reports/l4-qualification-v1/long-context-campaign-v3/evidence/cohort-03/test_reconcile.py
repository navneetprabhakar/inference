import unittest
from copy import deepcopy

from reconciler import reconcile


class ReconcileTests(unittest.TestCase):
    def test_patch_zero_and_deletion(self):
        current = {'pen': 2, 'tape': 1, 'book': 4}
        updates = {'pen': 0, 'tape': None, 'missing': None}
        self.assertEqual(reconcile(current, updates), {'pen': 0, 'book': 4})

    def test_pair_updates_and_success_leave_inputs_unchanged(self):
        current = {'pen': 2, 'tape': 1}
        updates = [('pen', 0), ('tape', None), ('book', 3)]
        before_current = deepcopy(current)
        before_updates = deepcopy(updates)
        self.assertEqual(reconcile(current, updates), {'pen': 0, 'book': 3})
        self.assertEqual(current, before_current)
        self.assertEqual(updates, before_updates)

    def test_duplicate_pairs_raise_even_if_quantities_match(self):
        for updates in (
            [('pen', 1), ('pen', 1)],
            [('pen', 1), ('pen', 2)],
            [('pen', None), ('pen', None)],
        ):
            with self.subTest(updates=updates):
                with self.assertRaises(ValueError):
                    reconcile({}, updates)

    def test_invalid_existing_entries(self):
        for current in ({'': 1}, {1: 1}, {'pen': None},
                        {'pen': -1}, {'pen': True}, {'pen': 1.5}):
            with self.subTest(current=current):
                before = deepcopy(current)
                with self.assertRaises(ValueError):
                    reconcile(current, {})
                self.assertEqual(current, before)

    def test_invalid_update_after_valid_update_preserves_inputs(self):
        for invalid in [('', 1), (1, 1), ('book', -1),
                        ('book', False), ('book', 1.5)]:
            with self.subTest(invalid=invalid):
                current = {'pen': 2, 'tape': 1}
                updates = [('pen', 0), invalid]
                before_current = deepcopy(current)
                before_updates = deepcopy(updates)
                with self.assertRaises(ValueError):
                    reconcile(current, updates)
                self.assertEqual(current, before_current)
                self.assertEqual(updates, before_updates)

    def test_duplicate_failure_preserves_inputs(self):
        current = {'pen': 2}
        updates = [('pen', 1), ('pen', 1)]
        before_current = deepcopy(current)
        before_updates = deepcopy(updates)
        with self.assertRaises(ValueError):
            reconcile(current, updates)
        self.assertEqual(current, before_current)
        self.assertEqual(updates, before_updates)


if __name__ == '__main__':
    unittest.main()
