"""CPU-only terminal audit. Does not resume or repair the frozen model attempt."""
import json,time,sqlite3,sys,os
from pathlib import Path
from common import *
import psutil

def main():
 assert (ROOT/'STOP.json').exists();clock=read(ROOT/'R0/clock.json');stop=read(ROOT/'STOP.json')
 active=[]
 for proc in psutil.process_iter(['pid','cmdline']):
  try:
   args=proc.info['cmdline'] or []
   if any(str(ROOT/name) in args for name in ['run_r0.py','evaluate.py','teacher.py']):active.append(proc.info)
  except (psutil.NoSuchProcess,psutil.AccessDenied):pass
 assert not active,'WORKER_STILL_ACTIVE'
 frozen=read(ROOT/'R0/freeze.json');assert all(sha(PROJECT/p)==h for p,h in frozen['files'].items())
 db=sqlite3.connect(ROOT/'work.sqlite');positions=db.execute('select coalesce(sum(positions),0) from work').fetchone()[0]
 bykind=[dict(kind=k,positions=n) for k,n in db.execute('select kind,sum(positions) from work group by kind')]
 assert not list(ROOT.glob('*/teacher/*-started.json'))
 sources=[]
 for c in read(ROOT/'plan.json')['source_candidates']:
  assert sha(PROJECT/c['path'])==c['sha256'];d=ROOT/'R0'/c['id'];row=dict(id=c['id'],source_sha256=c['sha256'],source_unchanged=True)
  for mode in ['stories','greedy']:
   row[mode+'_outputs_saved']=len(read(d/f'{mode}.json')) if (d/f'{mode}.json').exists() else 0
  if (d/'summary.json').exists():row['native_NLL_diagnostic']=read(d/'summary.json')['validation_nll']
  if (d/'fp32.json').exists():row['independent_FP32_NLL']=read(d/'fp32.json')['validation_nll'];row['absolute_NLL_difference']=abs(row['native_NLL_diagnostic']-row['independent_FP32_NLL'])
  row['complete_MLX_receipt']=(d/'mlx-receipt.json').exists();row['complete_FP32_receipt']=(d/'fp32-receipt.json').exists();sources.append(row)
 # Original sealed evaluation remains unopened; only byte digest custody checked.
 custody=read(ROOT/'case-custody.json');assert not custody['sealed_opened'];assert sha(custody['sealed_path'])==custody['sealed_sha256']
 bad=[dict(id=c['id'],prefix=c['prefix']) for c in read(ROOT/'cases.json')['grammar'] if 'childs' in c['prefix']]
 assert len(bad)==1
 incident=dict(reason='EVALUATION_BANK_PREPARATION_DEFECT',detected_after_model_launch=True,grammar_defects=bad,holdout_issue='Static generator review shows location and negation cases reuse development stems; exact original sealed payload was not opened.',root_cause='Prelaunch fixtures verified arithmetic/token spans but omitted semantic prefix validation and development/sealed normalized-stem disjointness.',operator_requested_interrupt=True,terminal_worker_event=stop,model_failure_claim=False,automatic_rerun_permitted=False)
 save(ROOT/'incident.json',incident)
 terminal=read(ROOT/'evaluation-supervisor.json');r=read(ROOT/'evaluation-resources.json')
 result=dict(status='INCONCLUSIVE_STOP',reason=incident['reason'],phase='R0',training_updates=0,training_targets=0,student_positions_reserved=positions,position_accounting='Conservative pre-forward reservations, including the interrupted command; not unique corpus tokens or training targets.',positions_by_kind=bykind,teacher_requests=0,teacher_output_plus_reasoning_tokens=0,elapsed_seconds_to_stop=stop['epoch']-clock['started_epoch'],sources=sources,all_frozen_files_unchanged=True,original_sealed_payload_opened=False,selected_source=None,source_selection_valid=False,primary_review_partial_count=len(read(ROOT/'R0/primary-draft.json')['reviews']),all_model_workers_reaped=True,peak_phase_process_tree_RSS_bytes=terminal['peak_RSS_bytes'],original_swap_baseline_bytes=401342464,observed_global_swap_bytes=r['global_swap_bytes'],free_disk_bytes=r['free_disk_bytes'],AC=True,D0_started=False,R1_started=False,R2_started=False,new_data_admission=False,usable_data_counts_updated=False,formal_English_pass=False,conversation_training_authorized=False,tool_training_authorized=False,finalized_epoch=time.time())
 save(ROOT/'report.json',result);save(ROOT/'R0/result.json',dict(status='INCONCLUSIVE_STOP',reason=incident['reason'],positions=positions,training_updates=0,source_selection=None))
 save(ROOT/'execution-status.json',dict(status='INCONCLUSIVE_STOP',phase='R0',reason=incident['reason'],stopped_epoch=stop['epoch'],all_workers_reaped=True,automatic_continuation=False))
 print(json.dumps(result))
if __name__=='__main__':main()
