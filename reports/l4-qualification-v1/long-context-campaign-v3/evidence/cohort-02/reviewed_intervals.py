from collections.abc import Iterable


def merge(intervals: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
    """Merge overlapping or touching half-open intervals.

    Empty intervals are discarded; reversed bounds raise ValueError.
    The input is consumed once and is not modified.
    """
    valid = []
    for start, end in intervals:
        if start > end:
            raise ValueError(f"Invalid interval: ({start}, {end})")
        if start < end:
            valid.append((start, end))

    valid.sort()
    merged: list[tuple[int, int]] = []
    for start, end in valid:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


if __name__ == "__main__":
    import unittest

    class MergeTests(unittest.TestCase):
        def test_original_and_nested(self):
            self.assertEqual(merge([(1, 8), (2, 3), (7, 10)]), [(1, 10)])
            self.assertEqual(merge([(1, 8), (2, 3)]), [(1, 8)])

        def test_touching_and_separate(self):
            self.assertEqual(merge([(1, 3), (3, 5), (7, 9)]), [(1, 5), (7, 9)])

        def test_empty_intervals_and_input(self):
            self.assertEqual(merge([(4, 4), (1, 2)]), [(1, 2)])
            self.assertEqual(merge([(4, 4)]), [])
            self.assertEqual(merge([]), [])

        def test_invalid(self):
            with self.assertRaises(ValueError):
                merge([(5, 3)])

        def test_negative_bounds(self):
            self.assertEqual(merge([(-5, -2), (-3, 1)]), [(-5, 1)])

        def test_preserves_list(self):
            intervals = [(7, 10), (1, 8), (2, 3)]
            original = intervals.copy()
            self.assertEqual(merge(intervals), [(1, 10)])
            self.assertEqual(intervals, original)

        def test_invalid_in_one_pass_generator(self):
            intervals = iter([(1, 2), (4, 4), (5, 3)])
            with self.assertRaises(ValueError):
                merge(intervals)

    unittest.main()
