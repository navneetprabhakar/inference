"""Local measured tool execution and generation diagnostics. No LLM judge."""
import argparse,collections,hashlib,json,re,time
from pathlib import Path
import numpy as np
import mlx.core as mx
from tokenizers import Tokenizer
from benchmark_mlx import Model
from train_local import atomic_json
from sft_common import *
from train_sft import dev_loss
from evaluate_pilot import PROMPTS,score as retention_score

def normalize(s):return ' '.join(re.findall(r'\w+',s.casefold()))
def strict_answer(text,reference):
 # Whitespace/case only: preserve numeric signs, decimal points, negation and extras.
 return ' '.join(text.casefold().split())==' '.join(reference.casefold().split())

def faithful(call,result,text):
 return strict_answer(text,result_answer(call,result))

def evaluate_record(model,tok,rec,config):
 messages=list(rec['messages']);kind=rec['kind'];r={'id':rec['id'],'kind':kind,'prompt':render(messages,True),'reference':rec['expected_answer'],'generations':[],'config':config};outputs=[];calls=rec.get('calls',[])
 def infer():
  g=generate(model,tok,messages,**config);r['generations'].append(g);outputs.append(g['output']);return g['output']
 if calls:
  exact=True;schema=True;last=None;last_call=None
  for expected in calls:
   out=infer()
   try:
    call=parse_call(out);res=execute(call)
   except (ValueError,TypeError,KeyError,ZeroDivisionError):exact=False;schema=False;break
   if call!=expected:exact=False;break
   messages += [{'role':'assistant','content':out},{'role':'tool','content':json.dumps(res,separators=(',',':'))}];last=res;last_call=call
  r.update(schema_valid=schema,call_exact=exact)
  if exact:
   answer=infer();r['canonical_result_exact_match']=faithful(last_call,last,answer);r['success']=r['canonical_result_exact_match']
  else:r['success']=False;r['canonical_result_exact_match']=False
 else:
  out=infer();attempt=CALL in out or out.lstrip().startswith('{');r['call_attempt']=attempt
  if kind=='grounded':r['success']=strict_answer(out,rec['expected_answer'])
  elif kind=='clarify':r['success']=not attempt and strict_answer(out,rec['expected_answer'])
  elif kind=='none':r['success']=None;r['tool_abstained']=not attempt;r['human_review_required']=True
  elif kind=='error':r['success']=not attempt and strict_answer(out,rec['expected_answer'])
  else:r['success']=None
 r['output']=outputs[-1] if outputs else '';return r

def summarize(rows):
 metrics={};by=collections.defaultdict(list)
 for r in rows:by[r['kind']].append(r)
 for kind,rr in by.items():
  gs=[g for r in rr for g in r['generations']];m={'cases':len(rr),'mean_repeated_4gram_fraction':sum(x['repeated_4gram_fraction'] for x in gs)/max(1,len(gs)),'eos_fraction':sum(x['stop']=='eos' for x in gs)/max(1,len(gs)),'role_boundary_stop_fraction':sum(x['stop']=='role_boundary' for x in gs)/max(1,len(gs)),'context_overflows':sum(x['stop']=='context_overflow' for x in gs)}
  if kind not in ['chat','none']:m.update(strict_success_fraction=sum(bool(r['success']) for r in rr)/len(rr),successes=sum(bool(r['success']) for r in rr))
  if kind=='none':m['tool_abstention_fraction']=sum(r['tool_abstained'] for r in rr)/len(rr);m['answer_quality']='pending blind human review'
  if kind in ['single','chain']:m.update(raw_schema_valid_fraction=sum(r['schema_valid'] for r in rr)/len(rr),exact_call_sequence_fraction=sum(r['call_exact'] for r in rr)/len(rr),canonical_result_exact_match=sum(r['canonical_result_exact_match'] for r in rr)/len(rr))
  metrics[kind]=m
 return metrics

def subset(records,counts):
 result=[]
 for kind,n in counts.items():result.extend([x for x in records if x['kind']==kind][:n])
 return result

