"""Strict V3 closed-loop evaluator. New test set requires explicit unlock; no training."""
import argparse,collections,hashlib,json,time
from pathlib import Path
from sft_v3 import *
from train_local import atomic_json

def evaluate_case(rec,infer):
 messages=list(rec['messages']);calls=rec.get('calls',[]);outputs=[]
 row={'id':rec['id'],'family':rec['family'],'kind':rec['kind'],'prompt':render(messages,True),'reference':rec['expected_answer'],'generations':outputs,'steps':[],'human_review_required':rec['kind']=='chat'}
 def generate_one():
  g=infer(messages);outputs.append(g);return g['output']
 if calls:
  prefix=True;complete=True
  for step,expected in enumerate(calls):
   out=generate_one();diagnostic={'index':step,'reached':True,'prefix_correct_before':prefix,'schema_valid':False,'name_exact':False,'call_exact':False,'argument_exact':{k:False for k in expected['arguments']}}
   try:
    call=parse_call(out);diagnostic.update(compare_call(rec,call,expected))
    if not diagnostic['schema_valid']:raise ValueError('Invalid schema')
    result=run_fixture(rec,call,step)
   except (ValueError,TypeError,KeyError,ZeroDivisionError) as e:
    diagnostic['error']=type(e).__name__;row['steps'].append(diagnostic);complete=False;prefix=False;break
   prefix=prefix and diagnostic['call_exact'];row['steps'].append(diagnostic)
   messages += [msg('assistant',out),msg('tool',json.dumps(result,separators=(',',':')))];diagnostic['executed_result']=result
  for step in range(len(row['steps']),len(calls)):
   row['steps'].append({'index':step,'reached':False,'prefix_correct_before':False,'schema_valid':False,'name_exact':False,'call_exact':False,'argument_exact':{k:False for k in calls[step]['arguments']}})
  answer=generate_one() if complete else ''
  row['call_sequence_exact']=prefix and complete
  row['canonical_answer_exact']=exact_answer(answer,rec['expected_answer']) if complete else False
  row['accepted_answer_exact']=accepted_answer(answer,rec) if complete else False
  row['answer_after_exact_calls']=row['canonical_answer_exact'] if row['call_sequence_exact'] else None
  row['success']=row['call_sequence_exact'] and row['canonical_answer_exact']
 else:
  answer=generate_one();attempt=CALL in answer or answer.lstrip().startswith('{');row['call_attempt']=attempt
  row['canonical_answer_exact']=exact_answer(answer,rec['expected_answer']);row['accepted_answer_exact']=accepted_answer(answer,rec)
  if rec['kind']=='chat':row['success']=None
  elif rec['kind']=='none':
   row['tool_abstained']=not attempt;row['success']=not attempt and row['canonical_answer_exact'];row['human_review_required']=not row['accepted_answer_exact']
  else:row['success']=not attempt and row['canonical_answer_exact']
  if rec['kind']=='clarify':row['missing_slot']=rec['missing_slot'];row['missing_slot_reference_match']=not attempt and row['accepted_answer_exact']
 # Numeric tokens differ => evidence of a copying error. Equality is NOT semantic faithfulness.
 row['numeric_tokens_match_reference']=numbers(answer)==numbers(rec['expected_answer']);row['output']=answer
 return row

