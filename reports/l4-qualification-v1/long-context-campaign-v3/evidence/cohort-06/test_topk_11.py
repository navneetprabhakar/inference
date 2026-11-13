def top_k(records, k):
    if k < 0:
        raise ValueError('k must be nonnegative')
    return sorted(records, key=lambda record: record['score'], reverse=True)[:k]

import pytest


def test_stable_ties_and_repeated_ids():
    records = [
        {'id': 'A', 'score': 5},
        {'id': 'B', 'score': 7},
        {'id': 'C', 'score': 7},
        {'id': 'B', 'score': 4},
    ]
    assert top_k(records, 2) == [records[1], records[2]]
    assert top_k(records, 10) == [
        records[1], records[2], records[0], records[3]
    ]


def test_does_not_mutate_input():
    records = [{'id': 'A', 'score': 1}, {'id': 'B', 'score': 2}]
    original = records.copy()
    top_k(records, 1)
    assert records == original


def test_zero_and_negative_k():
    records = [{'id': 'A', 'score': 1}]
    assert top_k(records, 0) == []
    with pytest.raises(ValueError):
        top_k(records, -1)


def test_single_iteration_request():
    class SinglePass:
        def __init__(self):
            self.requests = 0

        def __iter__(self):
            self.requests += 1
            if self.requests > 1:
                raise AssertionError('second iteration request')
            return iter([
                {'id': 'A', 'score': 5},
                {'id': 'B', 'score': 7},
                {'id': 'C', 'score': 7},
            ])

    source = SinglePass()
    assert top_k(source, 2) == [
        {'id': 'B', 'score': 7}, {'id': 'C', 'score': 7}
    ]
    assert source.requests == 1
