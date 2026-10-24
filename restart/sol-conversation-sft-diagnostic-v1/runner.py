"""Own-checkpoint, masked native-MLX SFT diagnostic. No foundation-stage resume or teacher calls."""
import copy,hashlib,importlib.util,json,math,os,random,signal,sys,time
from collections import Counter
from pathlib import Path
import numpy as np
from sentencepiece import SentencePieceProcessor
ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parents[1];PRIVATE=ROOT/'private'
SOURCE=PROJECT/'restart/foundation-resolution-v1/B/checkpoint.pt'
SOURCE_SHA='bf45241501cee600bd618677dc1a3ae666e6f50d9c628e29e7326ee9c87d338d'
UPSTREAM=PROJECT/'restart/mac15m-feasibility-v1/upstream'
TOK=UPSTREAM/'tokenizer.model'
started=None;positions=0;supervised=0;updates=0

def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
 return h.hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n');tmp.replace(p)
def check():
 if time.time()-started>=2700:raise TimeoutError('45-minute wall cap')
 import psutil
 if psutil.disk_usage(PROJECT).free<60*1024**3:raise RuntimeError('DISK_FLOOR_60_GIB')
 if psutil.Process().memory_info().rss>12*1024**3:raise RuntimeError('RSS_CAP_12_GIB')
def reserve(n,kind):
 global positions
 check()
 if positions+n>2000000:raise RuntimeError('2M_POSITION_CAP')
 positions+=n;save(ROOT/'work.json',dict(positions=positions,last_operation=kind,updates=updates,supervised_targets=supervised))
def serialize(sp,messages):
 ids=[sp.bos_id()];mask=[0];spans=[]
 assert len(messages)%2==0
 for i in range(0,len(messages),2):
  u,a=messages[i:i+2];assert u['role']=='user' and a['role']=='assistant'
  prefix=sp.encode('User: '+u['content']+'\nAssistant:');ids+=prefix;mask += [0]*len(prefix)
  begin=len(ids);answer=sp.encode(a['content']);ids+=answer+[sp.eos_id()];mask += [1]*(len(answer)+1)
  spans.append(dict(start=begin,end=len(ids),eos=len(ids)-1))
 assert len(ids)==len(mask) and all(ids[s['eos']]==sp.eos_id() for s in spans)
 return np.array(ids,np.int32),np.array(mask,np.float32),spans

def prompt(sp,messages):
 ids=[sp.bos_id()]
 for i,m in enumerate(messages):
  if m['role']=='user':ids+=sp.encode('User: '+m['content']+'\nAssistant:')
  else:ids+=sp.encode(m['content'])+[sp.eos_id()]
 return ids

def cases():
 # Private authored probes are frozen before any model execution; do not expose their text in Git.
 rows=read(PRIVATE/'probes.json')
 assert sum(len(r['users']) for r in rows)==24
 return rows


