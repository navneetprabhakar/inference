"""Assemble completed inference-only preflight evidence; no model execution."""
import hashlib,json,sqlite3,time
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parent;BASE=ROOT.parents[1]
def read(name):return json.loads((ROOT/name).read_text())
def save(name,obj):(ROOT/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 clock=read('clock.json');integrity=read('integrity-verification.json');numeric=read('resume-verification.json');summary=read('baseline/summary.json');behavior=read('behavior-metrics.json')
 primary=read('primary-review.json');teacher=read('teacher-review.json')['reviews'];receipt=read('teacher-receipt.json');cases=read('baseline/stories.json')
 assert len(cases)==len(teacher)==len(primary['reviews'])==100
 degeneration={v['id']:v['degenerate'] for v in behavior['per_output']};primary_ids={v['id'] for v in primary['reviews'] if v['coherent']}
 teacher_ids={v['id'] for v in teacher if sum(v['scores'])>=8 and min(v['scores'])>0 and not v['contradiction'] and not v['incoherent_sentence'] and not degeneration[v['id']]}
 origin=BASE/'restart/mac-native-benchmark-v1/confirmation/checkpoint.pt';assert sha(origin)==read('contract.json')['reference']['checkpoint_sha256']
 assert numeric['absolute_difference']<=.02 and integrity['training_updates']==0
 for phase in ['preflight','teacher-reviewed-client']:assert read(phase+'-supervisor.json')['returncode']==0 and read(phase+'-supervisor.json')['worker_reaped']
 assert receipt['requests']==1 and receipt['requested_model']=='gpt-6-luna'
 assert not (ROOT/'active-worker.json').exists()
 assert time.time()<clock['preflight_deadline_epoch']
 resource=[read(v) for v in ['preflight-supervisor.json','teacher-baseline-supervisor.json','teacher-reviewed-client-supervisor.json']]
 results=dict(status='CORRECTED_INFERENCE_PREFLIGHT_PASS_TRAINING_PAUSED',complete_local=datetime.now(ZoneInfo('Asia/Kolkata')).isoformat(),elapsed_seconds_since_authorization=time.time()-clock['start_epoch'],deadline_seconds=900,
   checkpoint_sha256=sha(origin),optimizer_step=601,retained_training_targets=78774272,learned_parameters=15191712,student_updates=0,training_authorized=False,next_stage_authorized=False,conversation_training_authorized=False,full_training_authorized=False,
   integrity=integrity,numerical_loss_absolute_difference=numeric['absolute_difference'],numerical_loss_absolute_tolerance=.02,
   baseline_validation_nll=summary['validation_nll'],baseline_validation_targets=131072,
   grammar={'correct':summary['grammar_correct'],'cases':100,'chance_reference':.5,'unique_pairs_ignoring_option_order':behavior['unique_grammar_pairs_ignoring_option_order'],'unique_pairs_correct':behavior['unique_grammar_pairs_correct']},
   grounded={'correct':summary['grounded_correct'],'cases':100,'chance_reference':.25},
   story={'primary_coherent':len(primary_ids),'teacher_coherent':len(teacher_ids),'conservative_coherent':len(primary_ids & teacher_ids),'cases':100,'template_families':20,'degeneration_threshold_failures':behavior['degenerate_outputs'],'generated_tokens':behavior['generated_tokens'],'eos_outputs':behavior['eos_outputs'],'grades_not_two_human_final_acceptance':True},
   frozen_packet_and_validation_unchanged=True,teacher_receipt=receipt,peak_process_tree_RSS_GiB=max(v['peak_RSS_bytes'] for v in resource)/1024**3,maximum_additional_swap_bytes=max(v['maximum_additional_swap_bytes'] for v in resource),all_workers_reaped=True,
   client_startup_note='Installed CLI patch was 0.163.0-alpha.11.2 rather than .11. Initial local version guard stopped before any model request. Exact installed version/flags were reviewed; then the single authorized teacher request completed. No inference rerun or deadline reset.',
   limitations=['Development packet, not the formal English acceptance gate.','Grammar lexical templates recur: 100 rendered trials cover only 45 distinct pairs ignoring option order.','Twenty story template families with five names each; counts are not 100 independent families.','Native TinyStories train/validation split is not newly deduplicated; family/near-duplicate leakage is unresolved.','No sealed acceptance set or prior conversation holdout used.'],
   decision='Evaluator repair verified on the actual student. Base coherence/comprehension remain inadequate for conversation SFT. No foundation continuation is started; first +75M stage awaits explicit owner approval.')
 save('report.json',results);save('stage.json',{'status':results['status'],'training_authorized':False,'epoch':time.time()})
 # Freeze post-run code versions while keeping initial and client-review revisions.
 save('source-pins-final.json',{p.name:sha(p) for p in ROOT.glob('*.py')})
 p=BASE/'restart/execution-v1/CURRENT_WORK.json';current=json.loads(p.read_text());current['foundation_continuation']={'status':results['status'],'training_authorized':False,'student_updates':0,'next_stage_authorized':False,'report':'restart/foundation-inference-preflight-v2/report.json','original_failed_attempt_preserved':'restart/foundation-continuation-v1/report.json'};p.write_text(json.dumps(current,indent=2)+'\n')
 p=BASE/'restart/execution-v1/STATUS.md';p.write_text(p.read_text()+'\n\n## Corrected inference-only preflight passed; training paused\n\nExplicit15-minute correction approved. Frozen baseline evaluation completed:131,072-target NLL2.36733935; grammar55/100 (22/45 distinct pairs ignoring option order), grounded completion28/100, narrative coherence0/100 in both primary-agent and GPT-6 Luna reviews across20 template families. No outputs crossed the frozen narrow repetition threshold, despite pervasive incoherence. BF16/FP32 fixed loss difference0.0003264 within existing0.02 tolerance; original checkpoint and optimizer unchanged, zero training updates, workers reaped, zero additional swap. Previous failed attempt and charges preserved. This verifies the evaluator repair, not English capability. First+75M foundation stage and conversation training remain paused pending owner approval. See restart/foundation-inference-preflight-v2/REPORT.md.\n')
 print(json.dumps({k:results[k] for k in ['status','elapsed_seconds_since_authorization','student_updates','baseline_validation_nll','peak_process_tree_RSS_GiB','maximum_additional_swap_bytes','all_workers_reaped']}))
if __name__=='__main__':main()
