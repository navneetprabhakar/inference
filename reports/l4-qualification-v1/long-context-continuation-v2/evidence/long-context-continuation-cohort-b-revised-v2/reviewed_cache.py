from collections import OrderedDict
import unittest


class HintCache:
    def __init__(self, capacity):
        if capacity < 0:
            raise ValueError('capacity must not be negative')
        self.capacity = capacity
        self._items = OrderedDict()

    def get(self, key, default=None):
        if key not in self._items:
            return default
        self._items.move_to_end(key)
        return self._items[key]

    def put(self, key, value):
        if self.capacity == 0:
            return
        if key in self._items:
            self._items[key] = value
            self._items.move_to_end(key)
            return
        if len(self._items) >= self.capacity:
            self._items.popitem(last=False)
        self._items[key] = value

    def __contains__(self, key):
        return key in self._items

    def __len__(self):
        return len(self._items)

    def keys(self):
        return list(self._items)

    def clear(self):
        self._items.clear()

    def __repr__(self):
        return f'HintCache({self.capacity}, {self.keys()})'


class HintCacheTests(unittest.TestCase):
    def test_read_refreshes_recency(self):
        cache = HintCache(2)
        cache.put('pear', 'fruit')
        cache.put('plum', None)
        self.assertEqual(cache.get('pear'), 'fruit')
        cache.put('kiwi', 'fruit')
        self.assertEqual(cache.keys(), ['pear', 'kiwi'])
        self.assertNotIn('plum', cache)

    def test_update_refreshes_recency(self):
        cache = HintCache(2)
        cache.put('pear', 'old')
        cache.put('plum', None)
        cache.put('pear', 'new')
        cache.put('kiwi', 'fruit')
        self.assertEqual(cache.keys(), ['pear', 'kiwi'])
        self.assertEqual(cache.get('pear'), 'new')

    def test_none_and_miss(self):
        cache = HintCache(2)
        cache.put('pear', None)
        cache.put('plum', 'fruit')
        missing = object()
        self.assertIsNone(cache.get('pear', missing))
        order = cache.keys()
        self.assertIs(cache.get('kiwi', missing), missing)
        self.assertEqual(cache.keys(), order)

    def test_zero_and_negative_capacity(self):
        cache = HintCache(0)
        cache.put('pear', 1)
        cache.put('plum', 2)
        self.assertEqual(len(cache), 0)
        self.assertEqual(cache.keys(), [])
        with self.assertRaises(ValueError):
            HintCache(-1)

    def test_instances_are_independent(self):
        first, second = HintCache(1), HintCache(2)
        first.put('pear', 1)
        second.put('plum', 2)
        second.put('kiwi', 3)
        first.put('pear', 4)
        first.put('apple', 5)  # Evicts pear.
        first.clear()
        self.assertEqual(second.keys(), ['plum', 'kiwi'])
        self.assertEqual(second.get('plum'), 2)
        self.assertEqual(len(first), 0)


if __name__ == '__main__':
    unittest.main()
