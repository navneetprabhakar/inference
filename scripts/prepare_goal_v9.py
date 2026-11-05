"""Freeze reviewed teacher mixture and audit actual accumulated-update coefficients."""
import hashlib,json,random
from pathlib import Path
from collections import defaultdict
import numpy as np
from tokenizers import Tokenizer
from sft_common import ROOT,encode_episode
from audit_teacher_fixture_trajectories import audit

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
def main():
 out=ROOT/'data/eight-hour-improvement-v9';run=ROOT/'runs/eight-hour-improvement-v9';out.mkdir(parents=True,exist_ok=True);run.mkdir(parents=True,exist_ok=True)
 if (out/'manifest.json').exists():raise RuntimeError('Already frozen')
 old=ROOT/'data/eight-hour-improvement-v8-r3/records.jsonl';fresh=ROOT/'data/eight-hour-teacher-reviewed-v2/records.jsonl';qa=ROOT/'data/eight-hour-improvement-v7/records.jsonl'
 freshmanifest=json.loads((fresh.parent/'manifest.json').read_text());assert sha(fresh)==freshmanifest['files']['records.jsonl']
 assert not json.loads((fresh.parent/'near-leakage-audit.json').read_text())['warnings']
 shares={'reviewed_natural':.40,'short_upstream':.10,'fresh_authored':.30,'grounded_qa':.10,'positive_tools':.05,'tool_boundaries':.05}
 groups={k:[] for k in shares}
 for r in load(old):
  if r['training_group']!='fresh_authored':groups[r['training_group']].append(r)
 groups['fresh_authored']=load(fresh);groups['grounded_qa']=[r for r in load(qa) if r['training_group']=='grounded_qa']
 tok=Tokenizer.from_file(str(ROOT/'data/sft-v3/tokenizer.json'));rows=[];ids=[];masks=[];lengths=[];targets=[];indices={k:[] for k in groups}
 for k,records in groups.items():
  for r in records:
   encoded=encode_episode(tok,r['messages'])
   if encoded is None:raise RuntimeError('Unencodable '+r['id'])
   token,mask,n=encoded;indices[k].append(len(rows));rows.append({**r,'training_group':k});ids.append(token);masks.append(mask);lengths.append(n);targets.append(int(mask.sum()))
 assert len({r['id'] for r in rows})==len(rows)
 rng=random.Random(2026110310);bags={};emitted={k:0 for k in groups};order=[];inputs=0
 while inputs<4000000:
  k=min(groups,key=lambda k:emitted[k]/shares[k])
  if not bags.get(k):bags[k]=indices[k].copy();rng.shuffle(bags[k])
  i=bags[k].pop();order.append(i);inputs+=lengths[i]-1;emitted[k]+=targets[i]
 batches=[]
 for j in range(0,len(order),64):
  block=sorted(order[j:j+64],key=lambda i:lengths[i]);batches.extend([block[k:k+2] for k in range(0,len(block),2) if len(block[k:k+2])==2])
 # Model the exact first-stage update grouping without running the model.
 coeff=defaultdict(float);actual=defaultdict(int);tokens=0;updates=0;pending=defaultdict(int);pending_count=0
 for ix in batches:
  for i in ix:k=rows[i]['training_group'];pending[k]+=targets[i];pending_count+=targets[i];actual[k]+=targets[i];tokens+=lengths[i]-1
  if pending_count>=512 or tokens>=1000000:
   for k,n in pending.items():coeff[k]+=n/pending_count
   updates+=1;pending=defaultdict(int);pending_count=0
  if tokens>=1000000:break
 auditmix={'first_stage_input_tokens':tokens,'optimizer_updates':updates,'supervised_tokens':sum(actual.values()),'supervised_token_shares':{k:actual[k]/sum(actual.values()) for k in shares},'average_normalized_update_loss_coefficients':{k:coeff[k]/updates for k in shares},'target_supervised_tokens_per_update':512}
 auditmix['maximum_share_deviation']=max(abs(auditmix['supervised_token_shares'][k]-auditmix['average_normalized_update_loss_coefficients'][k]) for k in shares)
 if auditmix['maximum_share_deviation']>.03:raise RuntimeError('Mixture coefficient deviation >3points '+str(auditmix))
 (out/'records.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n' for r in rows));np.savez_compressed(out/'episodes.npz',ids=np.stack(ids),mask=np.stack(masks),length=np.array(lengths,np.int32));(out/'order.json').write_text(json.dumps({'order':order,'seed':2026110310}));(out/'optimization-mix-audit.json').write_text(json.dumps(auditmix,indent=2)+'\n')
 replay=audit([out/'records.jsonl']);(out/'fixture-context-audit.json').write_text(json.dumps(replay,indent=2)+'\n');assert not replay['errors']
 manifest={'records':len(rows),'group_records':{k:len(v) for k,v in groups.items()},'desired_supervised_token_mix':shares,'scheduled_input_tokens':inputs,'scheduled_supervised_tokens':emitted,'source_hashes':{str(p.relative_to(ROOT)):sha(p) for p in [old,fresh,qa,fresh.parent/'manifest.json']},'files':{n:sha(out/n) for n in ['records.jsonl','episodes.npz','order.json']},'limitation':'Previouslyreviewedcorpus plus191parent-reviewednewteacherdialogues, structuredQAandtoolfixtures. No newindependenthumanreview. Weightingfix,data,andLRchange together; recoverytrialnotcausalablation.'};(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 cfg={'run_dir':str(run.relative_to(ROOT)),'base_checkpoint':'runs/eight-hour-improvement-v8/training/checkpoint-000001000188-1793652367950686000','data_dir':str(out.relative_to(ROOT)),'deadline_unix':1793672065,'max_nonpadding_input_tokens':1000000,'max_active_seconds':14400,'learning_rate':1e-5,'batch_size':2,'supervised_tokens_per_update':512,'checkpoint_every_steps':100,'min_free_disk_bytes':15*2**30,'max_mlx_allocator_bytes':12*2**30,'seed':2026110310,'initial_stage_cap':1000000,'potential_continuation_cap':4000000};(run/'training-config.json').write_text(json.dumps(cfg,indent=2)+'\n');print(json.dumps({'groups':manifest['group_records'],'mix_audit':auditmix},indent=2))
if __name__=='__main__':main()
