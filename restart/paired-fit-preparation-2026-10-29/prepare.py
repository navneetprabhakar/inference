"""CPU-only proposal builder; contains no training entry point."""
import json,random,copy,sys,hashlib,collections
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[1];C=P.parent/'contrastive-curriculum-2026-10-29';sys.path.insert(0,str(P.parent/'phase-a-2026-10-28'))
from build import serial,sp

def read(p):return json.loads(p.read_text())
def save(n,x):(P/n).write_text(json.dumps(x,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def generation_cost(rows):
 positions=forwards=turns=0;maximum=0
 for r in rows:
  history=[];prior=0
  for t in range(len(r['messages'])//2):
   history.append(r['messages'][2*t]);n=len(serial(history)[0])-prior+32*t;assert n+32<=256
   positions+=32*n+496;forwards+=32;turns+=1;maximum=max(maximum,n+32)
   a=r['messages'][2*t+1];history.append(a);prior+=len(sp.encode(a['content']))+1
 return dict(positions=positions,forwards=forwards,turns=turns,max_context=maximum)
def main():
 assert not (P/'freeze.json').exists(),'FROZEN_PROPOSAL'
 for n,h in read(C/'freeze.json')['files'].items():assert sha(ROOT/n)==h,n
 views=[read(C/f'private/view-{i}.json') for i in [0,1]];families=list(dict.fromkeys(r['scenario']['family'] for r in views[0]));indices=[]
 for block in range(4):
  entities=list(range(8));random.Random(291030+block).shuffle(entities)
  for offset,e in enumerate(entities):
   j=block*8+offset;indices.append(8*j+(e-j//2)%8)
 rows=[];lookup={};repairs=[]
 for view,source in enumerate(views):
  for r in source:
   if int(r['id'].split('-')[1]) not in indices:continue
   x=copy.deepcopy(r);x['source_id']=x['id'];x['id']=f'v{view}-'+x['id'];m=x['messages'][0];original=m['content']
   if x['scope']=='single':
    for a,b in [('From the two belongings, select','From the supplied record, select'),('Choose the '+x['scenario']['item']+' from the two objects','Find the '+x['scenario']['item']+' in the supplied record'),('Do not summarize both objects','Do not summarize the record')]:m['content']=m['content'].replace(a,b)
   if original!=m['content']:repairs.append(dict(id=x['id'],before=original,after=m['content']))
   x['ids'],x['mask']=serial(x['messages']);assert sum(x['mask'])==sum(r['mask']);lookup[view,x['source_id']]=len(rows);rows.append(x)
 schedules={a:[] for a in ['paired','shuffled']}
 for epoch in range(2):
  for view in [0,1]:
   deck=indices.copy();random.Random(291100+2*epoch+view).shuffle(deck);batches=[]
   for i in deck:
    for side in ['before','after']:batches.append([lookup[view,f'{f}-{i:03}-{side}'] for f in families])
   schedules['paired']+=batches
   random.Random(291200+2*epoch+view).shuffle(batches);schedules['shuffled']+=batches
 dev=[r for r in read(C/'private/unscored-development-candidate.json') if int(r['id'].split('-')[1])%4==0]
 replay=read(P.parent/'runner-readiness-2026-10-29/replay.json')
 save('private/fit-records.json',rows);save('private/development.json',dev);save('private/schedules.json',schedules);save('private/replay-indices.json',replay['indices'][:256]);save('repairs.json',repairs)
 targets=[];padding=[];adjacency={}
 for arm,schedule in schedules.items():
  assert len(schedule)==256
  assert set(collections.Counter(i for b in schedule for i in b).values())=={2}
  for b in schedule:assert len(b)==8 and len({rows[i]['scenario']['family'] for i in b})==8
  targets.append(sum(sum(rows[i]['mask']) for b in schedule for i in b));padding.append(sum(8*max(len(rows[i]['ids'])-1 for i in b) for b in schedule))
  adjacency[arm]=sum(rows[schedule[t][0]]['pair']==rows[schedule[t+1][0]]['pair'] for t in range(255))
 assert targets[0]==targets[1] and padding[0]==padding[1]
 for start in range(0,256,64):assert collections.Counter(map(tuple,schedules['paired'][start:start+64]))==collections.Counter(map(tuple,schedules['shuffled'][start:start+64]))
 for view in [0,1]:
  for f in families:
   rs=[r for r in rows if r['view']==view and r['scenario']['family']==f];assert len(rs)==64;assert set(collections.Counter(r['scenario']['item'] for r in rs).values())=={8}
 key=lambda r:tuple(m['content'] for m in r['messages'] if m['role']=='user');assert not {key(r) for r in rows}&{key(r) for r in dev}
 fit_cost=generation_cost(rows);dev_cost=generation_cost(dev);forwards=3*(fit_cost['forwards']+dev_cost['forwards'])
 # Train + one teacher-forced audit over all presentation records at source and endpoints + three native NLLs.
 train_positions=2*padding[0]+512*2048
 teacher_positions=3*sum(8*max(len(rows[i]['ids'])-1 for i in b) for b in schedules['paired'][:128])
 positions=train_positions+teacher_positions+3*(fit_cost['positions']+dev_cost['positions'])+3*131072
 timing=read(P.parent/'lr-feasibility-2026-10-29/timing.json');cal=read(P.parent/'lr-feasibility-2026-10-29/result.json')
 p95=max(x['step_seconds']['p95'] for x in cal['results'] if x['replay']==.5)
 projection=1.25*(512*p95+forwards*max(x['seconds_per_forward'] for x in timing['samples'])+(192+384)*max(timing['narrative_batch_seconds'])+120)
 old=read(P.parent/'retained-screen-2026-10-29/result.json');diag=read(P.parent/'binding-diagnosis-2026-10-29/result.json');carry={k:old['charges'][k]+diag['charges'][k] for k in old['charges']};seconds=old['seconds']+diag['seconds']
 save('carry-forward.json',dict(charges=carry,seconds=seconds,includes='Retained screen inclusive of612 calibration updates, plus inference diagnosis once. Earlier campaign/engineering usage remains separately recorded, not erased.',sources={str((P.parent/n).relative_to(ROOT)):sha(P.parent/n) for n in ['retained-screen-2026-10-29/private/study.sqlite','binding-diagnosis-2026-10-29/private/inference.sqlite']}))
 save('budget.json',dict(authorized=False,new_update_cap=512,updates_per_arm=256,new_active_seconds_cap=3600,new_position_cap=20000000,new_assistant_target_cap=2*targets[0],new_narrative_target_cap=1048576,projection_seconds=projection,positions_upper_bound=positions,training_positions=train_positions,teacher_forced_positions=teacher_positions,fit_generation=fit_cost,development_generation=dev_cost,generation_forwards_upper_bound=forwards,carry_forward_seconds=seconds,aggregate_active_seconds_cap=seconds+3600,aggregate_update_cap=carry['updates']+512,aggregate_position_cap=carry['positions']+20000000,artifact_new_bytes_cap=2147483648))
 assert positions<=20000000 and projection<=3600
 save('checks.json',dict(status='PASS',training_executed=False,fit_semantic_records=512,fit_presentation_records=len(rows),pairs_per_family=32,development_records=len(dev),repairs=len(repairs),same_batch_multiset_per_view_epoch=True,same_targets_per_arm=targets[0],same_padded_positions_per_arm=padding[0],adjacent_pair_transitions=adjacency,fit_indices=indices,generated_context_checks=True,parameter_loading=False))
 print(json.dumps(read(P/'budget.json'),indent=2));print(read(P/'checks.json'))
if __name__=='__main__':main()
