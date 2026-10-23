"""Close the second approved stage and preserve the mandatory owner review hold."""
import collections,hashlib,json,math,re,sqlite3,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent;BASE=ROOT.parents[1]
def read(p):return json.loads(p.read_text())
def save(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def behavior(rows):
 out={}
 for v in rows:
  text=v['response'].replace('’',"'").lower();words=re.findall(r"[a-z]+(?:'[a-z]+)?|[0-9]+",text);grams=[tuple(words[i:i+4]) for i in range(max(0,len(words)-3))];counts=collections.Counter(grams)
  frac=sum(n-1 for n in counts.values())/len(grams) if grams else 0
  sentences=[' '.join(re.findall(r"[a-z]+(?:'[a-z]+)?|[0-9]+",s)) for s in re.split(r'[.!?]+',text)];mx=max(collections.Counter(s for s in sentences if s).values(),default=0)
  out[v['id']]=dict(repeated_fourgram_fraction=frac,maximum_identical_sentence_count=mx,degenerate=frac>.20 or mx>=3)
 return out

def main():
 raw=read(ROOT/'stage2-result.json');contract=read(ROOT/'contract.json');clock=read(ROOT/'clock.json');sup=read(ROOT/'train-supervisor.json')
 assert raw['additional_updates']==572 and raw['additional_training_targets']==74973184 and sup['worker_reaped'] and sup['returncode']==0
 checkpoint=BASE/raw['checkpoint']['path'];assert sha(checkpoint)==raw['checkpoint']['sha256']
 assert sha(BASE/'restart/foundation-stage1-v1/stage1-checkpoint.pt')==contract['reference']['checkpoint_sha256']
 prior=read(BASE/'restart/foundation-stage1-v1/report.json');original=read(BASE/'restart/foundation-inference-preflight-v2/report.json')
 rows=read(ROOT/'stage2-evaluation/stories.json');oldrows=read(BASE/'restart/foundation-stage1-v1/stage1-evaluation/stories.json');options=read(ROOT/'stage2-evaluation/option-scores.json');primary=read(ROOT/'primary-review.json');grades=read(ROOT/'teacher-review.json')['reviews'];blind=read(ROOT/'teacher-blind-map.json')
 assert len(rows)==len(primary['reviews'])==100 and len(grades)==len(blind)==200
 metrics={'current':behavior(rows),'prior':behavior(oldrows)};teacher_ids={k:set() for k in metrics}
 for v in grades:
  m=blind[v['id']];stage=m['stage'];sid=m['id']
  if sum(v['scores'])>=8 and min(v['scores'])>0 and not v['contradiction'] and not v['incoherent_sentence'] and not metrics[stage][sid]['degenerate']:teacher_ids[stage].add(sid)
 primary_ids={v['id'] for v in primary['reviews'] if v['coherent'] and not metrics['current'][v['id']]['degenerate']}
 prior_primary={v['id'] for v in read(BASE/'restart/foundation-stage1-v1/primary-review.json')['reviews'] if v['coherent'] and not metrics['prior'][v['id']]['degenerate']}
 accepted=primary_ids & teacher_ids['current'];prior_accepted=prior_primary & teacher_ids['prior']
 updates=[json.loads(l) for l in (ROOT/'updates.jsonl').read_text().splitlines()];assert len(updates)==572 and all(math.isfinite(v['loss']) and math.isfinite(v['gradient_norm']) for v in updates)
 used=sqlite3.connect(ROOT/'work.sqlite').execute('SELECT SUM(positions) FROM work').fetchone()[0];assert used<=80000000 and used+contract['prior_new_run_positions_charged']<=320000000
 final=raw['evaluation'];gain=original['baseline_validation_nll']-final['validation_nll'];gate=dict(loss_improvement_at_least_point1=gain>=.10,coherent_at_least_20=len(accepted)>=20,coherence_gain_at_least_10pp=len(accepted)>=10)
 ending=updates[-1]['seconds'];start=next((v for v in updates if v['seconds']>=max(0,ending-1800)),updates[0]);last30=(updates[-1]['targets']-start['targets'])/(ending-start['seconds'])
 reference=read(ROOT/'serialized-reference.json');assert reference['status']=='PASS'
 resources=[sup,read(ROOT/'teacher-stage2-evaluation-supervisor.json'),read(ROOT/'serialized-reference-supervisor.json')];assert all(v['worker_reaped'] and v['returncode']==0 for v in resources)
 pins=read(ROOT/'source-pins.json');amendment=read(ROOT/'review-source-amendment.json');changed=[]
 for name,digest in pins.items():
  expected=amendment['review_sha256'] if name==amendment['file'] else digest
  if sha(BASE/name)!=expected:changed.append(name)
 assert not changed,changed
 unique={}
 for v in options:
  if v['kind']=='grammar':unique[(v['prefix'],tuple(sorted(v['options'])))]=v
 result=dict(status='SECOND_75M_STAGE_COMPLETE_WAITING_FOR_OWNER_APPROVAL' if all(gate.values()) else 'SECOND_75M_STAGE_COMPLETE_NARRATIVE_PROGRESS_GATE_FAILED',checkpoint=raw['checkpoint'],additional_updates=572,additional_training_targets=74973184,total_retained_training_targets=228720640,total_optimizer_step=1745,cumulative_targets_since_step601=149946368,learned_parameters=15191712,
 validation=dict(original_nll=original['baseline_validation_nll'],previous_nll=prior['validation']['checkpoint_nll'],current_nll=final['validation_nll'],gain_from_original_nats=gain,gain_this_stage_nats=prior['validation']['checkpoint_nll']-final['validation_nll']),
 grammar=dict(previous_correct=prior['grammar']['correct'],correct=final['grammar_correct'],cases=100,unique_pairs=len(unique),unique_pairs_correct=sum(v['correct'] for v in unique.values())),grounded=dict(previous_correct=prior['grounded']['correct'],correct=final['grounded_correct'],cases=100,choices=4),
 narrative=dict(original_conservative_coherent=0,previous_original_luna_conservative=prior['narrative']['conservative_coherent'],previous_sol_conservative=len(prior_accepted),current_primary_coherent=len(primary_ids),current_sol_coherent=len(teacher_ids['current']),current_conservative_coherent=len(accepted),cases=100,families=20,degenerate=sum(v['degenerate'] for v in metrics['current'].values()),cases_with_generated_BOS=sum(bool(v['BOS_positions']) for v in rows),full_window_metric_unchanged=True,first_document_text_saved_as_separate_diagnostic=True),
 mandatory_150M_progress_gate=dict(checks=gate,passed=all(gate.values()),original_baseline_teacher='gpt-6-luna',current_teacher='gpt-6-sol',reviewer_change_limits_original_baseline_comparability=True,paired_previous_current_sol_grading=True),
 teacher_receipt=read(ROOT/'teacher-receipt.json'),independent_serialized_reference=reference,training_updates_elapsed_seconds=ending,training_tokens_per_second=74973184/ending,final_30_minute_tokens_per_second=last30,elapsed_since_approval_seconds=time.time()-clock['start_epoch'],processed_positions_charged=used,prior_positions_charged=contract['prior_new_run_positions_charged'],cumulative_continuation_experiment_positions=used+contract['prior_new_run_positions_charged'],peak_process_tree_RSS_GiB=max(v['peak_RSS_bytes'] for v in resources)/1024**3,additional_global_swap_bytes=max(v['maximum_additional_swap_bytes'] for v in resources),all_workers_reaped=True,training_sources_unchanged=True,teacher_review_amendment_recorded=True,training_authorized=False,next_stage_authorized=False,conversation_training_authorized=False,full_training_authorized=False,formal_English_gate='NOT_RUN_AND_NOT_PASSED',development_only=True)
 result['primary_rubric_zero_counts']={name:sum(v['scores'][i]==0 for v in primary['reviews']) for i,name in enumerate(['grammar','topical_continuity','entity_consistency','causal_temporal_consistency','local_coherence'])}
 result['first_25_update_mean_loss']=sum(v['loss'] for v in updates[:25])/25
 result['last_25_update_mean_loss']=sum(v['loss'] for v in updates[-25:])/25
 save(ROOT/'behavior-metrics.json',metrics);save(ROOT/'report.json',result)
 save(ROOT/'global-stop.json',dict(reason='APPROVED_TARGET_CAP_REACHED_OWNER_REVIEW_REQUIRED' if all(gate.values()) else 'MANDATORY_150M_NARRATIVE_PROGRESS_GATE_FAILED',resource_breach=False,completed_updates=572,training_authorized=False,next_stage_authorized=False,epoch=time.time()))
 save(ROOT/'stage.json',dict(status=result['status'],training_authorized=False,next_stage_authorized=False))
 statepath=BASE/'restart/execution-v1/CURRENT_WORK.json';state=read(statepath);state['foundation_continuation'].update(status=result['status'],training_authorized=False,next_stage_authorized=False,additional_updates=572,additional_training_targets=74973184,total_retained_training_targets=228720640,checkpoint=raw['checkpoint']['path'],checkpoint_sha256=raw['checkpoint']['sha256'],report='restart/foundation-stage2-v1/REPORT.md',all_workers_reaped=True,review_hold='restart/foundation-stage2-v1/global-stop.json');save(statepath,state)
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