def prepare():
 sp=SentencePieceProcessor(model_file=str(TOK));selection=read(PRIVATE/'selection.json');reviews=read(PRIVATE/'review.json');freeze=read(ROOT/'selection-freeze.json')
 assert sha(PRIVATE/'selection.json')==freeze['selection_sha256'];assert len(reviews)==84
 datasets={};counts={};excluded=[]
 for split in ['train','development','test']:
  data=[];c=Counter()
  for r in selection:
   if r['split']!=split:continue
   if reviews[r['id']]['decision']!='pass':excluded.append(dict(id=r['id'],reason='PRIMARY_HOLD'));continue
   ids,m,spans=serialize(sp,r['messages'])
   if len(ids)>257:excluded.append(dict(id=r['id'],reason='EXACT_FORMAT_EXCEEDS_CONTEXT'));continue
   # Prefix identity is tested for every assistant turn, including the second/third turn.
   for i,s in enumerate(spans):assert prompt(sp,r['messages'][:2*i+1])==list(ids[:s['start']])
   assert len(m[1:])==len(ids)-1 and np.sum(m)==sum(len(sp.encode(x['content']))+1 for x in r['messages'] if x['role']=='assistant')
   data.append(dict(id=r['id'],family=r['family'],ids=ids.tolist(),mask=m.tolist(),messages=r['messages']))
   c.update(documents=1,content_tokens=sum(len(sp.encode(x['content'])) for x in r['messages']),assistant_content_tokens=sum(len(sp.encode(x['content'])) for x in r['messages'] if x['role']=='assistant'),supervised_targets=int(m.sum()),sequence_positions=len(ids)-1)
  datasets[split]=data;counts[split]=dict(c)
 assert len(datasets['train'])>=48 and len(datasets['development'])>=6 and len(datasets['test'])>=6
 trainfamilies={r['family'] for r in datasets['train']};assert len(trainfamilies)>=12
 assert not trainfamilies&{r['family'] for s in ['development','test'] for r in datasets[s]}
 save(PRIVATE/'datasets.json',datasets);save(PRIVATE/'probes.json',cases())
 save(ROOT/'data-receipt.json',dict(counts=counts,excluded=excluded,all_selected_directly_reviewed=True,format='BOS; per user turn encode(User: text\\nAssistant:); assistant content; EOS. Segments encoded independently, identically at inference.',mask='Assistant content and EOS only; next-token shift once; user/role labels and padding have zero loss.',dataset_sha256=sha(PRIVATE/'datasets.json'),probe_sha256=sha(PRIVATE/'probes.json'),tokenizer_sha256=sha(TOK),probe_turns=24,heldout_policy='Previously inspected synthetic holdouts and newly authored frozen probes; not sealed independent benchmarks.'))
 save(ROOT/'plan.json',dict(owner_instruction='go ahead',authority='One separately bounded SFT diagnostic following readiness response; does not resume failed foundation-recovery D0/R1/R2.',source_checkpoint=str(SOURCE.relative_to(PROJECT)),source_sha256=SOURCE_SHA,parameters=15191712,optimizer='Fresh AdamW states; FP32 master parameters and moments, BF16 compute; betas 0.9/0.95; eps1e-8; matrix decay0.1; norms0; clip1.',maximum_epochs=3,maximum_updates=24,batch=8,context=256,learning_rate=5e-5,warmup_updates=2,maximum_supervised_targets=60000,maximum_total_positions=2000000,wall_seconds=2700,correctness=dict(masked_loss_vs_independent_fp32_abs_max=.02,gradient_relative_L2_max=.08,gradient_cosine_min=.995,masked_label_change_loss_abs_max=1e-6,padding_change_loss_abs_max=1e-6),stops=dict(nonfinite=True,gradient_norm_above=100,foundation_nll_increase_fraction=.05,development_nll_increase_fraction=.10),selection='Lowest development assistant NLL among non-regressing epoch checkpoints; test never selects checkpoint.',success=dict(dev_assistant_nll_reduction_fraction_min=.05,manual_probe_correct_min=6,manual_probe_improvement_min=4,foundation_nll_increase_fraction_max=.05),after_stop='No more updates; read-only response assessment allowed. No checkpoint auto-promotion, further training or automatic retries.',source_sha256s={str(p.relative_to(PROJECT)):sha(p) for p in [Path(__file__),PROJECT/'restart/foundation-stage3-v1/engine.py',PROJECT/'restart/foundation-stage3-v1/engine_support.py',PROJECT/'restart/foundation-recovery-v2-corrected/common.py']},new_teacher_calls=0,new_downloads=0))
 print(json.dumps(dict(event='prepared',counts=counts,excluded=excluded)),flush=True)


def load():
 spec=importlib.util.spec_from_file_location('diagnostic_common',PROJECT/'restart/foundation-recovery-v2-corrected/common.py');common=importlib.util.module_from_spec(spec);spec.loader.exec_module(common)
 engine,support=common.load_engine(SOURCE,'bf16',schedule=lambda _:5e-5)
 common.mapping=sys.modules['engine_support'].mapping
 mx=engine.mx
 for opt,names in [(engine.om,engine.matrix),(engine.on,engine.norm)]:
  opt.state['step']=mx.array(0,mx.uint64)
  for k in names:
   opt.state[k]['m']=mx.zeros_like(engine.params[k]);opt.state[k]['v']=mx.zeros_like(engine.params[k])
 mx.eval(engine.om.state,engine.on.state)
 return engine,common