def summarize(rows):
 metrics={}
 for kind in sorted({r['kind'] for r in rows}):
  rr=[r for r in rows if r['kind']==kind];gs=[g for r in rr for g in r['generations']];scored=[r for r in rr if r['success'] is not None]
  m={'cases':len(rr),'scored_cases':len(scored),'strict_success_fraction':sum(bool(r['success']) for r in scored)/len(scored) if scored else None,'accepted_reference_fraction':sum(r['accepted_answer_exact'] for r in rr)/len(rr),'human_review_pending':sum(r['human_review_required'] for r in rr),'mean_repeated_4gram_fraction':sum(g.get('repeated_4gram_fraction',0) for g in gs)/max(1,len(gs)),'eos_fraction':sum(g.get('stop')=='eos' for g in gs)/max(1,len(gs)),'context_overflows':sum(g.get('stop')=='context_overflow' for g in gs)}
  if kind in ['single','chain']:
   ss=[s for r in rr for s in r['steps']];reached=[s for s in ss if s['reached']];exact=[r for r in rr if r['call_sequence_exact']]
   m.update(attempted_steps=len(reached),expected_steps=len(ss),schema_valid_given_attempt=sum(s['schema_valid'] for s in reached)/max(1,len(reached)),call_sequence_exact=sum(r['call_sequence_exact'] for r in rr)/len(rr),answer_given_exact_calls={'cases':len(exact),'fraction':sum(r['answer_after_exact_calls'] for r in exact)/len(exact) if exact else None},per_step={})
   for i in sorted({s['index'] for s in ss}):
    subset=[s for s in ss if s['index']==i];conditional=[s for s in subset if s['prefix_correct_before']];fields=collections.defaultdict(list)
    for s in subset:
     for k,v in s['argument_exact'].items():fields[k].append(v)
    m['per_step'][str(i+1)]={'cases':len(subset),'reached':sum(s['reached'] for s in subset),'exact_fraction':sum(s['call_exact'] for s in subset)/len(subset),'given_correct_prefix_cases':len(conditional),'exact_given_correct_prefix':sum(s['call_exact'] for s in conditional)/len(conditional) if conditional else None,'argument_accuracy':{k:{'cases':len(v),'correct':sum(v),'fraction':sum(v)/len(v)} for k,v in fields.items()}}
  if kind=='none':m['tool_abstention_fraction']=sum(r['tool_abstained'] for r in rr)/len(rr)
  if kind=='clarify':m['accepted_missing_slot_fraction']=sum(r['missing_slot_reference_match'] for r in rr)/len(rr)
  metrics[kind]=m
 return metrics

def main(a):
 if a.split=='test' and not a.unlock_test:raise RuntimeError('Fresh test locked. Select on development data; explicitly unlock once after review.')
 import mlx.core as mx
 from tokenizers import Tokenizer
 from benchmark_mlx import Model
 configure_memory();data=ROOT/'data/sft-v3';manifest=json.loads((data/'manifest.json').read_text())
 for n,digest in manifest['files'].items():assert hashlib.sha256((data/n).read_bytes()).hexdigest()==digest,n
 tok=Tokenizer.from_file(str(data/'tokenizer.json'));m=Model(768,12,16384);m.load_weights(str(a.checkpoint/'model.safetensors'));m.set_dtype(mx.bfloat16);mx.eval(m.parameters());records=[json.loads(x) for x in (data/f'{a.split}.jsonl').read_text().splitlines()];rows=[];a.output.mkdir(parents=True,exist_ok=True)
 assert not (a.output/'metrics.json').exists(),'Use a new output directory'
 for i,r in enumerate(records):
  rows.append(evaluate_case(r,lambda messages:generate(m,tok,messages,penalty=1.2,mode='greedy',seed=100)))
  if i%25==0:atomic_json(a.output/'generations.json',rows);atomic_json(a.output/'memory.json',memory_stats());print(i,flush=True)
 from evaluate_pilot import score as retention_score
 frozen=np.load(ROOT/'runs/evaluation-v1/loss_sets.npz');retention={name:retention_score(m,frozen[name]) for name in ['fineweb_validation','tinystories_unseen_shard']}
 atomic_json(a.output/'generations.json',rows);atomic_json(a.output/'metrics.json',{'split':a.split,'checkpoint':str(a.checkpoint),'model_sha256':hashlib.sha256((a.checkpoint/'model.safetensors').read_bytes()).hexdigest(),'data_sha256':hashlib.sha256((data/'manifest.json').read_bytes()).hexdigest(),'config':{'penalty':1.2,'mode':'greedy','seed':100},'metrics':summarize(rows),'language_retention':retention,'limitations':['Canonical and finite accepted-reference matches are not general semantic judges.','Chat quality remains pending blind human review.','Case-local external outputs are offline fixtures. Wrong executable calls receive their own result and the trajectory continues.','Fresh cases are template-correlated; do not treat every row as independent evidence.'],'cloud_spend_usd':0})
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--checkpoint',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--split',choices=['dev','test'],default='dev');p.add_argument('--unlock-test',action='store_true');main(p.parse_args())
