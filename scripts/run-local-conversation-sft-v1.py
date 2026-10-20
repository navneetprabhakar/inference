"""Finite local SFT, durable cumulative charges and actual-history assessments."""
# Creator: Navneet Prabhakar
import fcntl,json,os,resource,shutil,signal,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
from slm.data.stream_hash import sha
ROOT=Path('data/local-conversation-run-v1');PLAN=Path('configs/local-conversation-run-v1.json')
def save(p,v):
 p=Path(p);tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(v,indent=2,sort_keys=True)+'\n');tmp.replace(p)
def verify(p):
 for name,h in p['inputs'].items():
  if sha(name)!=h:raise ValueError('Frozen local conversation dependency changed: '+name)
def worker(p):
 from slm.common import checkpoint
 from slm.common.training import Trainer,Recipe
 from slm.common.tokenizer import BPE
 from slm.data.conversation_research import ConversationBatches
 from slm.english_budget_v3 import Meter
 from slm.english_learning import nll,compare_learning
 from slm.conversation_recovery import capture
 verify(p);started=time.monotonic();bpe=BPE.load(p['tokenizer']);meter=Meter(ROOT/'physical.sqlite',sha(PLAN),maximum=100000000,phase_maximum=p['maximum_remaining_sft_positions'],priors=p['sealed_raw_priors'])
 launch=json.loads((ROOT/'process.json').read_text());deadline=datetime.fromisoformat(launch['deadline_utc']).timestamp()
 def guard():
  if time.time()>deadline-900:raise TimeoutError('Local absolute deadline with checkpoint reserve')
  if shutil.disk_usage(ROOT).free<40*1024**3 or resource.getrusage(resource.RUSAGE_SELF).ru_maxrss>16*1024**3:raise ValueError('Local disk/RSS resource guard')
 with ConversationBatches(p['data'],p['tokenizer'],p['schedule_sha256']) as batches:
  config,weights=checkpoint.load(p['source_model']);t=Trainer(config,weights,batches,'mlx','default',Recipe(**p['recipe']),sha(Path(p['tokenizer'])/'manifest.json'))
  if any(not np.array_equal(weights[k],v) for k,v in t.impl.export(t.params).items()) or t.moments:raise ValueError('Exact FP32 source import/fresh optimizer required')
  save(ROOT/'origin-import.json',dict(creator='Navneet Prabhakar',passed=True,source_model_sha256=sha(Path(p['source_model'])/'manifest.json'),exact_weights=True,fresh_optimizer=True,old_optimizer_discard_explicit=True));del weights
  def heldout(name):
   scores=[]
   for line in Path(p['data'],'validation.jsonl').open():
    r=json.loads(line);ids,ys,mask=bpe.serialize(r['messages'],objective='assistant')
    v=t.impl.loss(t.params,t.config,t.array([ids]),t.array([ys]),t.array([mask]),loss_implementation=t.recipe.loss_implementation,embedding_implementation=t.recipe.embedding_implementation)
    value=float(v)
    if not np.isfinite(value):raise FloatingPointError('Nonfinite conversation heldout NLL')
    scores.append(dict(split_group=r['split_group'],row_index=r['row_index'],source=r['source'],nll=value))
   result=dict(creator='Navneet Prabhakar',rows=scores,mean_nll=float(np.mean([r['nll'] for r in scores])),scope='Assistant-target heldout NLL, not semantic conversation acceptance')
   save(ROOT/(name+'-conversation-nll.json'),result);return result
  before=heldout('initial');progress=None;stop='finite_two_pass_source_exhaustion';documents=[json.loads(x) for x in Path(p['retention_documents']).open()]
  try:
   with (ROOT/'updates.jsonl').open('x') as log:
    while t.cursor<len(batches):
     guard();_,end=t._update_context();cursor=t.cursor;positions=batches.counts(end)[0]-batches.counts(cursor)[0]
     meter.reserve('conversation_sft',cursor,positions);progress=t.update();meter.complete('conversation_sft',cursor)
     log.write(json.dumps(progress)+'\n');log.flush();os.fsync(log.fileno())
     if t.step%16==0:save(ROOT/'progress.json',dict(phase='training',**progress,cumulative_physical_positions=meter.total(),elapsed=time.monotonic()-started));print(json.dumps(dict(phase='training',**progress,elapsed=time.monotonic()-started)),flush=True)
     if t.step in p['scheduled_check_updates']:
      t.save(ROOT/('checkpoint-'+str(t.step)));measured=nll(t,bpe,documents,ROOT/f'retention-step-{t.step}.json');quality=compare_learning(json.loads(Path(p['retention_baseline']).read_text()),measured,.02)
      save(ROOT/f'retention-step-{t.step}-quality.json',quality)
      if min(quality['source_improvements_nats'].values())<-.1:stop='unchanged_retention_regression_guard';break
    t.save(ROOT/'terminal');after=heldout('terminal');save(ROOT/'training-completion.json',dict(creator='Navneet Prabhakar',complete=True,termination=stop,steps=t.step,cursor=t.cursor,new_physical_positions=t.tokens,new_supervised_positions=t.supervised_tokens,cumulative_physical_positions=meter.total(),initial_conversation_nll=before['mean_nll'],terminal_conversation_nll=after['mean_nll'],no_capability_claim=True,terminal_manifest_sha256=sha(ROOT/'terminal/manifest.json'),seconds=time.monotonic()-started))
  except BaseException as e:
   # Preserve the last complete model/moments if the failing atomic update did not mutate them safely.
   save(ROOT/'training-failure.json',dict(complete=False,error_type=type(e).__name__,message=str(e),cumulative_physical_positions=meter.total(),automatic_retry=False));raise
  finally:meter.close()
 del t
 verify(p)
 for name,protocol in p['generation_protocols'].items():
  guard();save(ROOT/'progress.json',dict(phase='generation',protocol=name));capture(ROOT/'terminal/model',p['tokenizer'],protocol,ROOT/name,p['maximum_generation_seconds_per_protocol'])
 verify(p);save(ROOT/'completion.json',dict(creator='Navneet Prabhakar',complete=True,raw_student_pairs=600,direct_grading_pending=True,model_promoted=False,teacher_calls=0,cloud_commands=0,plan_sha256=sha(PLAN),seconds=time.monotonic()-started))
