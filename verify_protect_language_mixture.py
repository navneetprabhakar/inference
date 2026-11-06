"""Synthetic overlap regressions; never load actual protected case files."""
from collections import Counter, defaultdict

from protect_language_mixture import augment, candidate_history
from protect_split import Shield


def empty_shield():
    shield = Shield.__new__(Shield)
    for name in ('grams', 'exact', 'shapes', 'calls', 'generic_units'):
        setattr(shield, name, set())
    shield.anchor_sets = []
    shield.by_anchor = defaultdict(set)
    shield.counts = Counter()
    return shield


def main():
    shield = empty_shield()
    augment(shield, {'turns': [{'user': 'Count violet shells',
                              'answer': 'There are seven shells'}]})
    transcript = ('User: Count violet shells\nAssistant: Certainly.\n'
                  'User: Now reverse the order.\nAssistant: Done.')
    assert not shield.reasons([{'role': 'user', 'text': transcript}])
    assert 'same_user_prompt' in shield.reasons(candidate_history(transcript))
    assert shield.reasons(candidate_history('User: A new request.\nAssistant: There are seven shells'))
    assert not shield.reasons(candidate_history('User: Describe snowfall.\nAssistant: Snow is frozen precipitation.'))
    multiline = candidate_history('User: First line\nsecond line\nAssistant: Final line')
    assert multiline[1]['text'] == 'First line\nsecond line'
    assert multiline[2]['text'] == 'Final line'
    assert len(candidate_history('Plain prose with no role delimiter.')) == 1
    augment(shield, {'user': 'Keep exactly 19 blue stones'})
    assert 'same_prompt_shape' in shield.reasons(candidate_history('User: Keep exactly 28 blue stones'))
    print('PASS: synthetic short-turn, assistant, multiline and unrelated-text overlap checks; no private files read')


if __name__ == '__main__':
    main()
