def top_k(records, k):
    if k < 0:
        raise ValueError('k must be nonnegative')
    return sorted(records, key=lambda record: record['score'], reverse=True)[:k]

import pytest


def test_stable_ties_repeated_ids_and_no_mutation():
    records = [
        {'id': 'A', 'score': 5},
        {'id': 'B', 'score': 7},
        {'id': 'C', 'score': 7},
        {'id': 'B', 'score': 4},
    ]
    original = records.copy()

    assert top_k(records, 2) == [records[1], records[2]]
    assert records == original
    assert top_k(records, 10) == [
        records[1], records[2], records[0], records[3]
    ]
    assert records == original


def test_zero_and_negative_k():
    records = [{'id': 'A', 'score': 1}]
    assert top_k(records, 0) == []
    with pytest.raises(ValueError):
        top_k(records, -1)


def test_one_pass_iterator():
    records = [
        {'id': 'A', 'score': 5},
        {'id': 'B', 'score': 7},
        {'id': 'C', 'score': 7},
    ]
    iterations = 0

    def source():
        nonlocal iterations
        iterations += 1
        yield from records

    generator = source()
    assert top_k(generator, 2) == [records[1], records[2]]
    assert iterations == 1
    assert list(generator) == []
