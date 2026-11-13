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



def subtract(availability, blackouts):
    """Subtract blackouts from half-open availability intervals.

    Empty intervals are discarded; reversed bounds raise ValueError.
    Inputs are consumed once and are not modified.
    """
    available = merge(availability)
    blocked = merge(blackouts)
    result = []
    j = 0
    for start, end in available:
        while j < len(blocked) and blocked[j][1] <= start:
            j += 1
        cursor = start
        k = j
        while k < len(blocked) and blocked[k][0] < end:
            left, right = blocked[k]
            if left > cursor:
                result.append((cursor, left))
            cursor = max(cursor, right)
            if cursor >= end:
                break
            k += 1
        if cursor < end:
            result.append((cursor, end))
        j = k
    return result


if __name__ == '__main__':
    import unittest

    class SubtractTests(unittest.TestCase):
        def test_middle_and_touching(self):
            self.assertEqual(subtract([(1, 10)], [(3, 5)]), [(1, 3), (5, 10)])
            self.assertEqual(subtract([(1, 5)], [(5, 8)]), [(1, 5)])

        def test_complete_and_fragments(self):
            self.assertEqual(subtract([(1, 5)], [(0, 6)]), [])
            self.assertEqual(subtract([(0, 10)], [(2, 3), (5, 7)]),
                             [(0, 2), (3, 5), (7, 10)])
            self.assertEqual(subtract([(1, 3), (5, 8)], [(2, 6)]),
                             [(1, 2), (6, 8)])

        def test_validation_and_preservation(self):
            a, b = [(5, 8), (1, 3)], [(2, 2), (6, 7)]
            self.assertEqual(subtract(a, b), [(1, 3), (5, 6), (7, 8)])
            self.assertEqual(a, [(5, 8), (1, 3)])
            self.assertEqual(b, [(2, 2), (6, 7)])
            with self.assertRaises(ValueError):
                subtract([], iter([(1, 2), (5, 3)]))
            self.assertEqual(subtract(iter([]), iter([])), [])

    unittest.main()
