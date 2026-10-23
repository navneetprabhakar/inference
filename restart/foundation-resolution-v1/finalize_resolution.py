"""CPU-only terminal audit. Never launches a model, teacher or next phase."""
import json,sqlite3,time
import numpy as np
from common import *
from decide import reviews
from scorer import binary

def main():
 result=read(ROOT/'R1-result.json');assert result['status']=='FAIL_STOP' and result['selected_arm'] is None
 assert read(ROOT/'STOP.json')['phase']=='R1' and not (ROOT/'R2-activation.json').exists()
 assert not (ROOT/'active-worker.json').exists()
 assert sha(ROOT/'plan.json')==read(ROOT/'approval-receipt.json')['plan_sha256']
 save(ROOT/'R1-clock.json',read(ROOT/'clock.json'))
 checks={}
 for manifest in ['R0-freeze.json','R0-review-freeze.json','R1-freeze.json','R1-review-freeze.json']:
  for name,digest in read(ROOT/manifest)['files'].items():
   path=PROJECT/name
   if manifest=='R0-freeze.json' and path==ROOT/'clock.json':path=ROOT/'R0-clock.json'
   assert sha(path)==digest,(manifest,name)
  checks[manifest]='PASS'
 for arm in ['A','B']:
  receipt=read(ROOT/arm/'checkpoint.json');assert sha(PROJECT/receipt['path'])==receipt['sha256']
  for archive in (ROOT/arm).glob('step-*.json'):
   r=read(archive);assert sha(ROOT/arm/(archive.stem+'.pt'))==r['sha256']
  assert abs(read(ROOT/arm/'summary.json')['validation_nll']-read(ROOT/arm/'fp32.json')['validation_nll'])<=.02
  assert len((ROOT/arm/'validation-history.jsonl').read_text().splitlines())==4
  assert read(ROOT/arm/'training-complete.json')['status']=='PASS'
 ref=read(ROOT/'reference-snapshot.json');assert sha(OLD/'stage3-checkpoint.pt')==ref['checkpoint_sha256'];assert sha(OLD/'global-stop.json')==ref['old_terminal_stop_sha256']
 for label in ['R0-evaluation','R0-grading','R1-execution','R1-grading']:
  s=read(ROOT/f'{label}-supervisor.json');assert s['results'] and all(r['worker_reaped'] and r['returncode']==0 for r in s['results'])
 db=sqlite3.connect(ROOT/'work.sqlite');charges=[dict(phase=a,kind=b,positions=c) for a,b,c in db.execute('SELECT phase,kind,SUM(positions) FROM work GROUP BY phase,kind ORDER BY phase,kind')]
 positions=sum(r['positions'] for r in charges);assert positions==69979600 and positions<=156000000
 receipts=[read(p) for p in sorted(ROOT.glob('*-teacher-*-receipt.json'))];requests=len(list(ROOT.glob('*-teacher-*-started.json')));assert requests==len(receipts)==4
 output=sum(r['usage']['output_tokens']+r['usage']['reasoning_output_tokens'] for r in receipts);assert output<=72000 and all(r['usage']['output_tokens']+r['usage']['reasoning_output_tokens']<=12000 for r in receipts)
 rs=[reviews('R1',i) for i in [1,2]];diagnostics={}
 for g in ['baseline','A','B']:
  ids=sorted(rs[0][g]);a,b=[r[g] for r in rs]
  diagnostics[g]=dict(binary_pass_counts=[sum(binary(v) for v in x.values()) for x in [a,b]],binary_repeat_agreement=sum(binary(a[i])==binary(b[i]) for i in ids)/40,total_score_MAD=sum(abs(sum(a[i]['scores'])-sum(b[i]['scores'])) for i in ids)/40)
 rates={}
 for arm in ['A','B']:
  rows=[json.loads(x) for x in (ROOT/arm/'updates.jsonl').read_text().splitlines()];last=rows[-32:]
  rates[arm]=dict(all_training_targets_per_second=256*131072/rows[-1]['elapsed_seconds'],last_32_update_targets_per_second=31*131072/(last[-1]['elapsed_seconds']-last[0]['elapsed_seconds']),training_seconds=rows[-1]['elapsed_seconds'])
 r0clock=read(ROOT/'R0-clock.json');r1clock=read(ROOT/'clock.json')
 report=dict(status='RESOLUTION_STOPPED_AT_R1_QUALITY_GATE',epoch=time.time(),model_parameters=15191712,from_scratch_own_lineage=True,new_pretrained_weights=False,R0_status='PASS',R1_status='FAIL_STOP',R2_started=False,conversation_training_started=False,tool_training_started=False,all_workers_reaped=True,source_manifest_checks=checks,old_stop_and_checkpoint_unchanged=True,physical_training_targets=67108864,targets_per_arm=33554432,selected_retained_new_targets=0,each_experimental_endpoint_targets=412221440,each_experimental_endpoint_step=3145,new_processed_positions=positions,work_charges=charges,old_continuation_positions=306104851,combined_continuation_resolution_positions=306104851+positions,teacher_requests=requests,new_teacher_output_plus_reasoning_tokens=output,new_teacher_input_tokens=sum(r['usage']['input_tokens'] for r in receipts),unused_R2_teacher_requests=2,unused_R2_allowances_not_reassigned=True,phase_elapsed_seconds=dict(R0_preparation_and_transition=r1clock['started_epoch']-r0clock['started_epoch'],R1_through_decision=result['epoch']-r1clock['started_epoch'],total_through_decision=result['epoch']-r0clock['started_epoch']),training_throughput=rates,peak_process_tree_RSS_bytes=max(read(ROOT/f'{label}-supervisor.json')['peak_RSS_bytes'] for label in ['R0-evaluation','R0-grading','R1-execution','R1-grading']),peak_GPU_bytes=max(read(ROOT/arm/'training-complete.json')['memory']['peak_active_or_driver_bytes'] for arm in ['A','B']),calibrated_anchor_result=result['calibration'],larger_packet_review_variation=diagnostics,stop_reason='No eligible branch: A fails story nonregression/incoherence and behavior gain; B improves grounding but fails paired mean story nonregression in review2 (-0.75 vs allowed -0.25).',interpretation='Cooldown improves fixed NLL and this development grounding packet; robust generative quality improvement was not demonstrated. Larger-packet story ratings also varied despite perfect easy-anchor classification. Do not treat this stop as a calibrated English-capability estimate, proof of capacity failure, or permission to extend training.',next_training_authorized=False)
 save(ROOT/'report.json',report)
 print(json.dumps({k:report[k] for k in ['status','new_processed_positions','physical_training_targets','teacher_requests','new_teacher_output_plus_reasoning_tokens','phase_elapsed_seconds','all_workers_reaped']}))
if __name__=='__main__':main()
