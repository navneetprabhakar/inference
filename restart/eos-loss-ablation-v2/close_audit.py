"""CPU-only closing checks, paired outcomes and immutable-source verification."""
from pathlib import Path
import json,hashlib
import torch
ROOT=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text())
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(4*1024**2),b''):h.update(block)
 return h.hexdigest()
result=read(ROOT/'result.json');assert result['status']=='COMPLETED'
ledger=read(ROOT/'ledger.json');assert ledger['updates']==400 and 'active_segment' not in ledger
for k in ('updates','positions','sft_targets','narrative_targets'):assert sum(x[k] for x in ledger['reservations'])==ledger[k]
checks={p:sha(Path(p))==expected for p,expected in read(ROOT/'freeze.json')['files'].items()};assert all(checks.values())
old=ROOT.parent/'teacher-bridge-execution-v2'
a=torch.load(old/'private/fit-200.pt',weights_only=False);b=torch.load(ROOT/'private/control-200.pt',weights_only=False)
exact_model=all(torch.equal(v,b['model'][k]) for k,v in a['model'].items())
exact_moments=all(torch.equal(v,b['optimizer']['state'][k][field]) for k,fields in a['optimizer']['state'].items() for field,v in fields.items())
assert exact_model and exact_moments
rows={arm:read(ROOT/'private'/(arm+'-200-responses.json')) for arm in ['control','eos025']}
pairs={}
for family in ['full_name','printed_time']:
 c={r['id']:r for r in rows['control'] if r['family']==family};t={r['id']:r for r in rows['eos025'] if r['family']==family};assert c.keys()==t.keys()
 pairs[family]=dict(control_correct=sum(r['strict'] for r in c.values()),treatment_correct=sum(r['strict'] for r in t.values()),gains=sum(t[k]['strict'] and not c[k]['strict'] for k in c),losses=sum(c[k]['strict'] and not t[k]['strict'] for k in c),identical_responses=sum(c[k]['response']==t[k]['response'] for k in c))
ledger_summary={k:ledger[k] for k in ['updates','positions','sft_targets','narrative_targets','model_seconds','peak_rss']}
summary=dict(status='COMPLETED',paired=pairs,passed_fit_gate=result['passed_fit_gate'],control_reproduces_previous_fit_weights_exactly=exact_model,control_reproduces_previous_fit_moments_exactly=exact_moments,ledger=ledger_summary,prior_updates=214,lifetime_updates_in_three_studies=614,no_promotion=True)
save(ROOT/'comparison.json',summary)
save(ROOT/'audit.json',dict(status='PASS_FOR_INTEGRITY_AND_ACCOUNTING',checks=checks,frozen_files_verified=len(checks),all_frozen_hashes_match=True,reservations_reconcile=True,active_model_segment=False,control_checkpoint_exactly_reproduced=True,artifact_bytes=sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file()),closing_script_sha256=sha(Path(__file__))))
print(json.dumps(summary,indent=2))
