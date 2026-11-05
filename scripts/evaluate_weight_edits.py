"""Isolated new-authorization evaluator. Never alters the closed eight-hour run."""
import argparse,fcntl,hashlib,json,os,time
from pathlib import Path
import mlx.core as mx
from tokenizers import Tokenizer
from benchmark_mlx import Model
from sft_common import ROOT,configure_memory,memory_stats,generate,parse_call,execute,system
from train_local import health
from inference_guard import violation
RUN=ROOT/'runs/weight-edit-experiment-v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def atomic(p,value):
 t=p.with_name(p.name+'.tmp');t.write_text(json.dumps(value,indent=2)+'\n');os.replace(t,p)
def main(a):
 auth=json.loads((RUN/'authorization.json').read_text());plan=json.loads((RUN/'edit-plan.json').read_text());out=Path(a.output).resolve();cp=Path(a.checkpoint).resolve();dataset=Path(a.dataset).resolve()
 assert out.is_relative_to(RUN) and cp.is_relative_to(ROOT) and dataset.is_relative_to(ROOT)
 out.mkdir(parents=True,exist_ok=True);output_lock=(out/'.lock').open('a');fcntl.flock(output_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 configure_memory();initial={**health(),**memory_stats()}
 def guard():
  if time.time()>=auth['deadline_unix'] or (RUN/'STOP').exists():raise RuntimeError('new_run_stop_or_deadline')
  current={**health(),**memory_stats()};reason=violation(current,initial)
  if reason:raise RuntimeError('resource_guard_'+reason)
  return current
 guard();identity={'checkpoint':str(cp.relative_to(ROOT)),'checkpoint_sha256':sha(cp/'model.safetensors'),'evaluation_sha256':sha(dataset),'decoding':plan['decoding'],'split':a.split}
 if a.split=='development':
  assert str(dataset.relative_to(ROOT))==auth['development'] and identity['evaluation_sha256']==plan['development_sha256']
 else:
  manifest=json.loads((dataset.parent/'manifest.json').read_text());assert identity['evaluation_sha256']==manifest['holdout_sha256']
  selection_path=RUN/'selection.json';selection=json.loads(selection_path.read_text());allowed=[selection['candidate'],selection['baseline']]
  assert any(identity['checkpoint']==s['checkpoint'] and identity['checkpoint_sha256']==s['sha256'] for s in allowed)
  assert selection['holdout_sha256']==identity['evaluation_sha256'] and selection['decoding']==identity['decoding']
  assert sha(dataset.parent/'rubric.json')==manifest['rubric_sha256']==selection['rubric_sha256']
  identity['selection_sha256']=sha(selection_path)
 if (out/'identity.json').exists():assert json.loads((out/'identity.json').read_text())==identity
 else:atomic(out/'identity.json',identity)
 if (out/'report.json').exists():print('Already complete; no rerun');return
 gpu=(ROOT/auth['gpu_lock']).open('a');fcntl.flock(gpu,fcntl.LOCK_EX|fcntl.LOCK_NB)
 records=[json.loads(x) for x in dataset.read_text().splitlines() if x];assert len({r['id'] for r in records})==len(records)
 rows=json.loads((out/'completed-cases.json').read_text()) if (out/'completed-cases.json').exists() else []
 assert len(rows)<=len(records)
 for previous,target in zip(rows,records):
  assert previous['id']==target['id'] and len(previous['turns'])==len(target['turns'])
  assert [t['user'] for t in previous['turns']]==[t['user'] for t in target['turns']]
 tok=Tokenizer.from_file(str(ROOT/'data/sft-v3/tokenizer.json'));model=Model(768,12,16384);model.load_weights(str(cp/'model.safetensors'));model.set_dtype(mx.bfloat16);mx.eval(model.parameters())
 began=time.time();resumed=len(rows)
 for rec in records[resumed:]:
  guard();messages=[];turns=[]
  if rec['tool_mode']:messages.append({'role':'system','content':system(list(rec['available_tools']))})
  for i,t in enumerate(rec['turns'],1):
   guard();messages.append({'role':'user','content':t['user']});g=generate(model,tok,messages,penalty=1.2,mode='greedy',seed=20261102,cap=96);messages.append({'role':'assistant','content':g['output']})
   ev={'turn':i,'user':t['user'],'student_reply':g,'tool_events':[]}
   if g['output'].strip().startswith('<|tool_call|>'):
    result=None
    try:
     call=parse_call(g['output'])
     if not rec['tool_mode'] or call['name'] not in rec['available_tools']:raise ValueError('Tool not available in this case')
     result=execute(call);ev['tool_events'].append({'call':call,'result':result,'accepted_fixture':True})
    except (ValueError,TypeError,KeyError,ZeroDivisionError,OverflowError) as exc:ev['tool_events'].append({'accepted_fixture':False,'error':type(exc).__name__})
    if result is not None:
     messages.append({'role':'tool','content':json.dumps(result,separators=(',',':'))});guard()
     final=generate(model,tok,messages,penalty=1.2,mode='greedy',seed=20261102,cap=96);ev['post_tool_student_reply']=final;messages.append({'role':'assistant','content':final['output']})
   turns.append(ev)
  rows.append({'id':rec['id'],'family':rec['family'],'tool_mode':rec['tool_mode'],'turns':turns,'semantic_review':'Requires explicit whole-answer review; no heuristic semantic pass.'});atomic(out/'completed-cases.json',rows);atomic(out/'progress.json',{'pid':os.getpid(),'completed':len(rows),'total':len(records),'updated_unix':time.time()})
 atomic(out/'raw-outputs.json',rows);report={**identity,'kind':'direct_weight_edit_local_evaluation','counts':{'conversations':len(rows),'student_turns':sum(len(r['turns']) for r in rows)},'elapsed_seconds':time.time()-began,'initial_health':initial,'final_health':guard(),'resumed_completed_cases':resumed};atomic(out/'report.json',report);print(json.dumps({'split':a.split,'conversations':len(rows),'seconds':report['elapsed_seconds'],'checkpoint_sha256':identity['checkpoint_sha256']}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--checkpoint',required=True);p.add_argument('--dataset',required=True);p.add_argument('--output',required=True);p.add_argument('--split',choices=['development','holdout'],required=True);main(p.parse_args())
