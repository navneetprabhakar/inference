"""Report a completed first stage; never launches training or repairs responses."""
import collections,hashlib,json,math,re,sqlite3,time
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parent;BASE=ROOT.parents[1];PRE=BASE/'restart/foundation-inference-preflight-v2'
def read(p):return json.loads(p.read_text())
def save(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def behavior(rows):
 out=[]
 for v in rows:
  text=v['response'].replace('’',"'").lower();words=re.findall(r"[a-z]+(?:'[a-z]+)?|[0-9]+",text);grams=[tuple(words[i:i+4]) for i in range(max(0,len(words)-3))];count=collections.Counter(grams)
  fraction=sum(n-1 for n in count.values())/len(grams) if grams else 0
  sentences=[' '.join(re.findall(r"[a-z]+(?:'[a-z]+)?|[0-9]+",s)) for s in re.split(r'[.!?]+',text)];frequency=collections.Counter(s for s in sentences if s);maximum=max(frequency.values(),default=0)
  out.append(dict(id=v['id'],repeated_fourgram_fraction=fraction,maximum_identical_sentence_count=maximum,degenerate=fraction>.20 or maximum>=3))
 return out

def main():
 raw=read(ROOT/'stage1-result.json');contract=read(ROOT/'contract.json');clock=read(ROOT/'clock.json');sup=read(ROOT/'train-supervisor.json')
 assert raw['additional_updates']==572 and raw['additional_training_targets']==74973184 and sup['worker_reaped'] and sup['returncode']==0
 checkpoint=BASE/raw['checkpoint']['path'];assert sha(checkpoint)==raw['checkpoint']['sha256']
 assert sha(BASE/'restart/mac-native-benchmark-v1/confirmation/checkpoint.pt')==contract['reference']['checkpoint_sha256']
 old=read(PRE/'report.json');rows=read(ROOT/'stage1-evaluation/stories.json');options=read(ROOT/'stage1-evaluation/option-scores.json');teacher=read(ROOT/'teacher-review.json')['reviews'];primary=read(ROOT/'primary-review.json')
 assert len(rows)==len(teacher)==len(primary['reviews'])==100
 metrics=behavior(rows);degenerate={v['id']:v['degenerate'] for v in metrics}
 teacher_ids={v['id'] for v in teacher if sum(v['scores'])>=8 and min(v['scores'])>0 and not v['contradiction'] and not v['incoherent_sentence'] and not degenerate[v['id']]}
 primary_ids={v['id'] for v in primary['reviews'] if v['coherent'] and not degenerate[v['id']]};accepted=primary_ids & teacher_ids
 updates=[json.loads(line) for line in (ROOT/'updates.jsonl').read_text().splitlines()];assert len(updates)==572 and all(math.isfinite(x['loss']) and math.isfinite(x['gradient_norm']) for x in updates)
 used=sqlite3.connect(ROOT/'work.sqlite').execute('SELECT SUM(positions) FROM work').fetchone()[0];assert used<=80000000 and used+contract['prior_new_run_positions_charged']<=320000000
 unique={}
 for s in options:
  if s['kind']=='grammar':unique[(s['prefix'],tuple(sorted(s['options'])))]=s
 final=raw['evaluation'];reduction=old['baseline_validation_nll']-final['validation_nll']
 ending=updates[-1]['seconds'];boundary=max(0,ending-1800);start=next((v for v in updates if v['seconds']>=boundary),updates[0]);last30=(updates[-1]['targets']-start['targets'])/(ending-start['seconds'])
 reference=read(ROOT/'serialized-reference.json');assert reference['status']=='PASS'
 boundary=read(ROOT/'boundary-audit.json');assert boundary['status']=='COMPLETE' and boundary['decoded_matches']==100
 resources=[sup,read(ROOT/'teacher-stage1-evaluation-supervisor.json'),read(ROOT/'serialized-reference-supervisor.json'),read(ROOT/'boundary-audit-supervisor.json')];assert all(v['worker_reaped'] for v in resources)
 result=dict(status='FIRST_75M_STAGE_COMPLETE_WAITING_FOR_OWNER_APPROVAL',complete_local=datetime.now(ZoneInfo('Asia/Kolkata')).isoformat(),checkpoint=raw['checkpoint'],source_checkpoint_unchanged=True,additional_updates=572,additional_training_targets=74973184,total_retained_training_targets=153747456,total_optimizer_step=1173,learned_parameters=15191712,
 validation={'baseline_nll':old['baseline_validation_nll'],'checkpoint_nll':final['validation_nll'],'improvement_nats':reduction,'fixed_targets':131072,'relative_improvement_percent':100*reduction/old['baseline_validation_nll']},
 grammar={'baseline_correct':55,'correct':final['grammar_correct'],'cases':100,'unique_pairs':len(unique),'unique_pairs_correct':sum(v['correct'] for v in unique.values())},grounded={'baseline_correct':28,'correct':final['grounded_correct'],'cases':100,'choices':4},
 narrative={'baseline_coherent':0,'primary_coherent':len(primary_ids),'teacher_coherent':len(teacher_ids),'conservative_coherent':len(accepted),'cases':100,'families':20,'degeneration_threshold_failures':sum(v['degenerate'] for v in metrics),'generated_tokens':sum(v['generated_tokens'] for v in rows),'eos_outputs':sum(v['eos'] for v in rows)},
 document_boundary_audit={'decoded_matches':100,'cases_with_BOS':boundary['cases_with_BOS'],'frozen_full_window_scores_unchanged':True,'limitation':'Nine generated document boundaries are hidden by string decoding. Full-window scores can penalize beginning another document. No shortened-response replacement or adjusted acceptance score was used.'},independent_serialized_reference=reference,disagreement_ids=sorted(primary_ids^teacher_ids),teacher_receipt=read(ROOT/'teacher-receipt.json'),first_25_update_mean_loss=sum(v['loss'] for v in updates[:25])/25,last_25_update_mean_loss=sum(v['loss'] for v in updates[-25:])/25,training_updates_elapsed_seconds=ending,training_tokens_per_second=74973184/ending,final_30_minute_tokens_per_second=last30,elapsed_since_this_approval_seconds=time.time()-clock['start_epoch'],
 processed_positions_charged=used,prior_preflight_positions_charged=contract['prior_new_run_positions_charged'],cumulative_continuation_experiment_positions=used+contract['prior_new_run_positions_charged'],peak_process_tree_RSS_GiB=max(v['peak_RSS_bytes'] for v in resources)/1024**3,additional_global_swap_bytes=max(v['maximum_additional_swap_bytes'] for v in resources),all_workers_reaped=True,
 training_authorized=False,next_stage_authorized=False,full_training_authorized=False,conversation_training_authorized=False,formal_English_gate='NOT_RUN_AND_NOT_PASSED',development_only=True,limitations=old['limitations'])
 save(ROOT/'behavior-metrics.json',{'per_case':metrics});save(ROOT/'report.json',result);save(ROOT/'stage.json',{'status':result['status'],'training_authorized':False,'next_stage_authorized':False,'epoch':time.time()})
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
