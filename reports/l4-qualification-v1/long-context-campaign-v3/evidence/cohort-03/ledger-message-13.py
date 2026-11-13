from collections.abc import Mapping
import unittest


def reconcile(current, updates):
    def validate(key, qty, allow_none):
        if not isinstance(key, str) or not key:
            raise ValueError('Invalid key')
        if qty is None and allow_none:
            return
        if isinstance(qty, bool) or not isinstance(qty, int) or qty < 0:
            raise ValueError('Invalid quantity')

    for key, qty in current.items():
        validate(key, qty, False)

    result = current.copy()
    seen = set()
    pairs = updates.items() if isinstance(updates, Mapping) else updates
    for key, qty in pairs:
        validate(key, qty, True)
        if key in seen:
            raise ValueError('Duplicate key')
        seen.add(key)
        if qty is None:
            result.pop(key, None)
        else:
            result[key] = qty
    return result


class ReconcileTests(unittest.TestCase):
    def test_patch_and_inputs(self):
        current = {'pen': 2, 'tape': 1, 'book': 4}
        updates = [('pen', 0), ('tape', None), ('missing', None)]
        self.assertEqual(reconcile(current, iter(updates)), {'pen': 0, 'book': 4})
        self.assertEqual(current, {'pen': 2, 'tape': 1, 'book': 4})
        self.assertEqual(updates, [('pen', 0), ('tape', None), ('missing', None)])

    def test_duplicate_and_invalid_updates_preserve_inputs(self):
        for bad in [[('pen', 1), ('pen', 1)],
                    [('pen', 1), ('', 2)], [('pen', 1), (1, 2)],
                    [('pen', 1), ('x', -1)], [('pen', 1), ('x', True)],
                    [('pen', 1), ('x', 1.5)]]:
            with self.subTest(bad=bad):
                current = {'pen': 2}
                before = bad.copy()
                with self.assertRaises(ValueError):
                    reconcile(current, bad)
                self.assertEqual(current, {'pen': 2})
                self.assertEqual(bad, before)

    def test_invalid_current(self):
        for current in ({'': 1}, {1: 1}, {'x': None}, {'x': -1},
                        {'x': False}, {'x': 1.5}):
            with self.subTest(current=current):
                before = current.copy()
                with self.assertRaises(ValueError):
                    reconcile(current, [])
                self.assertEqual(current, before)


if __name__ == '__main__':
    unittest.main()
