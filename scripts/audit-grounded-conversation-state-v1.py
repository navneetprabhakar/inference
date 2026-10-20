"""Verify terminal FP32 weights/moments, exact consumed schedule and every raw charge."""
# Creator: Navneet Prabhakar
import json,sqlite3
from pathlib import Path
import numpy as np
from safetensors.numpy import load_file
from slm.common import checkpoint
from slm.common.training import Recipe,validate_boundary
from slm.data.grounded_conversation_research import GroundedBatches
from slm.data.stream_hash import sha
ROOT=Path('data/grounded-conversation-run-v1');PLAN=Path('configs/grounded-conversation-run-v1.json')
def main():
 output=ROOT/'state-audit.json'
 if output.exists():raise FileExistsError(output)
 p=json.loads(PLAN.read_text());done=json.loads((ROOT/'training-completion.json').read_text());s=json.loads((ROOT/'terminal/state.json').read_text());manifest=json.loads((ROOT/'terminal/manifest.json').read_text())
 if not done['complete'] or done['terminal_manifest_sha256']!=sha(ROOT/'terminal/manifest.json') or s['recipe']!=p['recipe']:raise ValueError('Terminal complete exact recipe required')
 for name,h in p['inputs'].items():
  if sha(name)!=h:raise ValueError('Frozen source changed: '+name)
 if set(manifest)!={'state.json','optimizer.safetensors','model/model.safetensors','model/config.json','model/manifest.json'}:raise ValueError('Complete terminal training state required')
 for name,h in manifest.items():
  if sha(ROOT/'terminal'/name)!=h:raise ValueError('Terminal state checksum mismatch')
 config,weights=checkpoint.load(ROOT/'terminal/model');raw=load_file(str(ROOT/'terminal/optimizer.safetensors'))
 if set(raw)!={f'{slot}:{k}' for k in weights for slot in ('m','v')}:raise ValueError('Missing optimizer tensor')
 for name,v in raw.items():
  if v.dtype!=np.float32 or v.shape!=weights[name.split(':',1)[1]].shape or not np.isfinite(v).all() or (name.startswith('v:') and (v<0).any()):raise ValueError('Invalid moment')
 if s['precision']!='fp32' or s['dataset_hash']!=p['schedule_sha256']:raise ValueError('Precision/data state mismatch')
 db=sqlite3.connect('file:'+str((ROOT/'physical.sqlite').resolve())+'?mode=ro',uri=True);charges=db.execute('SELECT phase,cursor,positions,status FROM charges ORDER BY cursor').fetchall();db.close();updates=[json.loads(l) for l in (ROOT/'updates.jsonl').open()]
 with GroundedBatches(p['data'],p['tokenizer'],p['schedule_sha256']) as b:
  validate_boundary(Recipe(**p['recipe']),b,s['step'],s['cursor'],s['tokens'],s['supervised_tokens']);cursor=0;expected=[]
  for u in updates:
   end=min(cursor+p['recipe']['accumulation_steps'],len(b));positions=b.counts(end)[0]-b.counts(cursor)[0];expected.append(('conversation_sft',cursor,positions,'complete'))
   if (u['cursor'],u['tokens'],u['supervised_tokens'])!=(end,*b.counts(end)):raise ValueError('Update/prefix counters differ')
   cursor=end
  if cursor!=s['cursor'] or charges!=expected or len(charges)!=s['step']:raise ValueError('Missing/uncertain/retried physical gradient charge')
 prior=sum(r['positions'] for r in p['sealed_raw_priors']);actual=sum(r[2] for r in charges)
 if (done['new_physical_positions'],done['cumulative_physical_positions'])!=(actual,prior+actual) or actual>p['maximum_remaining_sft_positions']:raise ValueError('Distinct raw budget mismatch')
 for priorledger in p['sealed_raw_priors']:
  if sha(priorledger['path'])!=priorledger['sha256']:raise ValueError('Prior ledger modified')
 sourceconfig,sourceweights=checkpoint.load(p['source_model']);changed=sum(not np.array_equal(v,sourceweights[k]) for k,v in weights.items())
 if not changed or config!=sourceconfig:raise ValueError('Actual learned same-architecture weights required')
 result=dict(creator='Navneet Prabhakar',complete=True,passed=True,plan_sha256=sha(PLAN),all_frozen_inputs_unchanged=len(p['inputs']),terminal_model_manifest_sha256=sha(ROOT/'terminal/model/manifest.json'),terminal_training_manifest_sha256=sha(ROOT/'terminal/manifest.json'),weights_tensors=len(weights),fp32_parameters=sum(v.size for v in weights.values()),finite_optimizer_tensors=len(raw),changed_weight_tensors=changed,steps=s['step'],cursor=s['cursor'],new_physical_positions=actual,new_supervised_positions=s['supervised_tokens'],cumulative_recovery_physical_positions=prior+actual,raw_physical_ledger_sha256=sha(ROOT/'physical.sqlite'),all_gradient_charges_complete=True,source_model_preserved_sha256=sha(Path(p['source_model'])/'manifest.json'),retention_termination=done['termination'],no_capability_claim=True)
 output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
