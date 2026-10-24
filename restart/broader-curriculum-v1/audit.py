"""Read-only evidence audit. No model execution or threshold changes."""
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
result=read(R/'result.json');rows=read(R/'private/final-test-responses.json');cases={r['id']:r for r in read(R/'private/test-encoded.json')};train=read(R/'private/training.json');schedule=read(R/'private/schedules.json')['broad'][:result['updates_consumed']]
for path,digest in read(R/'freeze.json')['files'].items():assert sha(P/path)==digest,path
assert len(rows)==80
contexts={};unique={};complete={k:True for k in cases}
for r in rows:
 c=cases[r['id']];assert r['expected']==c['messages'][2*r['turn']+1]['content']
 if r['rule']=='value':correct=re.findall(r'\w+',r['response'].casefold())==re.findall(r'\w+',r['expected'].casefold())
 else:correct=r['response'].strip().endswith('?') and r['response'].count('?')==1 and len(r['response'].split())<=16 and any(k in r['response'].casefold() for k in c['keywords'])
 assert correct==r['correct'];assert r['eos']==(r['stop_token']==2)
 complete[r['id']] &= correct and r['eos']
 context=contexts.setdefault(r['id'],[]);context.append(('user',r['user']));unique[tuple(context)]=r;context.append(('assistant',r['response']))
groups={}
for c in cases.values():
 if c['group']:groups.setdefault(c['group'],[]).append(c['id'])
assert all(len(g)==2 for g in groups.values()) and len(groups)==24
assert sum(all(complete[k] for k in group) for group in groups.values())==result['test']['counterfactual_pairs_correct']
assert sum(r['correct'] and r['eos'] for r in rows)==result['test']['correct_and_eos_turns']
assert sum(sum(train[i]['mask']) for batch in schedule for i in batch)==result['sft_targets_consumed']
assert len(schedule)*2048==result['replay_targets_consumed']
indices={i for batch in schedule for i in batch};nnew=read(R/'data-receipt.json')['counts']['new_training']['conversations']
subskills={}
for label,selected in [('delayed_final_query',[r for r in rows if cases[r['id']]['family']=='delayed_update' and r['turn']==2]),('answer_present',[r for r in rows if cases[r['id']]['family']=='answerability' and cases[r['id']]['answer_present']]),('answer_absent',[r for r in rows if cases[r['id']]['family']=='answerability' and not cases[r['id']]['answer_present']])]:subskills[label]=dict(turns=len(selected),correct_and_eos=sum(r['correct'] and r['eos'] for r in selected))
chosen=result['selected'];retained=chosen['sft_targets'] if chosen else 0
receipt=dict(status='PASS',immutable_inputs_unchanged=True,test_scores_recomputed=True,unique_fresh_prefixes=len(unique),unique_correct_and_eos=sum(r['correct'] and r['eos'] for r in unique.values()),subskills=subskills,updates_consumed=result['updates_consumed'],selected_new_updates=chosen['updates'] if chosen else 0,new_sft_targets_consumed=result['sft_targets_consumed'],new_sft_targets_retained=retained,new_sft_targets_discarded=result['sft_targets_consumed']-retained,new_replay_targets_consumed=result['replay_targets_consumed'],new_replay_targets_retained=chosen['replay_targets'] if chosen else 0,unique_new_training_conversations_consumed=sum(i<nnew for i in indices),unique_old_training_conversations_consumed=sum(i>=nnew for i in indices),selected_checkpoint_sha256=chosen['checkpoint_sha256'] if chosen else None,selected_checkpoint_hash_verified=sha(P/chosen['checkpoint'])==chosen['checkpoint_sha256'] if chosen else None,artifact_bytes=sum(p.stat().st_size for p in R.rglob('*') if p.is_file()),test_response_sha256=sha(R/'private/final-test-responses.json'),retention_response_sha256=sha(R/'private/final-retention-responses.json'),parent_unchanged=result['parent_unchanged'],original_foundation_unchanged=result['original_foundation_unchanged'],promotion=False,hard_stop=result['stop'])
assert receipt['artifact_bytes']<5*1024**3
if (R/'rejected-assessment.json').exists():
 rejected=read(R/'rejected-assessment.json');rejected_rows=read(R/'private/rejected-fresh-test-responses.json');checkpoint=read(R/'result.json')['history'][-1]
 assert sha(P/rejected['checkpoint'])==checkpoint['checkpoint_sha256']
 for rr in rejected_rows:
  cc=cases[rr['id']]
  if rr['rule']=='value':valid=re.findall(r'\w+',rr['response'].casefold())==re.findall(r'\w+',rr['expected'].casefold())
  else:valid=rr['response'].strip().endswith('?') and rr['response'].count('?')==1 and len(rr['response'].split())<=16 and any(k in rr['response'].casefold() for k in cc['keywords'])
  assert valid==rr['correct'] and rr['eos']==(rr['stop_token']==2)
 assert sum(rr['correct'] and rr['eos'] for rr in rejected_rows)==rejected['fresh_test']['correct_and_eos_turns']
 child_complete={k:all(x['correct'] and x['eos'] for x in rejected_rows if x['id']==k) for k in cases}
 assert sum(all(child_complete[k] for k in group) for group in groups.values())==rejected['fresh_test']['counterfactual_pairs_correct']
 rejected_retention=read(R/'private/broad-retention-100-responses.json')
 assert sum(x['correct'] and x['eos'] for x in rejected_retention)==64
 assert rejected['retention']['correct_and_eos_turns']==64 and result['selected'] is None
 oldtargets=sum(sum(train[i]['mask']) for batch in schedule for i in batch if i>=nnew)
 receipt.update(primary_result_test_scope='Unchanged parent fallback, not the rejected candidate; no new eligible checkpoint.',rejected_checkpoint_hash_verified=True,rejected_fresh_test_scores_recomputed=True,rejected_fresh_correct_and_eos=rejected['fresh_test']['correct_and_eos_turns'],old_training_target_exposures=oldtargets,new_training_target_exposures=result['sft_targets_consumed']-oldtargets,old_target_fraction=oldtargets/result['sft_targets_consumed'],aggregate_positions_including_rejected_assessment=rejected['aggregate_positions'])
 assert rejected['aggregate_positions']<12000000 and rejected['new_updates']==0 and not rejected['selection_changed']
(R/'audit.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
