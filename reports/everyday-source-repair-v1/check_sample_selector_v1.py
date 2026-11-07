"""Synthetic-only deterministic sample checks; no corpus access."""
from select_quality_sample_v1 import choose
r=[dict(doc_id=f'fixture:{i:04d}',full_history_character_length=i,old_whole=0 if i<4 or i%3==0 else 1) for i in range(770)]
a,c=choose(r,20261110);b,d=choose(list(reversed(r)),20261110)
assert a==b and c==d
assert len(a)==len({x['doc_id'] for x in a})==64
assert all(sum(x['quartile']==q for x in a)==16 for q in range(4))
assert sum(x['eligible'] for x in c.values())==770
assert all(sum(x['cell_selected'].values())==16 for x in c.values())
r=[dict(x,old_whole=1) for x in r];a,c=choose(r,20261110)
assert len(a)==64 and all(set(x['cell_population'])=={'1'} for x in c.values())
print('6 deterministic selector fixtures PASS; no source read')
