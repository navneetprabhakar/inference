"""Frozen-weight development-only repetition sweep; never starts training."""
import hashlib,html,json,signal,subprocess,sys,time
from pathlib import Path
import mlx.core as mx
from tokenizers import Tokenizer
from benchmark_mlx import Model
from sft_common import ROOT,configure_memory,memory_stats,generate
from evaluate_sft_v3 import evaluate_case,summarize
from train_local import atomic_json
OUT=ROOT/'reports/sft-v3/penalty-sweep-v1';RUN=ROOT/'runs/sft-v3/penalty-sweep-v1';STOP=False
PENALTIES=[1.2,1.3,1.4,1.5]
def stop(*_):
 global STOP
 STOP=True

def diagnostics(rows):
 gs=[g for r in rows if r['kind']=='chat' for g in r['generations']];return {'mean_generated_tokens':sum(g['generated_tokens'] for g in gs)/len(gs),'length_cap_fraction':sum(g['stop']=='length' for g in gs)/len(gs),'role_boundary_fraction':sum(g['stop']=='role_boundary' for g in gs)/len(gs),'empty_fraction':sum(not g['output'].strip() for g in gs)/len(gs)}
def admissible(m,baseline,diag,base_diag):
 guards={k:m[k]['strict_success_fraction']+1e-9>=baseline[k]['strict_success_fraction']-.02 for k in ['single','chain','result','grounded','error','none']}
 guards.update({k+'_exact_calls':m[k]['call_sequence_exact']+1e-9>=baseline[k]['call_sequence_exact']-.02 for k in ['single','chain']})
 guards['clarification']=m['clarify']['accepted_missing_slot_fraction']+1e-9>=baseline['clarify']['accepted_missing_slot_fraction']-.02
 guards['chat_eos']=m['chat']['eos_fraction']+1e-9>=baseline['chat']['eos_fraction']-.05
 guards['chat_not_empty']=diag['empty_fraction']<=base_diag['empty_fraction']+.02
 return guards