def collate(rows):
 x=np.zeros((len(rows),256),np.int32);y=x.copy();mask=np.zeros_like(x,np.float32);lengths=[]
 for i,r in enumerate(rows):
  ids=np.array(r['ids'],np.int32);m=np.array(r['mask'],np.float32);n=len(ids)-1
  x[i,:n]=ids[:-1];y[i,:n]=ids[1:];mask[i,:n]=m[1:];lengths.append(n)
 return x,y,mask,lengths

def loss_functions(e):
 from mlx.utils import tree_unflatten
 mx=e.mx;nn=e.nn
 def loss_fn(params,x,y,mask):
  e.model.update(tree_unflatten([(k,v.astype(mx.bfloat16)) for k,v in params.items()]))
  logits=e.model(x).astype(mx.float32);ce=nn.losses.cross_entropy(logits,y,reduction='none')
  return mx.sum(ce*mask)/mx.sum(mask)
 return mx.compile(loss_fn),mx.compile(mx.value_and_grad(loss_fn))

def evaluate_loss(e,fn,rows,label):
 total=0.;denom=0
 for j in range(0,len(rows),8):
  x,y,m,_=collate(rows[j:j+8]);reserve(x.size,label);n=int(m.sum());value=fn(e.params,e.mx.array(x),e.mx.array(y),e.mx.array(m));e.mx.eval(value);e.memory();assert math.isfinite(float(value));total+=float(value)*n;denom+=n
 return total/denom

def foundation(e,label):
 arr=np.load(PROJECT/'restart/foundation-stage3-v1/validation.npy');assert arr.shape==(512,257)
 losses=[]
 for i in range(0,512,16):reserve(4096,label);losses.append(e.validation(arr[i:i+16]))
 return float(np.mean(losses))

def correctness(e,fn,gfn,rows,common):
 import torch
 sys.path.insert(0,str(UPSTREAM))
 from model import ModelArgs,Transformer
 mx=e.mx;x,y,m,lengths=collate(rows[:2]);reserve(x.size*4,'masked-preflight')
 loss,g=gfn(e.params,mx.array(x),mx.array(y),mx.array(m));mx.eval(loss,g)
 ybad=np.where(m>0,y,(y+7)%32000).astype(np.int32);z=fn(e.params,mx.array(x),mx.array(ybad),mx.array(m));mx.eval(z);labeldiff=abs(float(z)-float(loss));assert labeldiff<=1e-6
 xpad=x.copy()
 for i,n in enumerate(lengths):xpad[i,n:]=17
 z=fn(e.params,mx.array(xpad),mx.array(y),mx.array(m));mx.eval(z);paddiff=abs(float(z)-float(loss));assert paddiff<=1e-6
 torch.set_num_threads(2);t=Transformer(ModelArgs(**e.origin['model_args']));t.load_state_dict(e.origin['model'],strict=True);t.eval()
 logits=t(torch.tensor(x,dtype=torch.long),torch.tensor(y,dtype=torch.long));ce=torch.nn.functional.cross_entropy(logits.reshape(-1,32000),torch.tensor(y.reshape(-1),dtype=torch.long),reduction='none').reshape(y.shape)
 tm=torch.tensor(m);tl=(ce*tm).sum()/tm.sum();tl.backward()
 aa=bb=dot=diff=0.
 for old,p in t.named_parameters():
  a=p.grad.detach().numpy().astype(np.float64);b=np.array(g[common.mapping()[old]]).astype(np.float64)
  aa+=float(np.sum(a*a));bb+=float(np.sum(b*b));dot+=float(np.sum(a*b));diff+=float(np.sum((a-b)**2))
 relative=math.sqrt(diff/aa);cosine=dot/math.sqrt(aa*bb);delta=abs(float(loss)-float(tl.detach()))
 receipt=dict(status='PASS',mlx_masked_nll=float(loss),independent_torch_fp32_masked_nll=float(tl.detach()),absolute_nll_difference=delta,gradient_relative_L2=relative,gradient_cosine=cosine,masked_label_change_loss_difference=labeldiff,padding_input_change_loss_difference=paddiff,source_weights_unmodified=True,updates=0)
 save(ROOT/'correctness.json',receipt)
 assert delta<=.02 and relative<=.08 and cosine>=.995,'MASKED_NUMERICAL_CHECK_FAILED'
 del t,logits,ce,tl,g
 print(json.dumps(dict(event='correctness',**receipt)),flush=True)