def main():
 p=json.loads(PLAN.read_text());verify(p)
 if len(sys.argv)>1:
  if sys.argv[1]!='worker':raise ValueError('Only explicit owned worker action')
  worker(p);return
 if ROOT.exists():raise FileExistsError('Never replay an allocated attempt')
 ROOT.mkdir()
 with (ROOT/'execution.lock').open('x') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);now=time.time();save(ROOT/'process.json',dict(parent=os.getpid(),started_at_utc=datetime.fromtimestamp(now,timezone.utc).isoformat(),deadline_utc=datetime.fromtimestamp(now+p['maximum_wall_seconds'],timezone.utc).isoformat(),plan_sha256=sha(PLAN)))
  with (ROOT/'worker.log').open('xb') as out:
   child=subprocess.Popen([sys.executable,__file__,'worker'],stdout=out,stderr=subprocess.STDOUT,start_new_session=True);save(ROOT/'child.json',dict(pid=child.pid))
   try:
    code=child.wait(timeout=p['maximum_wall_seconds'])
    if code:raise RuntimeError('Local worker failed; inspect retained evidence, no automatic replay')
   except BaseException as e:
    if child.poll() is None:
     os.killpg(child.pid,signal.SIGTERM)
     try:child.wait(timeout=15)
     except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
    save(ROOT/'supervisor-failure.json',dict(complete=False,error_type=type(e).__name__,message=str(e),no_retry=True));raise
  save(ROOT/'supervisor-terminal.json',dict(complete=True,exit_code=0))
if __name__=='__main__':main()
