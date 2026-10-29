"""Bounded, authorized tiny-copy experiment. No implicit restart or extra updates."""
import sys,json,gc,sqlite3,pickle,hashlib,math
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[1];PRE=P.parent/'tiny-copy-preparation-2026-10-29';READY=P.parent/'runner-readiness-2026-10-29';sys.path[:0]=[str(PRE),str(READY)]
import runner as core,evaluate as evmod
from runner import Backend,Runner,Meter,read,sha,atomic
from inputs import TinyInputs
from metrics import score,summarize,select_lr
from preservation import narrative
ORIGINAL=core.resources

def resources():
 ORIGINAL()
 if sum(f.stat().st_size for f in P.rglob('*') if f.is_file())>1073741824:raise RuntimeError('NEW_ARTIFACT_CAP')
core.resources=resources;evmod.resources=resources

def save(path,obj):atomic(path,json.dumps(obj,indent=2).encode())
def verify():
 for manifest in [P/'freeze.json',PRE/'freeze.json']:
  for f,h in read(manifest)['files'].items():assert sha(ROOT/f)==h,f
 c=read(PRE/'carry-forward.json');assert sha(ROOT/c['source'])==c['source_sha256']
 return sha(P/'freeze.json')

def treehash(x):
 import numpy as np
 h=hashlib.sha256()
 def visit(v):
  if isinstance(v,dict):
   for k,a in sorted(v.items()):h.update(str(k).encode());visit(a)
  elif isinstance(v,(list,tuple)):
   for a in v:visit(a)
  else:
   a=np.asarray(v);h.update(str(a.dtype).encode());h.update(str(a.shape).encode());h.update(a.tobytes())
 visit(x);return h.hexdigest()

def packet(b,meter,rows,path):
 e=evmod.Evaluator(b,meter,path.parent);out=[]
 with path.open('x') as handle:
  for r in rows:
   response,eos,bos,overflow=e.generate(r['messages'][:1],32);o=dict(id=r['id'],response=response,eos=eos,bos=bos,overflow=overflow,expected=r['value'],**score(r['value'],response,eos,bos,overflow));out.append(o);handle.write(json.dumps(o)+'\n');handle.flush()
 return summarize(rows,out)

def teacher(b,meter,inputs,family,path):
 mx=b.mx;out=[]
 for indices in inputs.schedule[family][:8]:
  rows=[inputs.rows[i] for i in indices];x,y,m=core.collate(rows);meter.reserve('teacher-fit',int(x.size));meter.start()
  try:
   model=b.common.bind(b.e);logits=model(mx.array(x)).astype(mx.float32);loss=b.e.nn.losses.cross_entropy(logits,mx.array(y),reduction='none');pred=mx.argmax(logits,axis=-1);mx.eval(loss,pred);losses=loss.tolist();preds=pred.tolist();assert all(math.isfinite(v) for a in losses for v in a)
  finally:meter.stop()
  for j,r in enumerate(rows):
   positions=[k for k,v in enumerate(m[j]) if v];ts=[dict(expected=int(y[j,k]),predicted=int(preds[j][k]),nll=float(losses[j][k]),eos=i==len(positions)-1) for i,k in enumerate(positions)];errors=[i for i,t in enumerate(ts) if t['expected']!=t['predicted']]
   out.append(dict(id=r['id'],mean_loss=sum(t['nll'] for t in ts)/len(ts),first_error=errors[0] if errors else None,tokens=ts))
 save(path,out);assert len(out)==32
 return sum(r['mean_loss'] for r in out)/len(out)

def fit_eval(b,meter,inputs,family,folder,step):
 folder.mkdir(parents=True,exist_ok=True);loss=teacher(b,meter,inputs,family,folder/f'{step}-teacher.json');fit=packet(b,meter,[r for r in inputs.rows if r['family']==family],folder/f'{step}-fit.jsonl');result=dict(loss=loss,fit=fit);save(folder/f'{step}-summary.json',result)
 print(json.dumps({'event':'fit','family':family,'path':str(folder),'step':step,'loss':loss,'correct':sum(c['correct'] for c in fit.values()),'seconds':meter.seconds()}),flush=True);return result

