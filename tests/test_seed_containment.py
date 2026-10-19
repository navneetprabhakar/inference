# Creator: Navneet Prabhakar
import random
import pytest
from slm.data.seed_containment import PrefixIndex,normalized_bytes


def brute(patterns,raw):
    found=[]
    for key,p in patterns.items():
        start=0
        while (start:=raw.find(p,start))>=0:found.append((key,start));start+=1
    return sorted(found)


def test_every_offset_matches_brute_force_with_repeated_prefixes():
    rng=random.Random(20261019)
    patterns={str(i):bytes(rng.choice(b'abcde ') for _ in range(12)) for i in range(20)}
    raw=b''.join(b'\x80'+p+b'\n' for p in patterns.values())+patterns['1']
    assert sorted(PrefixIndex(patterns,width=7).matches(raw))==brute(patterns,raw)


def test_unicode_whitespace_case_and_partial_utf8_anchor():
    p=normalized_bytes('CAFÉ \n story about a friend')
    raw=normalized_bytes('Prefix: cafe\u0301   story about a friend. CAFÉ story about a friend')
    assert sorted(PrefixIndex({'p':p},width=4).matches(raw))==brute({'p':p},raw)


def test_hash_collision_never_becomes_full_match():
    # Base1 makes equal byte sums collide, including different prefix order.
    index=PrefixIndex({'one':b'abcd-more'},width=4,base=1)
    assert list(index.matches(b'dcba-more'))==[]
    assert any(not full for _,_,full in index.candidates(b'dcba-more'))


def test_short_target_boundaries_and_caps():
    p=b'abcdefgh';index=PrefixIndex({'x':p},width=8,max_bytes=20)
    assert list(index.matches(b'abc'))==[]
    assert list(index.matches(p))==[('x',0)]
    assert list(index.matches(b'Z'+p))==[('x',1)]
    with pytest.raises(ValueError):list(index.matches(b'a'*21))
    with pytest.raises(ValueError):PrefixIndex({'x':b'abc'},width=8)