def main():
 import fcntl
 RUN.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True);lock=(RUN/'.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
 selected=json.loads((ROOT/'reports/sft-v3/experiment/selection.json').read_text())['selected'];cp=Path(selected['checkpoint']);digest=hashlib.sha256((cp/'model.safetensors').read_bytes()).hexdigest();data=ROOT/'data/sft-v3';data_hash=hashlib.sha256((data/'manifest.json').read_bytes()).hexdigest()
 records=[json.loads(x) for x in (data/'dev.jsonl').read_text().splitlines()];assert len(records)==550
 baseline_path=ROOT/'reports/sft-v3/experiment'/selected['name']/'dev';baseline=json.loads((baseline_path/'metrics.json').read_text());base_rows=json.loads((baseline_path/'generations.json').read_text());assert baseline['model_sha256']==digest and baseline['data_sha256']==data_hash and baseline['config']=={'penalty':1.2,'mode':'greedy','seed':100};assert [r['id'] for r in base_rows]==[r['id'] for r in records]
 pins={n:hashlib.sha256((ROOT/'scripts'/n).read_bytes()).hexdigest() for n in ['evaluate_repetition_v3.py','evaluate_sft_v3.py','sft_v3.py','sft_common.py','benchmark_mlx.py']}
 state={'status':'starting','pid':__import__('os').getpid(),'started_at':time.time(),'checkpoint':str(cp),'model_sha256':digest,'data_sha256':data_hash,'code_pins':pins,'split':'dev','cases_per_penalty':550,'penalties':PENALTIES,'completed_penalties':[],'new_training_tokens':0,'cloud_spend_usd':0,'test_set_used':False}
 old=RUN/'status.json'
 if old.exists():
  previous=json.loads(old.read_text());assert previous['code_pins']==pins and previous['model_sha256']==digest and previous['data_sha256']==data_hash
 def save():state['updated_at']=time.time();atomic_json(RUN/'status.json',state)
 atomic_json(OUT/'protocol.json',{'penalties':PENALTIES,'split':'dev','checkpoint':str(cp),'greedy':True,'seed':100,'max_new_tokens':96,'penalty_scope':'generated tokens only; includes call JSON tokens; EOS and role stopping unchanged','baseline':'reuse identical frozen 1.2 development outputs','selection':'Lowest chat repetition among settings with <=2 percentage-point loss in strict tasks, exact calls and accepted clarification; <=5pp EOS drop; <=2pp empty-answer increase. Human chat quality review still required. No automatic default change.','test_set_used':False,'new_training_tokens':0})
 configure_memory();tok=Tokenizer.from_file(str(data/'tokenizer.json'));model=Model(768,12,16384);model.load_weights(str(cp/'model.safetensors'));model.set_dtype(mx.bfloat16);mx.eval(model.parameters())
 reports={};base_metrics=summarize(base_rows);base_diag=diagnostics(base_rows)
 try:
  for penalty in PENALTIES:
   dest=OUT/str(penalty);dest.mkdir(exist_ok=True);done=dest/'metrics.json'
   if done.exists():
    report=json.loads(done.read_text());assert report['model_sha256']==digest and report['data_sha256']==data_hash;reports[str(penalty)]=report;state['completed_penalties'].append(penalty);continue
   state.update(status='evaluating',penalty=penalty,cases_completed=0);save()
   if penalty==1.2:rows=base_rows
   else:
    partial=dest/'generations.json';rows=json.loads(partial.read_text()) if partial.exists() else [];assert [r['id'] for r in rows]==[r['id'] for r in records[:len(rows)]]
    for i,rec in enumerate(records[len(rows):],start=len(rows)):
     if STOP or (RUN/'STOP').exists():raise RuntimeError('Evaluation stopped; training remains stopped')
     rows.append(evaluate_case(rec,lambda messages:generate(model,tok,messages,penalty=penalty,mode='greedy',seed=100)))
     if i%10==0:atomic_json(partial,rows);state.update(cases_completed=len(rows),memory=memory_stats());save();print('penalty',penalty,'cases',len(rows),flush=True)
   atomic_json(dest/'generations.json',rows);metrics=summarize(rows);diag=diagnostics(rows);guards=admissible(metrics,base_metrics,diag,base_diag);report={'penalty':penalty,'model_sha256':digest,'data_sha256':data_hash,'metrics':metrics,'chat_diagnostics':diag,'guards':guards,'eligible':all(guards.values()),'human_chat_quality_review':'pending','reused_baseline':penalty==1.2};atomic_json(done,report);reports[str(penalty)]=report;state['completed_penalties'].append(penalty);save()
  assert hashlib.sha256((cp/'model.safetensors').read_bytes()).hexdigest()==digest
  eligible=[r for r in reports.values() if r['eligible']];best=min(eligible,key=lambda r:(r['metrics']['chat']['mean_repeated_4gram_fraction'],r['penalty']))
  summary={'reports':reports,'provisional_recommendation':best['penalty'],'default_changed':False,'new_training_tokens':0,'test_set_used':False,'checkpoint_unchanged':True,'human_chat_quality_review':'pending'};atomic_json(OUT/'comparison.json',summary)
  subprocess.run([sys.executable,str(ROOT/'scripts/blind_sft_review.py'),*[str(OUT/str(p)/'generations.json') for p in PENALTIES],'--output',str(OUT/'blind-review')],check=True)
  body='<meta charset="utf-8"><title>Repetition penalty comparison</title><style>body{font:16px/1.6 system-ui;max-width:1050px;margin:40px auto}pre{white-space:pre-wrap;background:#eee;padding:12px}</style><h1>Frozen-weight repetition comparison</h1><p>Development cases only; no training or test-set tuning. Chat coherence requires review. Default unchanged.</p><pre>'+html.escape(json.dumps(summary,indent=2))+'</pre>'
  by_pen={str(p):json.loads((OUT/str(p)/'generations.json').read_text()) for p in PENALTIES}
  for kind in ['chat','single','chain','clarify']:
   ids=[r['id'] for r in base_rows if r['kind']==kind][:3]
   for id in ids:
    base=next(r for r in base_rows if r['id']==id);body+='<h2>'+id+'</h2><pre>'+html.escape(base['prompt'])+'</pre>'
    for p in PENALTIES:
     r=next(r for r in by_pen[str(p)] if r['id']==id);body+='<h3>Penalty '+str(p)+'</h3><pre>'+html.escape('\n\n'.join(g['output'] for g in r['generations']))+'</pre>'
  (OUT/'REPORT.html').write_text(body);state.update(status='awaiting_user_review',finished_at=time.time(),recommendation=best['penalty'],report=str(OUT/'REPORT.html'),checkpoint_unchanged=True);save()
 except Exception as e:state.update(status='stopped',error=repr(e));save();raise
if __name__=='__main__':main()