def run(a):
 memory_policy=configure_memory()
 out=a.output;out.mkdir(parents=True,exist_ok=True);data=ROOT/'data/sft-v2';tok=Tokenizer.from_file(str(data/'tokenizer.json'));model=Model(768,12,16384);model.load_weights(str(a.checkpoint/'model.safetensors'));model.set_dtype(mx.bfloat16);mx.eval(model.parameters());dev=[json.loads(l) for l in (data/'dev.jsonl').read_text().splitlines()]
 start=time.time();base={'checkpoint':str(a.checkpoint),'model_sha256':hashlib.sha256((a.checkpoint/'model.safetensors').read_bytes()).hexdigest(),'stage':a.stage,'memory_policy':memory_policy,'paid_api_spend_usd':0,'cloud_spend_usd':0,'limitations':['Synthetic template-generated fixture tasks; not BFCL and not independent human release tests.','Chat coherence is not automatically scored. No human blind review has occurred.','Strict canonical matching rejects valid paraphrases; no-tool abstention is not answer quality. Chat/no-tool quality requires blind review.','Role-boundary stopping is an inference intervention, reported separately from learned EOS.']}
 if a.mode=='sweep':
  small=subset(dev,{'chat':20,'grounded':30,'single':50,'chain':30,'clarify':25,'none':20,'error':20});runs=[]
  for penalty in [1.,1.1,1.2,1.3]:
   for mode in ['greedy','sampled']:
    for seed in ([100] if mode=='greedy' else [100,101,102]):
     config={'penalty':penalty,'mode':mode,'seed':seed};rows=[evaluate_record(model,tok,x,config) for x in small];metrics=summarize(rows);runs.append({'config':config,'metrics':metrics,'rows':rows});atomic_json(out/'sweep.json',{'runs':runs,**base});atomic_json(out/'memory.json',memory_stats());print('sweep',config,flush=True)
  # Choose by mean across sampling seeds, never best-of-seed selection.
  ranked=[]
  for penalty in [1.,1.1,1.2,1.3]:
   for mode in ['greedy','sampled']:
    rr=[x for x in runs if x['config']['penalty']==penalty and x['config']['mode']==mode];scores=[]
    for x in rr:
     metrics=x['metrics'];primary=sum(metrics[k].get('strict_success_fraction',0) for k in ['grounded','single','chain','clarify','error'])/5;repeat=metrics['chat']['mean_repeated_4gram_fraction'];scores.append(primary-.1*repeat)
    ranked.append((sum(scores)/len(scores),penalty,mode))
  score,penalty,mode=max(ranked,key=lambda x:(x[0],-x[1],x[2]=='greedy'));atomic_json(out/'selected.json',{'penalty':penalty,'mode':mode,'seed':100,'selection_score':score,'selection':'dev only; sample settings averaged across three seeds'})
  # Also retain original literal-prefix regression probes, no special-token confound.
  legacy=[]
  for category,prompt in PROMPTS:
   for penalty in [1.,1.2]:legacy.append({'category':category,'prompt':prompt,'penalty':penalty,**generate(model,tok,[],penalty=penalty,raw_prompt=prompt)})
  atomic_json(out/'legacy-generations.json',legacy)
 else:
  config={'penalty':1.2,'mode':'greedy','seed':100}
  # Primary comparison always uses this predeclared common decoder; sweep is exploratory.
  records=[json.loads(l) for l in (data/('test.jsonl' if a.mode=='final' else 'dev.jsonl')).read_text().splitlines()]
  if a.mode=='milestone':records=subset(records,{'chat':8,'grounded':8,'single':10,'chain':4,'clarify':5,'none':5,'error':5})
  rows=[]
  for i,rec in enumerate(records):
   rows.append(evaluate_record(model,tok,rec,config))
   if i%25==0:atomic_json(out/'generations.json',rows);atomic_json(out/'memory.json',memory_stats());print('evaluation cases',i,flush=True)
  retention={}
  if a.mode=='final':
   frozen=np.load(ROOT/'runs/evaluation-v1/loss_sets.npz')
   for name in ['fineweb_validation','tinystories_unseen_shard']:retention[name]=retention_score(model,frozen[name])
  atomic_json(out/'generations.json',rows);metrics=summarize(rows);atomic_json(out/'metrics.json',{**base,'config':config,'metrics':metrics,'assistant_dev_nll':dev_loss(model,dict(np.load(data/'episodes.npz'))),'language_retention':retention})
  lines=[f'# {a.stage} — {a.mode} evaluation','','Local fixture execution and text diagnostics. All outputs are unedited. Chat pass rate requires human review. Tool result/clarification metrics are proxies, not broad capability scores.','','```json',json.dumps(metrics,indent=2),'```','']
  for r in rows:
   lines += [f"## {r['id']} ({r['kind']})",'','Prompt:','```text',r['prompt'],'```','Reference:','```text',r['reference'],'```']
   for i,g in enumerate(r['generations']):lines += [f'Output {i+1}:','```text',g['output'],'```',f"Stop: {g['stop']}",'']
  (out/'REPORT.md').write_text('\n'.join(lines)+'\n')
 atomic_json(out/'completed.json',{**base,'memory':memory_stats(),'complete':True,'seconds':time.time()-start});return 0
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--checkpoint',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--stage',required=True);p.add_argument('--mode',choices=['sweep','milestone','final'],required=True);p.add_argument('--config',type=Path);run(p.parse_args())
