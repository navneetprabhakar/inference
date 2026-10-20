"""After terminal training, compare exact preserved source and terminal on authored English cases."""
# Creator: Navneet Prabhakar
import json,os,resource,shutil,time
from datetime import datetime,timezone
from pathlib import Path
from slm.conversation_recovery import capture
from slm.data.stream_hash import sha
ROOT=Path('data/grounded-core-comparison-v1');TRAIN=Path('data/grounded-conversation-run-v1');CORE=Path('data/core-english-development-v1');PLAN=Path('configs/grounded-core-comparison-v1.json')
def save(p,v):Path(p).write_text(json.dumps(v,indent=2,sort_keys=True)+'\n')
def main():
 if ROOT.exists() or PLAN.exists():raise FileExistsError('Preserve allocated core comparison; never auto-replay')
 done=json.loads((TRAIN/'completion.json').read_text());audit=json.loads((TRAIN/'state-audit.json').read_text());p=json.loads(Path('configs/grounded-conversation-run-v1.json').read_text());source=Path(p['source_model']);terminal=TRAIN/'terminal/model'
 if not done['complete'] or not audit['passed']:raise ValueError('Actual complete audited terminal run required')
 review=json.loads((CORE/'audit-v2.json').read_text());contain=json.loads((CORE/'containment-audit-v4.json').read_text())
 if review['revised_protocol_sha256']!=sha(CORE/'protocol-v2.json') or contain['protocol_sha256']!=sha(CORE/'protocol-v2.json'):raise ValueError('Frozen actual-history criteria/audit required')
 if contain['first_scenario_request_containment_hits'] or contain['short_context_hits'] or any(v['first_scenario_request_near_hits'] or v['whole_request_sequence_near_hits'] for v in review['grouping_checks'].values()):raise ValueError('Known literal scenario exposure prevents unseen-scenario claim')
 deadline=json.loads((TRAIN/'process.json').read_text())['deadline_utc'];absolute=datetime.fromisoformat(deadline).timestamp()
 if time.time()>absolute-1200:raise TimeoutError('Preserve original local absolute clock, no deadline reset')
 if sha(source/'manifest.json')!=p['source_model_sha256'] or sha(terminal/'manifest.json')!=audit['terminal_model_manifest_sha256']:raise ValueError('Exact paired model identities required')
 paths=[CORE/'protocol-v2.json',CORE/'audit-v2.json',CORE/'containment-audit-v4.json',TRAIN/'state-audit.json',TRAIN/'completion.json',TRAIN/'process.json',Path('configs/grounded-conversation-run-v1.json'),Path(__file__),Path('src/slm/conversation_recovery.py'),Path('src/slm/inference/greedy.py'),Path('src/slm/backends/mlx_backend.py'),*source.rglob('*'),*terminal.rglob('*'),*Path(p['tokenizer']).rglob('*')]
 plan=dict(creator='Navneet Prabhakar',kind='grounded-core-paired-development-v1',training_allowed=False,cloud_allowed=False,teacher_calls=0,maximum_capture_seconds_per_model=1800,original_local_deadline_utc=deadline,deadline_reset=False,source_model=str(source),terminal_model=str(terminal),protocol=str(CORE/'protocol-v2.json'),actual_sessions=200,actual_turns=600,scope='Same100authored everyday scenarios, separate actual source/terminal histories. Development only, not random population or untouched final proof. No teacher/retrieval/repair; binary success direct review with self-checks grounded in actual replies. Broad75%target separate from narrow QA.',inputs={str(path):sha(path) for path in paths if path.is_file()})
 PLAN.write_text(json.dumps(plan,indent=2,sort_keys=True)+'\n');ROOT.mkdir();save(ROOT/'process.json',dict(pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),original_local_deadline_utc=deadline,plan_sha256=sha(PLAN)))
 try:
  for name,model in [('source',source),('trained',terminal)]:
   if time.time()>absolute-900 or shutil.disk_usage(ROOT).free<40*1024**3 or resource.getrusage(resource.RUSAGE_SELF).ru_maxrss>16*1024**3:raise ValueError('Original local clock/disk/RSS guard')
   capture(model,p['tokenizer'],CORE/'protocol-v2.json',ROOT/name,min(1800,absolute-time.time()-600))
  for path,h in plan['inputs'].items():
   if sha(path)!=h:raise ValueError('Frozen comparison input changed')
  save(ROOT/'completion.json',dict(creator='Navneet Prabhakar',complete=True,actual_sessions=200,actual_turns=600,actual_history=True,direct_grading_pending=True,training_updates=0,teacher_calls=0,cloud_commands=0,plan_sha256=sha(PLAN)))
 except BaseException as e:
  save(ROOT/'failure.json',dict(complete=False,error_type=type(e).__name__,message=str(e),automatic_retry=False));raise
if __name__=='__main__':main()
