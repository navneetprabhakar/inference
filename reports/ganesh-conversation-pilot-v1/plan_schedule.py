"""Offline exact-target block plan. NOT supported by current training runner."""
import collections,hashlib,itertools,json,random
from pathlib import Path
P=Path(__file__).resolve().parent
assert not (P/'freeze.json').exists(), 'Frozen packet; create a new version'
rows=[json.loads(x) for x in (P/'train.jsonl').read_text().splitlines()]
stats=json.loads((P/'row-statistics.json').read_text())['train'];byid={r['id']:r for r in rows};families=sorted(set(r['family'] for r in rows));control_ids=set();blocks={};residual=[]
for family in families:
 rr=[r for r in stats if r['family']==family];goal=sum(r['assistant_targets'] for r in rr);positions=sum(r['tokens'] for r in rr);turns=sum(r['turns'] for r in rr)
 if family in ('tools','model_identity'):counts=[1]*len(rr);selected=rr
 else:
  best=None
  for k in [3,4]:
   for ix in itertools.combinations(range(len(rr)),k):
    for cs in itertools.product(range(1,9),repeat=k):
     if sum(cs)>12:continue
     if sum(rr[i]['assistant_targets']*n for i,n in zip(ix,cs))!=goal:continue
     score=(abs(sum(cs)-len(rr)),abs(sum(rr[i]['turns']*n for i,n in zip(ix,cs))-turns),abs(sum(rr[i]['tokens']*n for i,n in zip(ix,cs))-positions),max(cs),tuple(ix),cs)
     if best is None or score<best[0]:best=(score,ix,cs)
   if best and best[0][0]==0 and best[0][1]==0:break
  assert best is not None,('No exact full-conversation target match',family,goal)
  selected=[rr[i] for i in best[1]];counts=list(best[2])
 broad=[r['id'] for r in rr];narrow=[r['id'] for r,n in zip(selected,counts) for _ in range(n)];control_ids.update(narrow)
 assert sum(next(x['assistant_targets'] for x in rr if x['id']==i) for i in narrow)==goal
 blocks[family]={'broad_ids':broad,'control_ids':narrow,'assistant_targets':goal}
 residual.append(dict(family=family,broad_unique=len(rr),control_unique=len(selected),broad_exposures=len(broad),control_exposures=len(narrow),broad_turns=turns,control_turns=sum(r['turns']*n for r,n in zip(selected,counts)),broad_positions=positions,control_positions=sum(r['tokens']*n for r,n in zip(selected,counts)),targets_each=goal,control_repeats={r['id']:n for r,n in zip(selected,counts)}))
(P/'control.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows if r['id'] in control_ids))
schedule=[]
for cycle in range(4):
 order=families[:];random.Random(103+cycle).shuffle(order)
 for family in order:
  b=blocks[family];o={'update':len(schedule)+1,'cycle':cycle,'family':family,'assistant_targets_each_arm':b['assistant_targets']}
  for arm in ['broad','control']:
   seq=b[arm+'_ids'][:];random.Random(103+cycle).shuffle(seq);o[arm]=seq
  schedule.append(o)
assert len(schedule)==40
plan={'schema':1,'status':'offline_plan_only_runner_integration_required','parent_manifest_sha256':'70075d157bb3a1bfa96866b3a5737d41037f416ce54b961b2ed0d5f16aa13145','seed':103,'cycles':4,'updates_per_arm':40,'targets_per_arm':sum(x['assistant_targets_each_arm'] for x in schedule),'epoch_equivalent_broad':4,'family_target_matching':'exact each update; full conversations and EOS, no target truncation or padding losses','selection':'Train-only token/length matching; no model outputs or development scores used. Narrow3or4of8 scenarios per family; shared tool/identity rows retained.','blocks':schedule,'residuals':residual,'unsupported_by_existing_nano_sft':['Explicit replay index blocks','One optimizer update per prescribed block with variable microbatch count','Learning-rate and momentum clock shared by block index rather than consumed-conversation fraction','Resume identity binding block plan, block cursor and persistent guards','Per-block target-equality checks before optimizer step']}
(P/'exposure-plan.json').write_text(json.dumps(plan,indent=2)+'\n');print(json.dumps({'targets_per_arm':plan['targets_per_arm'],'updates_per_arm':40,'control_unique':len(control_ids),'residuals':residual},indent=2))