def main():
 identity=verify();assert read(P/'approval.json')['approved'];assert not (P/'started.json').exists(),'NO_IMPLICIT_RESTART';inputs=TinyInputs();carry=read(PRE/'carry-forward.json');budget=read(PRE/'budget.json')
 limits=dict(positions=budget['aggregate_position_cap'],updates=budget['aggregate_update_cap'],assistant=carry['charges']['assistant']+budget['new_assistant_target_cap'],narrative=carry['charges']['narrative']+budget['new_narrative_target_cap'],seconds=budget['aggregate_seconds_cap'])
 save(P/'started.json',dict(limits=limits,authority='User approved512updates/15newactive minutes/6Mnewpositions, carry prior forward once'))
 meter=Meter(P/'private/study.sqlite',limits,True);assert meter.cursor()==0
 db=sqlite3.connect(f'file:{ROOT/carry["source"]}?mode=ro',uri=True);values=db.execute('SELECT SUM(positions),SUM(updates),SUM(assistant),SUM(narrative) FROM events').fetchone();sec,active=db.execute('SELECT seconds,active_start FROM timing').fetchone();db.close();assert active is None and dict(zip(['positions','updates','assistant','narrative'],values))==carry['charges'] and abs(sec-carry['seconds'])<1e-6
 meter.reserve('carry-forward-once',**carry['charges']);meter.db.execute('UPDATE timing SET seconds=? WHERE id=1',(sec,));meter.db.commit();save(P/'carry-forward.json',carry)
 arms=[];losses=[];initial=None;opt_hashes={};source={};arm=None
 try:
  for lr in [.0001,.0005]:
   for family in ['name','time']:
    arm=f'{family}-{lr:g}';folder=P/'private'/arm;resources();meter.start()
    try:
     b=Backend(lr);state=b.state();param=b.digest();rng=treehash(state['rng']);opt=treehash(state['optimizer']);assert state['steps']==0
    finally:meter.stop()
    if initial is None:
     initial=(param,rng);source_folder=P/'private/source';source_folder.mkdir(parents=True)
     for f in ['name','time']:source[f]=fit_eval(b,meter,inputs,f,source_folder/f,0)
     source['native']=narrative(b,meter);source['transfer']=packet(b,meter,read(PRE/'private/transfer.json'),source_folder/'transfer.jsonl');save(source_folder/'summary.json',source);assert b.digest()==param and treehash(b.state()['rng'])==rng
    else:assert (param,rng)==initial,'INITIAL_PARAMETERS_RNG_MISMATCH'
    if lr in opt_hashes:assert opt==opt_hashes[lr],'INITIAL_OPTIMIZER_MISMATCH'
    else:opt_hashes[lr]=opt
    r=Runner(b,inputs,meter,family,.5,identity,folder)
    with (folder/'updates.jsonl').open('x') as log:
     for _ in range(128):
      stats=r.one();log.write(json.dumps(dict(step=r.cursor,**stats))+'\n');log.flush()
      if r.cursor in [64,128]:result=fit_eval(b,meter,inputs,family,folder/'evaluation',r.cursor)
    native=narrative(b,meter);meter.start()
    try:r.save()
    finally:meter.stop()
    resources();record=dict(arm=arm,family=family,lr=lr,updates=128,initial_parameters=param,initial_rng=rng,initial_optimizer=opt,endpoint_parameters=b.digest(),checkpoint_sha256=sha(folder/'checkpoint.pkl'),native_nll=native['nll'],fit=result['fit'],loss=result['loss']);save(folder/'endpoint.json',record);arms.append(record);losses.append(dict(lr=lr,family=family,loss=result['loss']));save(P/'completed-arms.json',arms);del b,r,state;gc.collect()
  chosen=select_lr(losses,{f:source[f]['loss'] for f in ['name','time']});save(P/'selection.json',dict(common_lr=chosen,endpoint_training_losses=losses,source_training_losses={f:source[f]['loss'] for f in ['name','time']},rule='minimize worst-task source-normalized teacher-forced endpoint fit loss;tie smallerLR',transfer_started=False))
  selection_hash=sha(P/'selection.json');print(json.dumps({'event':'selection','lr':chosen}),flush=True)
  transfers={}
  for record in [a for a in arms if a['lr']==chosen]:
   folder=P/'private'/record['arm'];meter.start()
   try:b=Backend(chosen);b.restore(pickle.loads((folder/'checkpoint.pkl').read_bytes())['state']);assert b.digest()==record['endpoint_parameters']
   finally:meter.stop()
   transfers[record['family']]=packet(b,meter,[r for r in read(PRE/'private/transfer.json') if r['family']==record['family']],folder/'transfer.jsonl');assert b.digest()==record['endpoint_parameters'];del b;gc.collect()
  assert sha(P/'selection.json')==selection_hash;verify();resources();assert meter.totals()['updates']==5636
  save(P/'result.json',dict(status='COMPLETED',arms=arms,selection_sha256=selection_hash,selected_lr=chosen,transfer=transfers,charges=meter.totals(),seconds=meter.seconds(),new_charges={k:meter.totals()[k]-v for k,v in carry['charges'].items()},new_seconds=meter.seconds()-carry['seconds'],promotion=False,final_test_used=False))
 except BaseException as e:
  save(P/'stop.json',dict(reason=str(e),type=type(e).__name__,arm=arm,completed_arms=len(arms),charges=meter.totals(),seconds=meter.seconds(),no_implicit_retry=True));raise
if __name__=='__main__':main()
