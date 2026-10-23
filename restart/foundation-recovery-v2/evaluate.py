"""Read-only, metered native evaluation. No parameter or optimizer updates."""
import sys,math,argparse,time
import numpy as np
from common import *
from scorer import continuation,suffix_score,controls
sys.path.insert(0,str(UPSTREAM))

def fixed_loss(engine,meter):
 val=np.load(OLD/'validation.npy');assert val.shape==(512,257)
 losses=[]
 for i in range(0,len(val),16):meter.reserve(4096,'native-validation');losses.append(engine.validation(val[i:i+16]))
 nll=float(np.mean(losses));assert math.isfinite(nll);return nll

def fixtures():
 bank=read(ROOT/'cases.json');legacy=read(OLD/'packet.json');rows=[]
 for key,kind,cases in [('freshgrammar','grammar',bank['grammar']),('facts','facts',bank['facts']),('legacygrammar','grammar',legacy['grammar']),('legacyfacts','facts',legacy['grounded'])]:
  for i,c in enumerate(cases):
   rows.append(dict(**c,suite=key,variant='intact'))
   if kind=='facts':
    donor=next(v for v in cases if v.get('category',v['family'])==c.get('category',c['family']) and v['answer']!=c['answer'])
    _,q=c['prefix'].rsplit('. ',1);p,_=donor['prefix'].rsplit('. ',1)
    rows.extend([dict(**{**c,'prefix':q},suite=key,variant='empty'),dict(**{**c,'prefix':p+'. '+q},suite=key,variant='shuffled')])
 return rows

def options(engine,meter):
 from tokenizer import Tokenizer
 tok=Tokenizer(str(UPSTREAM/'tokenizer.model'));mx=engine.mx;model=bind(engine);rows=[]
 for c in fixtures():
  scores=[];lengths=[]
  for option in c['options']:
   ids,n=continuation(tok,c['prefix'],option);meter.reserve(len(ids)-1,'options-'+c['suite']+'-'+c['variant'])
   logits=model(mx.array([ids[:-1]],dtype=mx.int32)).astype(mx.float32)[0,n-1:,:]
   logp=logits-mx.logsumexp(logits,axis=-1,keepdims=True)
   score=mx.sum(mx.take_along_axis(logp,mx.array(ids[n:],dtype=mx.int32)[:,None],axis=-1));mx.eval(score);engine.memory()
   scores.append(float(score));lengths.append(len(ids)-n)
  assert len(set(lengths))==1 and all(math.isfinite(x) for x in scores)
  winners=[i for i,s in enumerate(scores) if abs(s-max(scores))<=1e-8]
  rows.append(dict(**c,scores=scores,correct=len(winners)==1 and winners[0]==c['answer']))
 return rows,summarize(rows)

def summarize(rows):
 out={}
 for suite in ['freshgrammar','facts','legacygrammar','legacyfacts']:
  for variant in ['intact','empty','shuffled']:
   rs=[r for r in rows if r['suite']==suite and r['variant']==variant]
   if rs:out[suite+'_'+variant]=dict(correct=sum(r['correct'] for r in rs),total=len(rs))
 unique={}
 for r in rows:
  if r['suite']=='legacygrammar':unique.setdefault((r['prefix'],tuple(sorted(r['options']))),[]).append(r['correct'])
 assert len(unique)==45
 out['legacygrammar_unique']=dict(correct=sum(all(v) for v in unique.values()),total=45)
 return out

