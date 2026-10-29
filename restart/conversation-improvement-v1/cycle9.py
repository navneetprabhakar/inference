import adapter9 as a
from journal_meter import Meter
import numpy as np,torch,json,sys,gc
from sentencepiece import SentencePieceProcessor
s=a.s;ROOT=s.ROOT

def preflight():
 meter=Meter('cycle9-preflight')
 try:
  m=a.Adapter();mx=m.mx;d=a.data();x,y,mask,_=s.serializer.collate(d[0][:2]);meter.reserve(x.size*2,'adapter-numerical')
  assert all(np.array_equal(np.array(m.base[k]),np.array(m.e.params[k])) for k in m.base)
  v,g=m.grad(m.a,mx.array(x),mx.array(y),mx.array(mask));mx.eval(v,g)
  sys.path.insert(0,str(s.serializer.UPSTREAM));from model import ModelArgs,Transformer
  torch.set_num_threads(2);t=Transformer(ModelArgs(**m.e.origin['model_args']));t.load_state_dict(m.e.origin['model']);t.eval()
  for p in t.parameters():p.requires_grad_(False)
  ta={k:torch.tensor(np.array(v),requires_grad=True) for k,v in m.a.items()};mp=m.e.mapping();params=dict(t.named_parameters())
  for old,new in mp.items():
   if new in m.names:params[old]=params[old]+2*(ta[new+'/B']@ta[new+'/A'])
  logits=torch.func.functional_call(t,params,(torch.tensor(x,dtype=torch.long),torch.tensor(y,dtype=torch.long)),tie_weights=True)
  ce=torch.nn.functional.cross_entropy(logits.reshape(-1,32000),torch.tensor(y.reshape(-1),dtype=torch.long),reduction='none').reshape(y.shape);tl=(ce*torch.tensor(mask)).sum()/mask.sum();tl.backward()
  aa=np.concatenate([ta[k].grad.numpy().ravel().astype(np.float64) for k in ta]);bb=np.concatenate([np.array(g[k]).ravel().astype(np.float64) for k in ta]);delta=abs(float(v)-float(tl.detach()));rel=np.linalg.norm(aa-bb)/np.linalg.norm(aa);cos=np.dot(aa,bb)/(np.linalg.norm(aa)*np.linalg.norm(bb))
  receipt=dict(loss_difference=delta,gradient_relative_L2=float(rel),gradient_cosine=float(cos),base_parameters=sum(v.size for v in m.base.values()),adapter_parameters=sum(v.size for v in m.a.values()))
  s.save(ROOT/'cycle9-numerical.json',receipt);assert delta<=.02 and rel<=.08 and cos>=.995,'ADAPTER_NUMERICAL_CHECK'
  del t,ta,params,logits,tl,ce,g;gc.collect()
  initial=m.state(meter)
  for i in range(2):m.update(a.groups(d,i),d[3][i],meter)
  uninterrupted=m.state(meter)
  m.restore(initial);m.update(a.groups(d,0),d[3][0],meter);path=m.save(meter,'cycle9-preflight-one');saved=torch.load(path,weights_only=False)
  # New engine and optimizer proves reload, rather than reuse of cached state.
  del m;gc.collect();m=a.Adapter();m.restore(saved);a.equal(saved,m.state(meter));m.update(a.groups(d,1),d[3][1],meter);a.equal(uninterrupted,m.state(meter))
  receipt.update(status='PASS',zero_delta=True,exact_resumed_trajectory=True,disposable_updates=4);s.save(ROOT/'cycle9-preflight.json',receipt);print(json.dumps(receipt),flush=True)
 except BaseException as ex:s.save(ROOT/'cycle9-preflight-stop.json',dict(reason=str(ex),type=type(ex).__name__));raise
 finally:meter.close()

def train():
 assert s.read(ROOT/'cycle9-preflight.json')['status']=='PASS'
 assert not (ROOT/'cycle9-started.json').exists();s.assert_frozen();s.save(ROOT/'cycle9-started.json',dict(status='STARTED'));meter=Meter('cycle9')
 try:
  m=a.Adapter();d=a.data();sp=SentencePieceProcessor(model_file=str(s.serializer.TOK));hist=[]
  for i in range(1200):
   stats=m.update(a.groups(d,i),d[3][i%len(d[3])],meter)
   with (ROOT/'cycle9-updates.jsonl').open('a') as f:f.write(json.dumps(stats)+'\n')
   if (i+1)%200:continue
   label='cycle9-'+str(i+1);p=m.save(meter,label);nll=s.foundation(m.e,meter);ret=s.generate(m.e,m.common,c.repair.run.bank('retention'),sp,16,meter,label+'-retention',legacy=True)
   row=dict(step=i+1,narrative_nll=nll,retention=ret,checkpoint=str(p.relative_to(s.PROJECT)),sha256=s.sha(p));hist.append(row);s.save(ROOT/'cycle9-history.json',hist);print(json.dumps(row),flush=True)
   assert nll<=s.ORIGINAL_NLL*1.05,'CYCLE9_NARRATIVE_GUARD'
   if (i+1)%400==0:
    row['development']=s.generate(m.e,m.common,c.repair.run.bank('development'),sp,48,meter,label+'-development');row['seen']=s.generate(m.e,m.common,s.read(s.PRIVATE/'probe-seen.json'),sp,48,meter,label+'-seen');s.save(ROOT/'cycle9-history.json',hist)
  s.save(ROOT/'cycle9-result.json',dict(status='COMPLETED',manual_review_required=True))
 except BaseException as ex:s.save(ROOT/'cycle9-stop.json',dict(reason=str(ex),type=type(ex).__name__,updates=meter.data['updates']));raise
 finally:meter.close()
import campaign as c
if __name__=='__main__':
 if sys.argv[1]=='preflight':preflight()
 else:train()