def generate(e,sp,bank,label):
 from mlx.utils import tree_unflatten
 mx=e.mx;e.model.update(tree_unflatten([(k,v.astype(mx.bfloat16)) for k,v in e.params.items()]))
 result=[]
 for case in bank:
  messages=[]
  for turn,user in enumerate(case['users']):
   messages.append(dict(role='user',content=user));ids=prompt(sp,messages);assert len(ids)+48<=256
   out=[];stop_token=None
   for j in range(48):
    reserve(len(ids),'response-'+label);logits=e.model(mx.array([ids],mx.int32))[0,-1,:].astype(mx.float32);mx.eval(logits);e.memory()
    if not bool(mx.all(mx.isfinite(logits))):raise RuntimeError('NONFINITE_GENERATION')
    token=int(mx.argmax(logits).item())
    if token in [sp.eos_id(),sp.bos_id()]:stop_token=token;break
    out.append(token);ids.append(token)
   text=sp.decode(out);result.append(dict(id=case['id'],turn=turn,user=user,response=text,generated_ids=out,stop_token=stop_token,expected=case['expected'][turn],decoding='greedy; max48; stopBOSorEOS; no truncation, rerolls or best-of'))
   messages.append(dict(role='assistant',content=text))
  save(PRIVATE/f'{label}-responses.json',result)
 print(json.dumps(dict(event='responses_complete',label=label,responses=len(result))),flush=True)
 return result

def checkpoint(e,common,epoch):
 import torch
 global updates,supervised
 base=e.base_step;e.base_step=0
 try:old=e.checkpoint()
 finally:e.base_step=base
 state={k:old[k] for k in ['model','model_args','optimizer','mlx_rng_state','compute_precision']};state.update(optimizer_step=updates,schema='own-native-sft-diagnostic-v1',foundation_source_sha256=SOURCE_SHA,foundation_source_optimizer_step=3145,foundation_retained_targets=412221440,sft_supervised_targets=supervised,sft_updates=updates,epoch=epoch,chat_format_sha256=sha(ROOT/'data-receipt.json'))
 path=ROOT/f'epoch-{epoch}.pt';tmp=ROOT/f'epoch-{epoch}.tmp.pt';torch.save(state,tmp);tmp.replace(path)
 loaded=torch.load(path,map_location='cpu',weights_only=False);assert loaded['optimizer_step']==updates
 for oldname,new in common.mapping().items():assert np.array_equal(loaded['model'][oldname].numpy(),np.array(e.params[new]))
 return path