def generate(engine,meter,cases,out,greedy=False):
 from tokenizer import Tokenizer
 tok=Tokenizer(str(UPSTREAM/'tokenizer.model'));mx=engine.mx;model=bind(engine);stories=[]
 rng=[mx.array(x) for x in mx.random.state]
 for case in cases:
  check(meter.phase);mx.random.seed(case['seed']);ids=tok.encode(case['prefix'],bos=True,eos=False);generated=[];eos=False
  assert len(ids)<=96 and len(ids)+case['max_new_tokens']<=256
  for j in range(case['max_new_tokens']):
   meter.reserve(len(ids),'greedy-full-input' if greedy else 'sampled-full-input')
   logits=model(mx.array([ids],dtype=mx.int32))[0,-1,:].astype(mx.float32)
   if not bool(mx.all(mx.isfinite(logits))):raise RuntimeError('NONFINITE_LOGITS')
   if greedy:token=int(mx.argmax(logits).item())
   else:
    logits=logits/.7;order=mx.argsort(logits)[::-1];v=logits[order];probs=mx.softmax(v)
    token=int(order[mx.random.categorical(mx.where(mx.cumsum(probs)-probs>.9,-float('inf'),v))].item())
   engine.memory()
   if token==tok.eos_id:eos=True;break
   ids.append(token);generated.append(token)
  stories.append(dict(**case,response=tok.decode(generated),generated_ids=generated,generated_tokens=len(generated),eos=eos,BOS_positions=[i for i,t in enumerate(generated) if t==tok.bos_id],decoding='greedy' if greedy else 'sampled'))
  save(out,stories)
  print(__import__('json').dumps(dict(event='generation',mode='greedy' if greedy else 'sampled',completed=len(stories),total=len(cases))),flush=True)
 for i,x in enumerate(rng):mx.random.state[i][...] = x
 mx.eval(mx.random.state)
 return stories

def independent(path,meter,out):
 import torch
 from model import ModelArgs,Transformer
 from tokenizer import Tokenizer
 torch.set_num_threads(2);state=torch.load(path,map_location='cpu',weights_only=False)
 model=Transformer(ModelArgs(**state['model_args'])).to('mps');model.load_state_dict(state['model'],strict=True);model.eval()
 tok=Tokenizer(str(UPSTREAM/'tokenizer.model'));val=np.load(OLD/'validation.npy');losses=[];rows=[]
 with torch.no_grad():
  for i in range(0,len(val),16):
   meter.reserve(4096,'independent-fp32-validation');x=torch.tensor(val[i:i+16,:-1].astype(np.int64),device='mps');y=torch.tensor(val[i:i+16,1:].astype(np.int64),device='mps');model(x,y);losses.append(float(model.last_loss));torch.mps.synchronize()
  # All intact native spans, independently implemented NumPy suffix log probability.
  for c in [x for x in fixtures() if x['variant']=='intact']:
   scores=[]
   for option in c['options']:
    ids,n=continuation(tok,c['prefix'],option);meter.reserve(len(ids)-1,'independent-fp32-options')
    x=torch.tensor([ids[:-1]],device='mps');y=torch.tensor([ids[1:]],device='mps');logits=model(x,y)[0].float().cpu().numpy();scores.append(suffix_score(logits,ids,n))
   rows.append(dict(id=c['id'],suite=c['suite'],scores=scores,correct=int(np.argmax(scores))==c['answer'] and sum(abs(v-max(scores))<=1e-8 for v in scores)==1))
 nll=float(np.mean(losses));assert math.isfinite(nll)
 memory=dict(driver_bytes=torch.mps.driver_allocated_memory());assert memory['driver_bytes']<=12*GIB
 save(out/'fp32-options.json',rows);save(out/'fp32.json',dict(validation_nll=nll,targets=131072,backend='independent Torch MPS FP32',memory=memory));return nll,memory

def main():
 phase,backend,name=sys.argv[1:];assert phase=='R0';check(phase);freeze_check(phase);meter=Meter(phase)
 source=next(c for c in read(ROOT/'plan.json')['source_candidates'] if c['id']==name);path=PROJECT/source['path'];assert sha(path)==source['sha256'];out=ROOT/phase/name;out.mkdir(exist_ok=True)
 if backend=='mlx':
  engine,_=load_engine(path);nll=fixed_loss(engine,meter);rows,scores=options(engine,meter)
  save(out/'options.json',rows);save(out/'summary.json',dict(validation_nll=nll,**scores,dtype_proof=engine.dtype_proof))
  generate(engine,meter,read(ROOT/'cases.json')['calibration'],out/'stories.json')
  generate(engine,meter,read(ROOT/'cases.json')['calibration'],out/'greedy.json',True)
  finite(engine);assert engine.local_step==0;memory=engine.memory()
 else:nll,memory=independent(path,meter,out)
 assert sha(path)==source['sha256'],'SOURCE_MUTATED'
 save(out/f'{backend}-receipt.json',dict(source_sha256=source['sha256'],source_immutable=True,training_updates=0,memory=memory,phase_positions=Meter(phase).total(),completed_epoch=time.time()))
 print(__import__('json').dumps(dict(event='evaluation_complete',backend=backend,source=name,nll=nll)),flush=True)
if __name__=='__main__':main()
