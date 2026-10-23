"""Parameter-freeze read-only evaluations, reused across resolution phases."""
import argparse,json,math,sys,time
import numpy as np
from common import *
from scorer import continuation,controls
sys.path.insert(0,str(UPSTREAM))

def fixed_loss(engine,meter):
 val=np.load(OLD/'validation.npy');assert val.shape==(512,257)
 losses=[]
 for i in range(0,len(val),16):
  meter.reserve(16*256,'fixed-validation');losses.append(engine.validation(val[i:i+16]))
 nll=float(np.mean(losses));assert math.isfinite(nll);return nll

def options(engine,meter):
 from tokenizer import Tokenizer
 tok=Tokenizer(str(UPSTREAM/'tokenizer.model'));mx=engine.mx;model=bind(engine)
 packet=read(OLD/'packet.json');ctrl=controls(packet['grounded']);rows=[]
 for kind in ['grammar','grounded']:
  for c in packet[kind]:
   prefixes=[('intact',c['prefix'])]
   if kind=='grounded':prefixes += [('empty',ctrl[c['id']][0]),('shuffled',ctrl[c['id']][1])]
   for variant,prefix in prefixes:
    scores=[];lengths=[]
    for option in c['options']:
     joint,n=continuation(tok,prefix,option);meter.reserve(len(joint)-1,'options-'+kind+'-'+variant)
     logits=model(mx.array([joint[:-1]],dtype=mx.int32)).astype(mx.float32)[0,n-1:,:]
     logp=logits-mx.logsumexp(logits,axis=-1,keepdims=True)
     score=mx.sum(mx.take_along_axis(logp,mx.array(joint[n:],dtype=mx.int32)[:,None],axis=-1));mx.eval(score);engine.memory()
     scores.append(float(score));lengths.append(len(joint)-n)
    assert len(set(lengths))==1 and all(math.isfinite(x) for x in scores)
    winners=[i for i,s in enumerate(scores) if abs(s-max(scores))<=1e-8]
    rows.append(dict(**c,kind=kind,variant=variant,scores=scores,correct=len(winners)==1 and winners[0]==c['answer']))
 grammar=[r for r in rows if r['kind']=='grammar'];unique={}
 for r in grammar:unique.setdefault((r['prefix'],tuple(sorted(r['options']))),[]).append(r['correct'])
 assert len(unique)==45
 summary=dict(grammar_correct=sum(r['correct'] for r in grammar),grammar_unique_correct=sum(all(v) for v in unique.values()),grammar_unique_total=len(unique))
 for variant in ['intact','empty','shuffled']:summary['grounded_'+variant+'_correct']=sum(r['correct'] for r in rows if r['kind']=='grounded' and r['variant']==variant)
 return rows,summary

def generate(engine,meter,cases,out):
 from tokenizer import Tokenizer
 tok=Tokenizer(str(UPSTREAM/'tokenizer.model'));mx=engine.mx;model=bind(engine);stories=[]
 rng=[mx.array(x) for x in mx.random.state]
 for case in cases:
  check(meter.phase);mx.random.seed(case['seed']);ids=tok.encode(case['prefix'],bos=True,eos=False);generated=[];eos=False
  assert len(ids)+case['max_new_tokens']<=256
  for j in range(case['max_new_tokens']):
   meter.reserve(len(ids),'generation-full-input')
   logits=model(mx.array([ids],dtype=mx.int32))[0,-1,:].astype(mx.float32)/.7
   if not bool(mx.all(mx.isfinite(logits))):raise RuntimeError('NONFINITE_LOGITS')
   order=mx.argsort(logits)[::-1];v=logits[order];probs=mx.softmax(v)
   masked=mx.where(mx.cumsum(probs)-probs>.9,-float('inf'),v)
   token=int(order[mx.random.categorical(masked)].item());engine.memory()
   if token==tok.eos_id:eos=True;break
   ids.append(token);generated.append(token)
  bos=[i for i,t in enumerate(generated) if t==tok.bos_id]
  stories.append(dict(**case,response=tok.decode(generated),generated_ids=generated,generated_tokens=len(generated),eos=eos,BOS_positions=bos))
  save(out,stories)
  print(json.dumps(dict(event='generation',case=len(stories),total=len(cases),phase=meter.phase)),flush=True)
 for i,x in enumerate(rng):mx.random.state[i][...] = x
 mx.eval(mx.random.state)
 return stories

def main():
 a=argparse.ArgumentParser();a.add_argument('phase');a.add_argument('backend');a.add_argument('checkpoint');a.add_argument('name');a.add_argument('--stories',action='store_true');args=a.parse_args()
 check(args.phase);freeze_check(args.phase);meter=Meter(args.phase);path=PROJECT/args.checkpoint;before=sha(path)
 out=ROOT/args.name;out.mkdir(exist_ok=True)
 if args.backend=='mlx':
  engine,_=load_engine(path);nll=fixed_loss(engine,meter);rows,scores=options(engine,meter)
  save(out/'options.json',rows);save(out/'summary.json',dict(validation_nll=nll,**scores,dtype_proof=engine.dtype_proof))
  if args.stories:generate(engine,meter,read(ROOT/'probes.json')['stories'],out/'stories.json')
  memory=engine.memory()
 else:
  import torch
  torch.set_num_threads(4)
  from model import ModelArgs,Transformer
  state=torch.load(path,map_location='cpu',weights_only=False);model=Transformer(ModelArgs(**state['model_args'])).to('mps');model.load_state_dict(state['model'],strict=True);model.eval()
  val=np.load(OLD/'validation.npy');losses=[]
  with torch.no_grad():
   for i in range(0,len(val),16):
    meter.reserve(16*256,'independent-fp32-validation');x=torch.from_numpy(val[i:i+16,:-1].astype(np.int64)).to('mps');y=torch.from_numpy(val[i:i+16,1:].astype(np.int64)).to('mps');model(x,y);losses.append(float(model.last_loss));torch.mps.synchronize()
  nll=float(np.mean(losses));assert math.isfinite(nll)
  # Independent Torch suffix-option path also records FP32 option decisions.
  from tokenizer import Tokenizer
  tok=Tokenizer(str(UPSTREAM/'tokenizer.model'));packet=read(OLD/'packet.json');rows=[]
  from scorer import suffix_score
  with torch.no_grad():
   for kind in ['grammar','grounded']:
    for c in packet[kind]:
     scores=[]
     for option in c['options']:
      ids,n=continuation(tok,c['prefix'],option);meter.reserve(len(ids)-1,'independent-fp32-options')
      x=torch.tensor([ids[:-1]],device='mps');y=torch.tensor([ids[1:]],device='mps');logits=model(x,y)[0].cpu().numpy()
      scores.append(suffix_score(logits,ids,n))
     rows.append(dict(id=c['id'],kind=kind,scores=scores,correct=int(np.argmax(scores))==c['answer'] and sum(abs(v-max(scores))<=1e-8 for v in scores)==1))
  save(out/'fp32-options.json',rows);save(out/'fp32.json',dict(validation_nll=nll,targets=131072,backend='independent Torch MPS FP32'))
  memory=dict(driver_bytes=torch.mps.driver_allocated_memory());assert memory['driver_bytes']<=12*GIB
 assert sha(path)==before,'CHECKPOINT_MUTATED'
 save(out/f'{args.backend}-receipt.json',dict(checkpoint_sha256=before,checkpoint_immutable=True,memory=memory,phase_positions_reserved=meter.total(),epoch=time.time()))
 print(json.dumps(dict(event='evaluation_complete',name=args.name,backend=args.backend,nll=nll)),flush=True)
if __name__=='__main__':main()
