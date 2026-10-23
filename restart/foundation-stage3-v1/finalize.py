"""Finalize only the approved endpoint. No model imports, training or repairs."""
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
  text=v['response'].replace('’',"'").lower();words=re.findall(r"[a-z]+(?:'[a-z]+)?|[0-9]+",text);grams=[tuple(words[i:i+4]) for i in range(max(0,len(words)-3))];counts=collections.Counter(grams);frac=sum(n-1 for n in counts.values())/len(grams) if grams else 0
  sentences=[' '.join(re.findall(r"[a-z]+(?:'[a-z]+)?|[0-9]+",s)) for s in re.split(r'[.!?]+',text)];mx=max(collections.Counter(s for s in sentences if s).values(),default=0)
  out[v['id']]=dict(repeated_fourgram_fraction=frac,maximum_identical_sentence_count=mx,degenerate=frac>.20 or mx>=3)
 return out

def main():
 c=read(ROOT/'contract.json');proposal=read(ROOT/'proposal.json');approval=read(ROOT/'approval.json');clock=read(ROOT/'clock.json');raw=read(ROOT/'stage3-result.json')
 assert c['current_stage_training_authorized'] and sha(ROOT/'proposal.json')==approval['proposal_sha256']
 assert raw['additional_updates']==1144 and raw['additional_training_targets']==149946368
 checkpoint=BASE/raw['checkpoint']['path'];assert sha(checkpoint)==raw['checkpoint']['sha256']
 assert raw['checkpoint']['optimizer_step']==2889 and raw['checkpoint']['completed_targets']==378667008 and raw['checkpoint']['verified_exact_CPU_reload']
 assert sha(BASE/'restart/foundation-stage2-v1/stage2-checkpoint.pt')==c['reference']['checkpoint_sha256']
 resources=[read(ROOT/(name+'-supervisor.json')) for name in ['train','teacher-stage3-evaluation','serialized-reference']]
 assert all(v['worker_reaped'] and not v['stop_reason'] for v in resources)
 assert all(resources[i]['returncode']==0 for i in [0,1])
 # A failed read-only verifier is reported as a failed gate, never silently
 # repaired or counted as parity success. Its one allowed attempt is consumed.
 reference_path=ROOT/'serialized-reference.json'
 if reference_path.exists():
  reference=read(reference_path)
 else:
  assert resources[2]['returncode']!=0
  log=ROOT/'serialized-reference.log'
  reference=dict(status='NOT_VERIFIED_VERIFIER_FAILED',failure_log_sha256=sha(log),failure=log.read_text().splitlines()[-1],attempts=1,rerun_authorized=False)
 reference_passed=resources[2]['returncode']==0 and reference['status']=='PASS' and reference.get('absolute_difference',math.inf)<=.02
 pins=read(ROOT/'source-pins.json');assert sha(ROOT/'source-pins.json')==proposal['source_pins_sha256']
 assert all(sha(ROOT/name)==digest for name,digest in pins.items())
 prior=read(BASE/'restart/foundation-stage2-v1/report.json');rows=read(ROOT/'stage3-evaluation/stories.json');oldrows=read(BASE/'restart/foundation-stage2-v1/stage2-evaluation/stories.json');primary=read(ROOT/'primary-review.json');grades=read(ROOT/'teacher-review.json')['reviews'];blind=read(ROOT/'teacher-blind-map.json')
 assert len(rows)==len(primary['reviews'])==100 and len(grades)==len(blind)==200
 metrics={'current':behavior(rows),'prior':behavior(oldrows)};teacher_ids={k:set() for k in metrics}
 for v in grades:
  m=blind[v['id']];stage=m['stage'];sid=m['id']
  if sum(v['scores'])>=8 and min(v['scores'])>0 and not v['contradiction'] and not v['incoherent_sentence'] and not metrics[stage][sid]['degenerate']:teacher_ids[stage].add(sid)
 primary_ids={v['id'] for v in primary['reviews'] if v['coherent'] and not metrics['current'][v['id']]['degenerate']};accepted=primary_ids&teacher_ids['current']
 oldprimary={v['id'] for v in read(BASE/'restart/foundation-stage2-v1/primary-review.json')['reviews'] if v['coherent'] and not metrics['prior'][v['id']]['degenerate']}
 final=raw['evaluation'];baseline=prior['validation']['current_nll'];gain=baseline-final['validation_nll'];degenerate=sum(v['degenerate'] for v in metrics['current'].values())
 checks=dict(validation_nll_gain_at_least_point1=gain>=.10,conservative_coherent_at_least20=len(accepted)>=20,coherence_gain_over_recorded3_at_least10pp=len(accepted)-3>=10,grammar_at_least75=final['grammar_correct']>=75,grounded_at_least42=final['grounded_correct']>=42,degeneration_at_most5=degenerate<=5,correctness_and_resources=reference_passed)
 passed=all(checks.values());status='SUCCESSOR_COMPLETE_DEVELOPMENT_PROGRESS_GATE_PASSED_REVIEW_REQUIRED' if passed else 'SUCCESSOR_COMPLETE_DEVELOPMENT_PROGRESS_GATE_FAILED'
 updates=[json.loads(v) for v in (ROOT/'updates.jsonl').read_text().splitlines()];assert len(updates)==1144 and all(math.isfinite(v['loss']) and math.isfinite(v['gradient_norm']) for v in updates)
 periodic=[json.loads(v) for v in (ROOT/'validation-history.jsonl').read_text().splitlines()];assert len(periodic)==11 and all(math.isfinite(v['nll']) and v['nll']<=baseline+.20 for v in periodic)
 used=sqlite3.connect(ROOT/'work.sqlite').execute('select sum(positions) from work').fetchone()[0];assert used<=160000000 and used+c['prior_new_run_positions_charged']<=320000000
 teacher=read(ROOT/'teacher-receipt.json');observed=teacher['usage']['output_tokens']+teacher['usage']['reasoning_output_tokens'];assert observed<=28020 and teacher['requests']==1 and teacher['requested_model']=='gpt-6-sol'
 end=updates[-1]['seconds'];boundary=max(0,end-1800);start=next(v for v in updates if v['seconds']>=boundary);last30=(updates[-1]['targets']-start['targets'])/(end-start['seconds'])
 options=read(ROOT/'stage3-evaluation/option-scores.json');unique={}
 for v in options:
  if v['kind']=='grammar':unique[(v['prefix'],tuple(sorted(v['options'])))]=v
 result=dict(status=status,approved_scope='Single1144update/149946368target successor; stop even if passed',parameters=15191712,checkpoint=raw['checkpoint'],additional_training_targets=149946368,total_training_targets=378667008,total_optimizer_step=2889,
 validation=dict(baseline_nll=baseline,current_nll=final['validation_nll'],improvement_nats=gain,fixed_targets=131072,periodic_checks=11),grammar=dict(baseline_correct=75,correct=final['grammar_correct'],cases=100,unique_pairs=45,unique_correct=sum(v['correct'] for v in unique.values())),grounded=dict(baseline_correct=42,correct=final['grounded_correct'],cases=100,choices=4),
 narrative=dict(recorded_baseline_conservative=3,paired_regraded_baseline_conservative=len(oldprimary&teacher_ids['prior']),paired_regraded_baseline_teacher=len(teacher_ids['prior']),primary=len(primary_ids),teacher=len(teacher_ids['current']),conservative=len(accepted),conservative_ids=sorted(accepted),cases=100,families=20,degenerate=degenerate,cases_with_generated_BOS=sum(bool(v['BOS_positions']) for v in rows),prior_regrading_does_not_replace_recorded_baseline=True),
 progress_gate=dict(passed=passed,checks=checks),independent_saved_checkpoint_reference=reference,teacher_receipt=teacher,teacher_aggregate_requests=4,teacher_aggregate_observed_output_and_reasoning_tokens=19980+observed,teacher_original_observed_token_cap=48000,
 training_seconds=end,average_targets_per_second=149946368/end,final30_targets_per_second=last30,elapsed_since_approval_seconds=time.time()-clock['start_epoch'],first25_mean_loss=sum(v['loss'] for v in updates[:25])/25,last25_mean_loss=sum(v['loss'] for v in updates[-25:])/25,processed_positions=used,prior_processed_positions=c['prior_new_run_positions_charged'],cumulative_original_positions=used+c['prior_new_run_positions_charged'],original_position_cap=320000000,peak_process_tree_RSS_GiB=max(v['peak_RSS_bytes'] for v in resources)/1024**3,additional_global_swap_bytes=max(v['maximum_additional_swap_bytes'] for v in resources),all_workers_reaped=True,training_sources_unchanged=True,development_only=True,formal_English_gate='NOT_RUN_AND_NOT_PASSED',training_authorized=False,next_stage_authorized=False,conversation_training_authorized=False,full_training_authorized=False,old_failed_gate_preserved=True)
 result.update(training_update_clock_seconds=end,worker_training_seconds_including_initialization=raw['training_seconds'],average_targets_per_second_including_initialization=149946368/raw['training_seconds'],resource_guards_passed=all(not v['stop_reason'] for v in resources),independent_checkpoint_parity_verified=reference_passed,teacher_grade_instability_disclosure='Same prior checkpoint scored14/100 in the earlier Sol review and4/100 in this paired Sol regrade; absolute agent grades are unstable research diagnostics.')
 save(ROOT/'behavior-metrics.json',metrics);save(ROOT/'report.json',result);save(ROOT/'stage.json',dict(status=status,training_authorized=False,next_stage_authorized=False))
 save(ROOT/'global-stop.json',dict(reason='APPROVED_SUCCESSOR_CAP_REACHED_OWNER_REVIEW_REQUIRED' if passed else 'SUCCESSOR_DEVELOPMENT_PROGRESS_GATE_FAILED',resource_breach=False,training_authorized=False,next_stage_authorized=False,completed_updates=1144,epoch=time.time()))
 c.update(status='APPROVAL_CONSUMED_STAGE_COMPLETE',current_stage_training_authorized=False);save(ROOT/'contract.json',c)
 statepath=BASE/'restart/execution-v1/CURRENT_WORK.json';state=read(statepath);state['foundation_continuation'].update(status=status,training_authorized=False,next_stage_authorized=False,conversation_training_authorized=False,current_stage='restart/foundation-stage3-v1',checkpoint=raw['checkpoint']['path'],checkpoint_sha256=raw['checkpoint']['sha256'],total_retained_training_targets=378667008,additional_training_targets=149946368,additional_updates=1144,report='restart/foundation-stage3-v1/REPORT.md',all_workers_reaped=True,mandatory_progress_gate_passed=passed,review_hold='restart/foundation-stage3-v1/global-stop.json');state['foundation_successor_preparation'].update(status=status,training_authorized=False);save(statepath,state)
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
