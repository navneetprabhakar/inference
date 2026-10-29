"""Full-parameter grouped runner. CLI currently permits plan/forward verification only."""
import json,hashlib,os,time,math,sqlite3,pickle,sys
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parent;PROJECT=P.parents[1]
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def resources():
 import psutil
 if psutil.Process().memory_info().rss>12*1024**3:raise RuntimeError('RSS_CAP')
 if psutil.disk_usage(PROJECT).free<60*1024**3:raise RuntimeError('FREE_DISK_FLOOR')
 if sum(f.stat().st_size for f in P.rglob('*') if f.is_file())>6*1024**3:raise RuntimeError('ARTIFACT_CAP')

def atomic(path,data):
 path=Path(path);tmp=path.with_suffix(path.suffix+'.tmp')
 with tmp.open('wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
 os.replace(tmp,path)

def collate(rows):
 n=max(len(r['ids'])-1 for r in rows);x=np.zeros((len(rows),n),np.int32);y=x.copy();m=np.zeros_like(x,np.float32)
 if n>256:raise ValueError('CONTEXT_OVERFLOW')
 for i,r in enumerate(rows):
  ids=np.asarray(r['ids']);mask=np.asarray(r['mask']);k=len(ids)-1
  if len(ids)!=len(mask) or not set(mask).issubset({0,1}) or ids.min()<0 or ids.max()>=32000:raise ValueError('INVALID_RECORD')
  x[i,:k]=ids[:-1];y[i,:k]=ids[1:];m[i,:k]=mask[1:]
  if m[i].sum()==0:raise ValueError('NO_ASSISTANT_TARGETS')
 return x,y,m

class Meter:
 """Reservations are committed BEFORE work. Failed work stays charged; no refunds."""
 def __init__(self,path,limits,allow_updates=False):
  self.db=sqlite3.connect(path);self.limits=limits;self.allow_updates=allow_updates
  self.db.execute('CREATE TABLE IF NOT EXISTS policy(value TEXT)')
  policy=json.dumps({'limits':limits,'allow_updates':allow_updates},sort_keys=True);previous=self.db.execute('SELECT value FROM policy').fetchone()
  if previous and previous[0]!=policy:raise RuntimeError('LEDGER_POLICY_CHANGED')
  if not previous:self.db.execute('INSERT INTO policy VALUES(?)',(policy,));self.db.commit()
  self.db.execute('CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, kind TEXT, positions INTEGER, updates INTEGER, assistant INTEGER, narrative INTEGER)');self.db.execute('CREATE TABLE IF NOT EXISTS timing(id INTEGER PRIMARY KEY CHECK(id=1), seconds REAL, active_start REAL)')
  row=self.db.execute('SELECT seconds,active_start FROM timing').fetchone()
  if row and row[1] is not None:
   self.db.execute('UPDATE timing SET seconds=seconds+?,active_start=NULL WHERE id=1',(max(0,time.time()-row[1]),));self.db.commit()
  if not row:self.db.execute('INSERT INTO timing VALUES(1,0,NULL)');self.db.commit()
 def totals(self):
  values=self.db.execute('SELECT COALESCE(SUM(positions),0),COALESCE(SUM(updates),0),COALESCE(SUM(assistant),0),COALESCE(SUM(narrative),0) FROM events').fetchone();return dict(zip(['positions','updates','assistant','narrative'],values))
 def cursor(self):return self.db.execute('SELECT COALESCE(MAX(id),0) FROM events').fetchone()[0]
 def seconds(self):
  sec,start=self.db.execute('SELECT seconds,active_start FROM timing').fetchone();return sec+(max(0,time.time()-start) if start is not None else 0)
 def check(self):
  if self.seconds()>self.limits['seconds']:raise RuntimeError('TIME_CAP')
 def reserve(self,kind,positions,updates=0,assistant=0,narrative=0):
  if updates and not self.allow_updates:raise RuntimeError('OPTIMIZER_FORBIDDEN')
  charges=dict(positions=positions,updates=updates,assistant=assistant,narrative=narrative)
  if any(type(v) is not int or v<0 for v in charges.values()):raise ValueError('INVALID_CHARGE')
  self.check()
  with self.db:
   self.db.execute('BEGIN IMMEDIATE');tot=self.totals()
   for k,v in charges.items():
    if tot[k]+v>self.limits[k]:raise RuntimeError('CAP_'+k)
   self.db.execute('INSERT INTO events(kind,positions,updates,assistant,narrative) VALUES(?,?,?,?,?)',(kind,positions,updates,assistant,narrative))
 def start(self):
  self.check()
  if self.db.execute('SELECT active_start FROM timing').fetchone()[0] is not None:raise RuntimeError('ACTIVE_SEGMENT_ALREADY_STARTED')
  self.db.execute('UPDATE timing SET active_start=? WHERE id=1',(time.time(),));self.db.commit()
 def stop(self):
  sec=self.seconds();self.db.execute('UPDATE timing SET seconds=?,active_start=NULL WHERE id=1',(sec,));self.db.commit();self.check()

class Inputs:
 def __init__(self):
  self.config=read(P/'config.json');self.replay_meta=read(P/'replay.json');self.data=PROJECT/self.config['data_dir'];self.schedule=read(self.data/'training-schedule.json')
  self.rows={w:read(self.data/(w+'.json')) for w in ['canonical','diverse']}
  self.replay=np.load(PROJECT/self.replay_meta['path'],mmap_mode='r')
  if sha(PROJECT/self.replay_meta['path'])!=self.replay_meta['sha256']:raise RuntimeError('REPLAY_CHANGED')
 def batch(self,wording,index,coefficient):
  if coefficient not in [0,.5] or wording not in self.rows or not 0<=index<1000:raise ValueError('INVALID_ARM_OR_CURSOR')
  rows=[self.rows[wording][i] for i in self.schedule[index]]
  if len({r['scenario']['family'] for r in rows})!=8:raise ValueError('TASK_BALANCE')
  x,y,m=collate(rows);replay=None
  if coefficient:replay=np.asarray(self.replay[self.replay_meta['indices'][index]],np.int32)
  return (x,y,m),replay

def verify_manifest():
 manifest=read(P/'freeze.json')
 for name,h in manifest['files'].items():
  if sha(PROJECT/name)!=h:raise RuntimeError('FROZEN_INPUT_CHANGED: '+name)
 return sha(P/'freeze.json')

class Backend:
 def __init__(self,lr=2e-5):
  # Reuse the repaired deterministic native embedding backward, but fresh full parameters.
  sys.path.insert(0,str(PROJECT/'restart/resume-repair-v1'));import validate as repair
  self.e,self.common=repair.s.load(PROJECT/'restart/foundation-resolution-v1/B/checkpoint.pt',mode='fresh',cursor=0)
  self.mx=self.e.mx;mx=self.mx
  from mlx.utils import tree_unflatten
  import mlx.optimizers as optim
  self.opt=optim.AdamW(lr,betas=[.9,.95],eps=1e-8,weight_decay=0.,bias_correction=True);self.opt.init(self.e.params);mx.eval(self.opt.state)
  mx.random.seed(291026)
  def loss(params,x,y,m):
   self.e.model.update(tree_unflatten([(k,v.astype(mx.bfloat16)) for k,v in params.items()]))
   ce=self.e.nn.losses.cross_entropy(self.e.model(x).astype(mx.float32),y,reduction='none')
   # Each row is exactly one task. Normalize within task before averaging tasks.
   return mx.mean(mx.sum(ce*m,axis=1)/mx.sum(m,axis=1))
  self.loss=mx.compile(loss);self.grad=mx.compile(mx.value_and_grad(loss));self.steps=0
 def digest(self):
  h=hashlib.sha256()
  for k,v in sorted(self.e.params.items()):h.update(k.encode());h.update(np.array(v).tobytes())
  return h.hexdigest()
 def forward(self,batch):
  resources()
  value=self.loss(self.e.params,*[self.mx.array(a) for a in batch]);self.mx.eval(value);self.e.memory()
  if not math.isfinite(float(value)):raise RuntimeError('NONFINITE_LOSS')
  return float(value)
 def apply(self,batch,replay,coefficient):
  resources()
  mx=self.mx;v,g=self.grad(self.e.params,*[mx.array(a) for a in batch]);mx.eval(v,g)
  loss=float(v);combined={k:(1-coefficient)*a for k,a in g.items()}
  if coefficient:
   x=replay[:,:-1];b=(x,replay[:,1:],np.ones_like(x,np.float32));rv,rg=self.grad(self.e.params,*[mx.array(a) for a in b]);mx.eval(rv,rg)
   loss=(1-coefficient)*loss+coefficient*float(rv);combined={k:a+coefficient*rg[k] for k,a in combined.items()}
  norm=mx.sqrt(sum(mx.sum(v*v) for v in combined.values()));mx.eval(norm)
  if not math.isfinite(loss) or not math.isfinite(float(norm)):raise RuntimeError('NONFINITE_GRADIENT')
  factor=mx.minimum(mx.array(1.),1/(norm+1e-6));self.e.params=self.opt.apply_gradients({k:v*factor for k,v in combined.items()},self.e.params);mx.eval(self.e.params,self.opt.state)
  if not all(bool(mx.all(mx.isfinite(v))) for v in self.e.params.values()):raise RuntimeError('NONFINITE_PARAMETERS')
  self.steps+=1;self.e.memory();return {'loss':loss,'gradient_norm':float(norm)}
 def state(self):
  from mlx.utils import tree_map
  convert=lambda x:np.array(x) if isinstance(x,self.mx.array) else x
  self.mx.eval(self.e.params,self.opt.state,self.mx.random.state)
  return {'params':tree_map(convert,self.e.params),'optimizer':tree_map(convert,self.opt.state),'rng':[np.array(x) for x in self.mx.random.state],'steps':self.steps}
 def restore(self,d):
  from mlx.utils import tree_map
  convert=lambda x:self.mx.array(x) if isinstance(x,np.ndarray) else x
  self.e.params=tree_map(convert,d['params']);self.opt.state=tree_map(convert,d['optimizer']);self.mx.random.state=[self.mx.array(x) for x in d['rng']];self.steps=d['steps'];self.mx.eval(self.e.params,self.opt.state)

class Runner:
 def __init__(self,backend,inputs,meter,wording,replay,manifest,work):
  self.backend=backend;self.inputs=inputs;self.meter=meter;self.wording=wording;self.replay=replay;self.manifest=manifest;self.work=Path(work);self.work.mkdir(parents=True,exist_ok=True);self.cursor=0
 def one(self):
  batch,replay=self.inputs.batch(self.wording,self.cursor,self.replay);x,y,m=batch;n=0 if replay is None else int(replay[:,:-1].size)
  self.meter.reserve('training-step',int(x.size)+n,updates=1,assistant=int(m.sum()),narrative=n)
  self.meter.start()
  try:stats=self.backend.apply(batch,replay,self.replay)
  finally:self.meter.stop()
  self.cursor+=1;return stats
 def save(self):
  d={'manifest':self.manifest,'wording':self.wording,'replay':self.replay,'cursor':self.cursor,'ledger_cursor':self.meter.cursor(),'state':self.backend.state()}
  atomic(self.work/'checkpoint.pkl',pickle.dumps(d,protocol=5));return d
 def restore(self):
  with (self.work/'checkpoint.pkl').open('rb') as f:d=pickle.load(f)
  if (d['manifest'],d['wording'],d['replay'])!=(self.manifest,self.wording,self.replay):raise RuntimeError('RESUME_IDENTITY_MISMATCH')
  if d['ledger_cursor']!=self.meter.cursor():raise RuntimeError('RESUME_DIRTY_LEDGER_NO_REWIND')
  self.backend.restore(d['state']);self.cursor=d['cursor']
 def run(self,evaluate,until=1000):
  if not self.cursor:evaluate('source',0)
  while self.cursor<until:
   self.one()
   if self.cursor in [250,500,1000]:evaluate('endpoint' if self.cursor==1000 else 'sentinel',self.cursor)
   self.save()

if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('command',choices=['plan','train']);args=parser.parse_args()
 if args.command=='train':raise SystemExit('TRAINING_DISABLED: explicit approval and numerical/calibration readiness required; no optimizer calls made')
 inputs=Inputs();print(json.dumps({'arms':inputs.config['arms'],'training_authorized':False,'schedule_updates':len(inputs.schedule)}))
