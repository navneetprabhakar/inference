"""Finite English learning measurements and conservative physical-work accounting."""
# Creator: Navneet Prabhakar
from collections import Counter
from pathlib import Path
import json,os,sqlite3,time
import numpy as np
from slm.common.tokenizer import STRUCTURAL
from slm.data.schema import digest
from slm.data.stream_hash import sha

def save(path,value):Path(path).write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
class Meter:
 def __init__(self,path,contract_hash,maximum=100000000,phase_maximum=78000000):
  self.db=sqlite3.connect(path);self.maximum=maximum;self.phase_maximum=phase_maximum
  self.db.executescript('PRAGMA synchronous=FULL; CREATE TABLE IF NOT EXISTS contract(hash TEXT); CREATE TABLE IF NOT EXISTS charges(phase TEXT,cursor INTEGER,positions INTEGER,status TEXT,PRIMARY KEY(phase,cursor));')
  rows=self.db.execute('SELECT hash FROM contract').fetchall()
  if not rows:self.db.execute('INSERT INTO contract VALUES(?)',(contract_hash,));self.db.commit()
  elif rows!=[(contract_hash,)]:raise ValueError('Frozen physical budget contract differs')
 def reserve(self,phase,cursor,positions):
  if type(positions) is not int or positions<1:raise ValueError('Positive complete work reservation required')
  self.db.execute('BEGIN IMMEDIATE')
  try:
   total=self.db.execute('SELECT coalesce(sum(positions),0) FROM charges').fetchone()[0]
   phase_total=self.db.execute('SELECT coalesce(sum(positions),0) FROM charges WHERE phase=?',(phase,)).fetchone()[0]
   preliminary=self.db.execute("SELECT coalesce(sum(positions),0) FROM charges WHERE phase IN ('common','mlx','cuda')").fetchone()[0]
   if (total+positions>self.maximum or phase_total+positions>self.phase_maximum
       or (phase in ('common','mlx','cuda') and preliminary+positions>2000000)):
    raise ValueError('Physical prediction-position budget exhausted')
   self.db.execute('INSERT INTO charges VALUES(?,?,?,?)',(phase,cursor,positions,'reserved'));self.db.commit()
  except BaseException:self.db.rollback();raise
 def complete(self,phase,cursor):self.db.execute("UPDATE charges SET status='complete' WHERE phase=? AND cursor=?",(phase,cursor));self.db.commit()
 def total(self):return self.db.execute('SELECT coalesce(sum(positions),0) FROM charges').fetchone()[0]
 def close(self):self.db.close()

def nll(trainer,bpe,documents,output,maximum_positions=1024):
 if Path(output).exists():raise FileExistsError(output)
 rows=[];start=time.monotonic()
 context=__import__('torch').no_grad if trainer.backend=='torch' else __import__('contextlib').nullcontext
 for i,r in enumerate(documents):
  tokens=(bpe.encode(r['text'])+[STRUCTURAL['eos']])[:maximum_positions+1]
  if len(tokens)<2:raise ValueError('Nonempty heldout document required')
  with context():
   value=trainer.impl.loss(trainer.params,trainer.config,trainer.array([tokens[:-1]]),trainer.array([tokens[1:]]),trainer.array(np.ones((1,len(tokens)-1),np.float32)),loss_implementation=trainer.recipe.loss_implementation,embedding_implementation=trainer.recipe.embedding_implementation)
   score=float(value.detach()) if trainer.backend=='torch' else float(value)
  if not np.isfinite(score):raise FloatingPointError('Nonfinite held-out NLL')
  rows.append(dict(example_id=r['example_id'],split_group=r['split_group'],source=r['source'],nll=score,positions=len(tokens)-1,full_document_scored=len(tokens)-1>=len(bpe.encode(r['text']))))
 result=dict(creator='Navneet Prabhakar',kind='bounded-heldout-document-nll-v1',documents=len(rows),mean_document_nll=float(np.mean([r['nll'] for r in rows])),maximum_positions_per_document=maximum_positions,seconds=time.monotonic()-start,rows=rows,scope='Fixed first up to1024prediction positions per heldout document, equal-document averaging. Full long documents are not claimed scored; same protocol across candidates.')
 save(output,result);return result

def compare_learning(before,after,minimum=.1,maximum_slice_regression=.1):
 a,b=before['rows'],after['rows']
 if [(r['example_id'],r['split_group'],r['source'],r['positions']) for r in a]!=[(r['example_id'],r['split_group'],r['source'],r['positions']) for r in b]:raise ValueError('Identical family-isolated held-out measurements required')
 if len({r['split_group'] for r in a})!=len(a):raise ValueError('One document per held-out family required')
 delta=np.array([x['nll']-y['nll'] for x,y in zip(a,b)],np.float64);rng=np.random.default_rng(20261020)
 boot=np.mean(delta[rng.integers(0,len(delta),size=(2000,len(delta)))],axis=1);lo,hi=np.quantile(boot,[.025,.975])
 slices={s:float(np.mean([d for d,r in zip(delta,a) if r['source']==s])) for s in sorted({r['source'] for r in a})}
 passed=float(delta.mean())>=minimum and lo>0 and min(slices.values())>=-maximum_slice_regression
 return dict(passed=bool(passed),mean_improvement_nats=float(delta.mean()),bootstrap_95_lower=float(lo),bootstrap_95_upper=float(hi),source_improvements_nats=slices,minimum_improvement_nats=minimum,maximum_slice_regression=maximum_slice_regression,bootstrap_seed=20261020,resamples=2000,unit='one independent document family')

def run_updates(trainer,updates,meter,phase,output,wall_seconds):
 output=Path(output);output.mkdir(exist_ok=False);start=time.monotonic();last=None
 with (output/'updates.jsonl').open('x') as log:
  for _ in range(updates):
   if time.monotonic()-start>wall_seconds:raise TimeoutError('Finite update-phase wall deadline')
   _,end=trainer._update_context();positions=trainer.batches.counts(end)[0]-trainer.batches.counts(trainer.cursor)[0];cursor=trainer.cursor
   meter.reserve(phase,cursor,positions)
   last=trainer.update();meter.complete(phase,cursor)
   log.write(json.dumps(last)+'\n');log.flush();os.fsync(log.fileno())
   if trainer.step%8==0:print(json.dumps(dict(phase=phase,**last,elapsed=time.monotonic()-start)),flush=True)
 trainer.save(output/'checkpoint');save(output/'completion.json',dict(creator='Navneet Prabhakar',complete=True,last=last,seconds=time.monotonic()-start,physical_reserved_positions=meter.total(),checkpoint_manifest_sha256=sha(output/'checkpoint/manifest.json')))
 return output/'checkpoint'
