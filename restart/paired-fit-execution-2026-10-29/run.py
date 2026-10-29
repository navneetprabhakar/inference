"""User-authorized512-update matched experiment; no automatic continuation."""
import sys,json,gc,sqlite3,hashlib,collections
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[1];PRE=P.parent/'paired-fit-preparation-2026-10-29';READY=P.parent/'runner-readiness-2026-10-29'
sys.path[:0]=[str(PRE),str(READY)]
import runner as core,evaluate as evmod
from runner import Backend,Runner,Meter,read,sha,atomic
from inputs import FitInputs
from preservation import narrative
ORIGINAL=core.resources

def resources():
 ORIGINAL()
 if sum(f.stat().st_size for f in P.rglob('*') if f.is_file())>2*1024**3:raise RuntimeError('NEW_ARTIFACT_CAP')
core.resources=resources;evmod.resources=resources

def verify():
 for f,h in read(P/'freeze.json')['files'].items():assert sha(ROOT/f)==h,f
 for f,h in read(PRE/'freeze.json')['files'].items():assert sha(ROOT/f)==h,f
 for f,h in read(PRE/'carry-forward.json')['sources'].items():assert sha(ROOT/f)==h,f
 return sha(P/'freeze.json')

def state_digest(b):
 import numpy as np
 h=hashlib.sha256()
 def walk(x):
  if isinstance(x,dict):
   for k,v in sorted(x.items()):h.update(str(k).encode());walk(v)
  elif isinstance(x,(tuple,list)):
   for v in x:walk(v)
  else:
   a=np.asarray(x);h.update(str(a.dtype).encode());h.update(str(a.shape).encode());h.update(a.tobytes())
 walk(b.state());return h.hexdigest()

def teacher(b,meter,inputs):
 mx=b.mx;by=collections.defaultdict(list)
 for indices in inputs.schedule['paired'][:128]:
  rows=[inputs.rows[i] for i in indices];batch=core.collate(rows);meter.reserve('teacher-forced-fit',int(batch[0].size));meter.start()
  try:
   model=b.common.bind(b.e);x,y,m=[mx.array(a) for a in batch];v=b.e.nn.losses.cross_entropy(model(x).astype(mx.float32),y,reduction='none');loss=mx.sum(v*m,axis=1)/mx.sum(m,axis=1);mx.eval(loss);values=loss.tolist();assert all(__import__('math').isfinite(z) for z in values)
  finally:meter.stop()
  for r,value in zip(rows,values):by[r['scenario']['family']].append(value)
 return {k:{'mean':sum(v)/len(v),'conversations':len(v)} for k,v in by.items()}

def evaluate(b,meter,inputs,name):
 print(json.dumps({'event':'evaluation-start','name':name,'seconds':meter.seconds()}),flush=True)
 e=evmod.Evaluator(b,meter,P/'private'/name/'evaluation');loss=teacher(b,meter,inputs);native=narrative(b,meter)
 result=dict(fit=e.packet(inputs.rows,'fit'),development=e.packet(read(PRE/'private/development.json'),'development'),teacher_loss=loss,native_nll=native)
 atomic(P/'private'/name/'evaluation'/'summary.json',json.dumps(result,indent=2).encode());print(json.dumps({'event':'evaluation-end','name':name,'fit':result['fit']['correct'],'dev':result['development']['correct'],'native_nll':native['nll'],'seconds':meter.seconds()}),flush=True)
 return result

def main():
 identity=verify();assert read(P/'approval.json')['approved'];assert not (P/'started.json').exists(),'NO_IMPLICIT_RESTART'
 carry=read(PRE/'carry-forward.json');budget=read(PRE/'budget.json');limits=dict(positions=budget['aggregate_position_cap'],updates=budget['aggregate_update_cap'],assistant=carry['charges']['assistant']+budget['new_assistant_target_cap'],narrative=carry['charges']['narrative']+budget['new_narrative_target_cap'],seconds=budget['aggregate_active_seconds_cap'])
 inputs=FitInputs();atomic(P/'started.json',json.dumps({'limits':limits,'authority':'Approved paired-versus-shuffled fit experiment;512 new updates,60 new active minutes,20M new positions;carry prior once'}).encode())
 meter=Meter(P/'private/study.sqlite',limits,True);assert meter.cursor()==0
 totals=dict(positions=0,updates=0,assistant=0,narrative=0);seconds=0
 for path,h in carry['sources'].items():
  assert sha(ROOT/path)==h;db=sqlite3.connect(f'file:{ROOT/path}?mode=ro',uri=True);vals=db.execute('SELECT SUM(positions),SUM(updates),SUM(assistant),SUM(narrative) FROM events').fetchone();sec,active=db.execute('SELECT seconds,active_start FROM timing').fetchone();db.close();assert active is None;seconds+=sec
  for k,v in zip(totals,vals):totals[k]+=v
 assert totals==carry['charges'] and abs(seconds-carry['seconds'])<1e-6
 meter.reserve('carry-forward-once',**totals);meter.db.execute('UPDATE timing SET seconds=? WHERE id=1',(seconds,));meter.db.commit();atomic(P/'carry-forward.json',json.dumps(carry,indent=2).encode())
 completed=[];initial=None;arm=None
 try:
  for arm in ['paired','shuffled']:
   resources();meter.start()
   try:b=Backend(.0005);digest=state_digest(b)
   finally:meter.stop()
   if initial is None:
    initial=digest;source=evaluate(b,meter,inputs,'source');assert state_digest(b)==initial
   else:assert digest==initial,'FRESH_INITIALIZATION_MISMATCH'
   r=Runner(b,inputs,meter,arm,.5,identity,P/'private'/arm)
   with (P/'private'/arm/'updates.jsonl').open('x') as log:
    for _ in range(256):
     stats=r.one();log.write(json.dumps({'step':r.cursor,**stats})+'\n');log.flush()
     if r.cursor%64==0:print(json.dumps({'event':'training','arm':arm,'step':r.cursor,'seconds':meter.seconds(),**stats}),flush=True)
   resources();meter.start()
   try:r.save()
   finally:meter.stop()
   evaluation=evaluate(b,meter,inputs,arm);record=dict(arm=arm,updates=r.cursor,initial_state_digest=digest,endpoint_parameters=b.digest(),checkpoint_sha256=sha(r.work/'checkpoint.pkl'));completed.append(record);atomic(P/'completed-arms.json',json.dumps(completed,indent=2).encode());del b,r;gc.collect()
  verify();assert meter.totals()['updates']==5124;resources()
  atomic(P/'result.json',json.dumps(dict(status='COMPLETED',arms=completed,charges=meter.totals(),seconds=meter.seconds(),new_charges={k:meter.totals()[k]-carry['charges'][k] for k in totals},new_seconds=meter.seconds()-carry['seconds'],automatic_promotion=False,final_test_used=False),indent=2).encode())
 except BaseException as e:
  atomic(P/'stop.json',json.dumps(dict(reason=str(e),type=type(e).__name__,arm=arm,completed=completed,charges=meter.totals(),seconds=meter.seconds(),no_implicit_retry=True),indent=2).encode());raise
if __name__=='__main__':main()
