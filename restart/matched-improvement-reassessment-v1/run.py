"""Matched descriptive improvement assessment; inference only, no model decision or training."""
import gc,importlib.util,json,os,re,time
from pathlib import Path
from sentencepiece import SentencePieceProcessor
R=Path(__file__).resolve().parent;P=R.parents[1];V=R/'private'
spec=importlib.util.spec_from_file_location('fresh_factual_inference_helper',P/'restart/sol-conversation-sft-diagnostic-v1/runner.py');s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
ORIGINAL=s.SOURCE;ORIGINAL_SHA=s.SOURCE_SHA
started=None;positions=0;peak_rss=0

def read(p):return json.loads(p.read_text())
def save(p,x):
 tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(x,indent=2)+'\n');tmp.replace(p)
def frozen():
 for path,digest in read(R/'freeze.json')['files'].items():assert s.sha(P/path)==digest,path

def reserve(n):
 global positions,peak_rss
 import psutil
 if time.time()-started>=900:raise TimeoutError('15_MINUTE_INFERENCE_WALL_CAP')
 if positions+n>2000000:raise RuntimeError('2M_INFERENCE_POSITION_CAP')
 rss=psutil.Process().memory_info().rss;peak_rss=max(peak_rss,rss)
 if rss>12*1024**3:raise RuntimeError('12_GIB_RSS_CAP')
 if psutil.disk_usage(P).free<60*1024**3:raise RuntimeError('60_GIB_DISK_FLOOR')
 if sum(p.stat().st_size for p in R.rglob('*') if p.is_file())>1024**3:raise RuntimeError('1_GIB_ARTIFACT_CAP')
 positions+=n
 save(R/'work.json',dict(inference_positions=positions,training_updates=0,elapsed_seconds=time.time()-started,peak_rss_bytes=peak_rss))
def norm(text):return re.findall(r'\w+',text.casefold())
def generate(e,common,bank,sp,label):
 mx=e.mx;model=common.bind(e);rows=[]
 for case in bank:
  context=[]
  for turn in range(len(case['oracle'])):
   user=case['messages'][turn*2];context.append(user);ids=s.prompt(sp,context);assert len(ids)+32<=256
   tokens=[];stop=None
   for k in range(32):
    reserve(len(ids));logits=model(mx.array([ids],mx.int32))[0,-1,:].astype(mx.float32);mx.eval(logits);e.memory()
    if not bool(mx.all(mx.isfinite(logits))):raise RuntimeError('NONFINITE_LOGITS')
    token=int(mx.argmax(logits).item())
    if token in [sp.bos_id(),sp.eos_id()]:stop=token;break
    tokens.append(token);ids.append(token)
   text=sp.decode(tokens)
   rows.append(dict(id=case['id'],family=case['family'],section=case['section'],wording=case['wording'],value_level=case['value_level'],condition=case['condition'],turn=turn,user=user['content'],expected=case['oracle'][turn],response=text,generated_ids=tokens,stop_token=stop,eos=stop==sp.eos_id(),exact_normalized=norm(text)==norm(case['oracle'][turn])))
   context.append(dict(role='assistant',content=text))
   save(V/(label+'-responses.json'),rows)
 return dict(turns=len(rows),eos=sum(x['eos'] for x in rows),exact_answers=sum(x['exact_normalized'] for x in rows),positions_after_model=positions,raw_responses_sha256=s.sha(V/(label+'-responses.json')),memory=e.memory(),new_training_updates=e.local_step)

def main():
 global started
 if (R/'started.json').exists():raise RuntimeError('NO_AUTOMATIC_INFERENCE_RETRY')
 frozen();started=time.time();save(R/'started.json',dict(epoch=started,pid=os.getpid(),purpose='New user-authorized inference-only assessment; does not reset any closed training clock.'))
 plan=read(R/'plan.json');bank=read(V/'bank.json');sp=SentencePieceProcessor(model_file=str(s.TOK));result={}
 for name,config in plan['models'].items():
  frozen();s.SOURCE=P/config['path'];s.SOURCE_SHA=config['sha256'];e,c=s.load()
  result[name]=generate(e,c,bank,sp,name);assert e.local_step==0
  print(json.dumps(dict(event='inference_complete',model=name,**result[name])),flush=True);del e,c;gc.collect()
 frozen();assert s.sha(ORIGINAL)==ORIGINAL_SHA
 save(R/'result.json',dict(status='MATCHED_ASSESSMENT_CLOSED_PENDING_SEMANTIC_REVIEW',decision_deferred=True,models=result,training_updates=0,inference_positions=positions,elapsed_seconds=time.time()-started,peak_rss_bytes=peak_rss,all_frozen_inputs_unchanged=True,original_foundation_unchanged=True,promotion=False,automatic_continuation=False))
if __name__=='__main__':
 try:main()
 except BaseException as error:
  save(R/'STOP.json',dict(error=type(error).__name__,detail=str(error),training_updates=0,inference_positions=positions,elapsed_seconds=time.time()-started if started else None));raise
