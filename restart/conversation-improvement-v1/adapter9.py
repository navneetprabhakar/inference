import campaign as c
import numpy as np, torch, math
from mlx.utils import tree_unflatten,tree_map
import mlx.optimizers as optim
s=c.s
PARENT=s.PROJECT/'restart/foundation-resolution-v1/B/checkpoint.pt'
class Adapter:
 def __init__(self):
  self.e,self.common=s.load(PARENT,mode='fresh',cursor=0);self.mx=self.e.mx;mx=self.mx
  self.base=dict(self.e.params);self.names=[k for k in self.base if 'layers.' in k and self.base[k].ndim==2];assert len(self.names)==42
  mx.random.seed(s.SEED)
  self.a={}
  for k in self.names:
   out,inp=self.base[k].shape;self.a[k+'/A']=mx.random.normal((8,inp))/math.sqrt(inp);self.a[k+'/B']=mx.zeros((out,8))
  self.opt=optim.AdamW(2e-4,betas=[.9,.95],eps=1e-8,weight_decay=0.,bias_correction=True);self.opt.init(self.a)
  self.step=0;self.targets=0;self.replay=0
  mx.eval(self.a,self.opt.state);self.sync()
  def loss(a,x,y,m):
   self.e.model.update(tree_unflatten([(k,v.astype(mx.bfloat16)) for k,v in self.merged(a).items()]))
   logits=self.e.model(x).astype(mx.float32);ce=self.e.nn.losses.cross_entropy(logits,y,reduction='none')
   return mx.sum(ce*m)/mx.sum(m)
  self.loss=mx.compile(loss);self.grad=mx.compile(mx.value_and_grad(loss))
 def merged(self,a):return {k:v+2*(a[k+'/B']@a[k+'/A']) if k in self.names else v for k,v in self.base.items()}
 def sync(self):self.e.params=self.merged(self.a);self.mx.eval(self.e.params)
 def update(self,groups,narrative,meter):
  mx=self.mx;parts=[(w,s.serializer.collate(rows)[:3]) for _,w,rows in groups]
  nt=sum(int(m.sum()) for _,(x,y,m) in parts);nx=narrative[:,:-1];parts.append((.5,(nx,narrative[:,1:],np.ones_like(nx,dtype=np.float32))))
  meter.reserve(sum(x.size for _,(x,y,m) in parts),'adapter-optimizer-update',updates=1,sft=nt,narrative=nx.size)
  total=None;losses=[]
  for w,(x,y,m) in parts:
   v,g=self.grad(self.a,mx.array(x),mx.array(y),mx.array(m));mx.eval(v,g);losses.append(float(v));total={k:w*g[k]+(total[k] if total is not None else 0) for k in g}
  norm=mx.sqrt(sum(mx.sum(g*g) for g in total.values()));mx.eval(norm)
  assert math.isfinite(float(norm)) and float(norm)<100 and all(math.isfinite(v) for v in losses),'NUMERICAL_GUARD'
  factor=mx.minimum(mx.array(1.),1/(norm+1e-6));self.a=self.opt.apply_gradients({k:g*factor for k,g in total.items()},self.a);mx.eval(self.a,self.opt.state)
  self.step+=1;self.targets+=nt;self.replay+=nx.size;self.sync();self.e.memory();meter.check()
  return dict(step=self.step,losses=losses,norm=float(norm))
 def state(self,meter):
  self.mx.eval(self.a,self.opt.state,self.mx.random.state)
  return dict(schema='rank8-adapter-v1',parent_sha256=s.sha(PARENT),adapters=tree_map(lambda x:np.array(x) if isinstance(x,self.mx.array) else x,self.a),optimizer=tree_map(lambda x:np.array(x) if isinstance(x,self.mx.array) else x,self.opt.state),rng=[np.array(x) for x in self.mx.random.state],step=self.step,targets=self.targets,replay=self.replay,ledger_cursor=len(meter.data['reservations']))
 def restore(self,d):
  assert d['parent_sha256']==s.sha(PARENT)
  self.a=tree_map(lambda x:self.mx.array(x) if isinstance(x,np.ndarray) else x,d['adapters']);self.opt.state=tree_map(lambda x:self.mx.array(x) if isinstance(x,np.ndarray) else x,d['optimizer'])
  self.mx.random.state=[self.mx.array(x) for x in d['rng']];self.step=d['step'];self.targets=d['targets'];self.replay=d['replay'];self.sync()
 def save(self,meter,label):
  p=s.PRIVATE/(label+'.pt');torch.save(self.state(meter),p);return p

def equal(a,b):
 if isinstance(a,dict):
  assert a.keys()==b.keys()
  for k in a:
   if k!='ledger_cursor':equal(a[k],b[k])
 elif isinstance(a,(list,tuple)):
  assert len(a)==len(b)
  for x,y in zip(a,b):equal(x,y)
 elif isinstance(a,np.ndarray):assert np.array_equal(a,b)
 else:assert a==b

def data():
 return s.read(s.PRIVATE/'teacher.json'),s.read(s.PRIVATE/'original-rehearsal.json'),s.read(s.PRIVATE/'cycle7-schedule.json'),np.load(s.PRIVATE/'replay.npy').astype(np.int32)
def groups(d,i):
 teacher,old,schedule,_=d
 return [('rehearsal',.25,[old[j] for j in schedule[i]['rehearsal']]),('conversation',.25,[teacher[j] for j in schedule[i]['teacher']])]
