"""Synthetic-only equivalence tests; never construct Shield or read any corpus."""
from collections import defaultdict
import random
from unittest.mock import patch

import language_overlap_index as fast
from protect_split import Shield, anchors, grams, shape, words


def synthetic(texts):
    shield=Shield.__new__(Shield)  # Bypass constructor: it reads private files.
    shield.exact=set();shield.shapes=set();shield.grams=set()
    shield.anchor_sets=[];shield.by_anchor=defaultdict(set)
    shield.calls=set();shield.generic_units=set()
    for text in texts:
        shield.exact.add(tuple(words(text)));shield.shapes.add(shape(text));shield.grams.update(grams(text))
        terms=anchors(text);index=len(shield.anchor_sets);shield.anchor_sets.append(terms)
        for word in terms:shield.by_anchor[word].add(index)
    return shield


def run():
    rng=random.Random(417)
    vocabulary=['amber','breeze','cactus','dolphin','ember','fossil','garden','harbor','island','jungle',
                'kettle','lemon','marble','nectar','orchid','pebble','quartz','raven','silver','tulip',
                'umber','velvet','willow','xenon','yellow','zephyr','acorn','brook','cloud','drift']
    fixed=['Sing blue moons', 'Alice keeps 17 amber stones today',
           'one two three four five six seven eight nine ten',
           'Ｃａｔ Café amber breeze cactus dolphin',
           'amber breeze cactus dolphin ember fossil garden harbor island jungle',
           'amber breeze cactus dolphin ember', 'please answer', '']
    synthetic_texts=fixed+[' '.join(rng.sample(vocabulary,rng.randint(3,16))) for _ in range(150)]
    shields=[synthetic(synthetic_texts[:80]),synthetic(synthetic_texts[80:])]
    merged=fast.TextOverlapIndex(shields)
    candidates=list(synthetic_texts)+['Bob keeps 98 amber stones today','sing BLUE moons!!!',
       'prefix one two three four five six seven eight suffix','User: Sing blue moons\nAssistant: Okay.',
       'Café amber breeze cactus dolphin','ＣＡＴ café AMBER breeze cactus dolphin',
       'A number -12.5 appears by 3 and +7.0 in a sentence','the and or','',
       'xenon ١٢ 123 ² ४']
    for _ in range(1000):
        candidate=' '.join(rng.choices(vocabulary+['the','please','9','Alice'],k=rng.randint(0,70)))
        if rng.random()<.3:candidate=candidate.upper()
        candidates.append(candidate)
    compared=0
    for text in candidates:
        expected=any(bool(s.reasons([{'role':'user','text':text}])) for s in shields)
        actual=merged.matches(text)
        assert actual==expected,(text,expected,actual)
        compared+=1
    # Isolate anchor matching from exact/shingle/shape checks at both thresholds.
    boundaries=0
    for n_a in range(1,26):
        for n_b in range(1,26):
            for common in range(min(n_a,n_b)+1):
                a=[f'shared{i}' for i in range(common)]+[f'left{i}' for i in range(n_a-common)]
                b=[f'shared{i}' for i in range(common)]+[f'right{i}' for i in range(n_b-common)]
                shield=synthetic([' '.join(b)]);shield.exact.clear();shield.shapes.clear();shield.grams.clear()
                index=fast.TextOverlapIndex([shield])
                text=' '.join(a)
                assert index.matches(text)==bool(shield.reasons([{'role':'user','text':text}])),(n_a,n_b,common)
                boundaries+=1
    # Duplicate anchors across shields do not change the boolean result.
    repeated=synthetic(['amber breeze cactus dolphin ember']*4)
    repeated.exact.clear();repeated.shapes.clear();repeated.grams.clear()
    index=fast.TextOverlapIndex([repeated,repeated])
    assert index.statistics()['anchor_sets']==1
    assert index.matches('amber breeze cactus dolphin ember surplus')
    history=[{'role':'user','text':'User: Sing blue moons\nAssistant: All done'},
             {'role':'user','text':'Sing blue moons'},{'role':'user','text':'All done'}]
    assert merged.matches_history(history)==any(bool(s.reasons(history)) for s in shields)
    assert merged.matches_history(history)
    assert merged.matches_history(iter(history))
    # Main word tokenization happens exactly once; shapes keep their original helper.
    with patch.object(fast,'words',wraps=fast.words) as tokenized:
        merged.matches('unmatched frobnicate blueberry noisette')
        assert tokenized.call_count==1
    # Early positives avoid unnecessary expensive anchoring even at a low work cap.
    limited=fast.TextOverlapIndex([repeated],max_posting_visits=1)
    refused=0
    for action in [lambda:fast.TextOverlapIndex(shields,max_text_chars=3).matches('four'),
                   lambda:limited.matches('amber breeze cactus dolphin'),
                   lambda:merged.matches_history([{'role':'assistant','text':'foo'}]),
                   lambda:merged.matches_history([{'role':'user','text':'Sing blue moons'},
                                                  {'role':'user','text':'foo','call':{}}])]:
        try:action()
        except (ValueError,fast.OverlapLimitError):refused+=1
        else:raise AssertionError('unsupported or excessive input was accepted')
    exact=fast.TextOverlapIndex(shields,max_posting_visits=1)
    assert exact.matches('Sing blue moons')
    print(f'PASS {compared} synthetic text comparisons, {boundaries} anchor-boundary comparisons, '
          f'{refused} refusals, merged duplicates, short role-delimited turn and tokenization reuse; no corpus/private reads')

if __name__=='__main__':run()
