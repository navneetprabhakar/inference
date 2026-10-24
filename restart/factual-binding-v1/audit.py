"""Read-only audit; never updates weights or changes frozen thresholds."""
import json,hashlib,re
from pathlib import Path
from collections import Counter
R=Path(__file__).resolve().parent;P=R.parents[1]
def read(p):return json.loads(p.read_text())
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4194304),b''):h.update(b)
 return h.hexdigest()
result=read(R/'result.json');rows=read(R/'private/final-test-responses.json');cases={r['id']:r for r in read(R/'private/test-encoded.json')}
for path,digest in read(R/'freeze.json')['files'].items():assert sha(P/path)==digest
assert len(rows)==80
for r in rows:
 c=cases[r['id']];assert r['expected']==c['messages'][2*r['turn']+1]['content']
 exact=re.findall(r'\w+',r['response'].casefold())==re.findall(r'\w+',r['expected'].casefold())
 assert exact==r['correct'];assert r['eos']==(r['stop_token']==2)
family={}
for name in ['color','location','owner','correction']:
 selected=[r for r in rows if cases[r['id']]['family']==name]
 family[name]=dict(turns=len(selected),correct_and_eos=sum(r['correct'] and r['eos'] for r in selected),eos=sum(r['eos'] for r in selected))
contexts={};unique={}
for r in rows:
 context=contexts.setdefault(r['id'],[]);context.append(('user',r['user']));unique[tuple(context)]=r;context.append(('assistant',r['response']))
chosen=result['selected'];receipt=dict(status='PASS',frozen_inputs_unchanged=True,parameters=15191712,source_sha256=sha(P/'restart/foundation-resolution-v1/B/checkpoint.pt'),updates_consumed=result['updates_consumed'],sft_targets_consumed=result['sft_targets_consumed'],replay_targets_consumed=result['replay_targets_consumed'],selected_updates=chosen['updates'] if chosen else 0,selected_checkpoint_sha256=chosen['checkpoint_sha256'] if chosen else None,selected_checkpoint_hash_verified=sha(P/chosen['checkpoint'])==chosen['checkpoint_sha256'] if chosen else None,test_counts_recomputed=True,unique_generated_prefixes=len(unique),unique_correct_and_eos=sum(r['correct'] and r['eos'] for r in unique.values()),by_family=family,artifact_bytes=sum(p.stat().st_size for p in R.rglob('*') if p.is_file()),private_response_sha256=sha(R/'private/final-test-responses.json'),replay_duplicates='The original 200 replay batches repeated twice; counts represent exposures, not unique data.',test_independence_limit='Same held-out fact combinations occur in familiar and novel templates; 32 pairs are correlated synthetic probes, not independent benchmark evidence.',checkpoint_promoted=False)
assert receipt['artifact_bytes']<5*1024**3
(R/'audit.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