def main():
 global started,updates,supervised
 signal.signal(signal.SIGTERM,lambda *_:(_ for _ in ()).throw(KeyboardInterrupt('Terminated')))
 if (ROOT/'started.json').exists():raise RuntimeError('NO_AUTOMATIC_RETRY')
 assert sha(SOURCE)==SOURCE_SHA
 prepare();started=time.time();save(ROOT/'started.json',dict(epoch=started,pid=os.getpid(),source_sha256=SOURCE_SHA))
 plan=read(ROOT/'plan.json')
 for path,digest in plan['source_sha256s'].items():assert sha(PROJECT/path)==digest
 data=read(PRIVATE/'datasets.json');sp=SentencePieceProcessor(model_file=str(TOK));e,common=load();fn,gfn=loss_functions(e)
 correctness(e,fn,gfn,data['train'],common)
 baseline=dict(foundation_nll=foundation(e,'baseline-foundation'),development_assistant_nll=evaluate_loss(e,fn,data['development'],'baseline-dev'),test_assistant_nll=evaluate_loss(e,fn,data['test'],'baseline-test'))
 save(ROOT/'baseline.json',baseline);generate(e,sp,read(PRIVATE/'probes.json'),'before')
 history=[];selected=None;best=float('inf');hard_stop=None
 for epoch in range(1,4):
  order=list(data['train']);random.Random(24102400+epoch).shuffle(order);epoch_start=time.time()
  for i in range(0,len(order),8):
   x,y,m,_=collate(order[i:i+8]);n=int(m.sum());assert updates<24 and supervised+n<=60000
   reserve(x.size,'sft-train');value,g=gfn(e.params,e.mx.array(x),e.mx.array(y),e.mx.array(m));e.mx.eval(value,g);assert math.isfinite(float(value))
   norm=e.mx.sqrt(sum(e.mx.sum(v*v) for v in g.values()));e.mx.eval(norm)
   if not math.isfinite(float(norm)) or float(norm)>100:raise RuntimeError('GRADIENT_HARD_STOP')
   lr=5e-5*min(1.,(updates+1)/2);e.params,clipped=e.step_fn(e.params,g,e.mx.array(lr));e.mx.eval(e.params,e.om.state,e.on.state,clipped);e.local_step+=1;updates+=1;supervised+=n
   common.finite(e);e.memory();save(ROOT/'progress.json',dict(epoch=epoch,updates=updates,supervised_targets=supervised,positions=positions,loss=float(value),gradient_norm=float(norm),learning_rate=lr,elapsed_seconds=time.time()-started))
  path=checkpoint(e,common,epoch);dev=evaluate_loss(e,fn,data['development'],'epoch-dev');base=foundation(e,'epoch-foundation')
  r=dict(epoch=epoch,updates=updates,supervised_targets=supervised,development_assistant_nll=dev,foundation_nll=base,checkpoint=str(path.relative_to(PROJECT)),sha256=sha(path),elapsed_seconds=time.time()-started,epoch_train_and_eval_seconds=time.time()-epoch_start)
  history.append(r);save(ROOT/'history.json',history);print(json.dumps(dict(event='epoch_complete',**r)),flush=True)
  if base>baseline['foundation_nll']*1.05:hard_stop='FOUNDATION_REGRESSION_ABOVE_5_PERCENT';break
  if dev>baseline['development_assistant_nll']*1.10:hard_stop='DEVELOPMENT_REGRESSION_ABOVE_10_PERCENT';break
  if dev<best:best=dev;selected=r
 # A regression ends updates. Read-only assessment uses the best safe epoch, or the last rejected child if none were safe.
 chosen=selected or history[-1]
 import torch
 restored=torch.load(PROJECT/chosen['checkpoint'],map_location='cpu',weights_only=False)
 e.params={new:e.mx.array(restored['model'][old].numpy(),dtype=e.mx.float32) for old,new in common.mapping().items()};e.mx.eval(e.params)
 final_test=evaluate_loss(e,fn,data['test'],'final-test');generate(e,sp,read(PRIVATE/'probes.json'),'after')
 assert sha(SOURCE)==SOURCE_SHA
 save(ROOT/'result.json',dict(status='BOUNDED_TEST_COMPLETE_PENDING_RESPONSE_ASSESSMENT',training_stop=hard_stop,baseline=baseline,selected_checkpoint=chosen,selected_checkpoint_is_safe=selected is not None,final_test_assistant_nll=final_test,training_updates=updates,sft_supervised_target_exposures=supervised,total_positions=positions,elapsed_seconds=time.time()-started,memory=e.memory(),source_sha256_unchanged=True,parameters=15191712,checkpoint_promoted=False,more_training_authorized=False))
 print(json.dumps(read(ROOT/'result.json')),flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as err:
  save(ROOT/'STOP.json',dict(error=type(err).__name__,detail=str(err),epoch=time.time(),updates=updates,supervised_targets=supervised,positions=positions,source_sha256_unchanged=sha(SOURCE)==SOURCE_SHA));raise
