"""Non-vacuous sequential baselines and semantic-split checks for preparedv2."""
import json,collections,hashlib
from pathlib import Path
from tasks import oracle,FAMILIES
from contracts import score
ROOT=Path(__file__).resolve().parent;D=ROOT/'private/prepared-v2'
def read(n):return json.loads((D/(n+'.json')).read_text())
rows=read('matrix');correct=total=0
for r in rows:
 if r['scenario']['family'] not in ['state','clarification']:continue
 previous=oracle(r['scenario'])[0] # grant a correct first answer, then repeat it forever
 for turn in range(1,len(r['messages'])//2):
  total+=1;correct+=score(r['scenario'],turn,previous)['complete']
assert total==384 and correct==0
train=read('diverse');missing=[r['scenario'] for r in train if r['scenario']['family']=='missing'];table=collections.defaultdict(collections.Counter)
for s in missing:table[s['color']][s['present']]+=1
assert all(v[True]>0 and v[False]>0 for v in table.values())
# Facts/numeric-ID appearance invariance is tested in checks_v2. Inspect name-component distinction.
name_rows=[r['scenario'] for r in train if r['scenario']['family']=='name'];components={word for r in name_rows for word in r['name'].split()};names={r['name'] for r in name_rows}
new=[r['scenario'] for r in rows if r['scenario']['family']=='name' and r['cell']=='B'];assert all(s['name'] not in names for s in new)
known=sum(all(w in components for w in s['name'].split()) for s in new);unknown=sum(any(w not in components for w in s['name'].split()) for s in new);assert known==unknown==16
# Retained cellA/C is intentionally seen by definition; B/D must be scene-family-disjoint.
assert all(r['scenario']['pool']=='unseen' for r in rows if r['cell'] in 'BD')
result=dict(status='PASS',stale_answer_baseline=dict(first_answer='oracle-correct seed',followup_correct=correct,followup_total=total),missingness_by_color={k:dict(v) for k,v in table.items()},unseen_names=dict(known_components=known,new_components=unknown),context_sensitive_split_note='A/C intentionally share training worlds; B/D use separate world IDs and heldout target relations. This is a controlled matrix, not a blanket claim that all development records are disjoint from training.')
(ROOT/'supplemental-checks.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
