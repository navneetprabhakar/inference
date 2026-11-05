"""Sequential raw student evaluator for the frozen eight-hour v3 suites.

This deliberately writes no semantic pass label.  It persists every model
reply, every emitted tool call and deterministic fixture result for later
case-by-case assistant review.
"""
import argparse, fcntl, hashlib, json, os, time
from pathlib import Path
import mlx.core as mx
from tokenizers import Tokenizer
from benchmark_mlx import Model
from sft_common import ROOT, configure_memory, generate, parse_call, execute, system, memory_stats
from train_local import health as host_health
from inference_guard import violation, stop_requested
from goal_decoding import policy, penalty_for

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def checkpoint(p):
    p=Path(p); return p if (p/'model.safetensors').exists() else p/json.loads((p/'latest.json').read_text())['directory']
def main(a):
    decoding=policy(a.prose_penalty,a.tool_penalty)
    prompt_format=getattr(a,'prompt_format','special_roles_v1')
    if prompt_format!='special_roles_v1':decoding['prompt_format']=prompt_format
    def decode(model,tok,messages,**kwargs):
        if prompt_format=='plain_roles_v1':
            from goal_plain_roles import render
            kwargs['raw_prompt']=render(messages,True)
        return generate(model,tok,messages,**kwargs)
    root=Path(a.evaluation_root) if a.evaluation_root else ROOT/'data/eight-hour-improvement-v1/evaluation-v3'
    if not root.is_absolute(): root=ROOT/root
    manifest=json.loads((root/'manifest.json').read_text())
    if a.split=='confirmation' and not a.selection: raise RuntimeError('confirmation is sealed: frozen selection artifact required')
    records=[json.loads(x) for x in (root/(a.split+'.jsonl')).read_text().splitlines() if x]
    if sha(root/(a.split+'.jsonl')) != manifest[a.split]['sha256']: raise RuntimeError('evaluation hash mismatch')
    cp=checkpoint(a.checkpoint).resolve(); out=Path(a.output); out.mkdir(parents=True,exist_ok=True)
    lock=(out/'.evaluation.lock').open('a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if (out/'report.json').exists():
        prior=json.loads((out/'report.json').read_text())
        if prior.get('evaluation_sha256')!=manifest[a.split]['sha256'] or prior.get('checkpoint_sha256')!=sha(cp/'model.safetensors') or prior.get('decoding')!=decoding:
            raise RuntimeError('Output directory belongs to different evaluation/checkpoint; preserve it and use a new output directory')
        if not (out/'raw-outputs.json').exists(): raise RuntimeError('Completed report lacks raw outputs')
        print(json.dumps({'state':'already_completed','report':prior},indent=2)); return
    def atomic_write(path,value):
        tmp=path.with_name(path.name+'.tmp'); tmp.write_text(json.dumps(value,indent=2)+'\n'); os.replace(tmp,path)
    configure_memory(); base={**host_health(), **memory_stats()}
    goal_root=ROOT/'runs/eight-hour-improvement-v1'
    deadline=json.loads((goal_root/'authorization.json').read_text())['deadline_unix']
    def guard():
        now={**host_health(), **memory_stats()}
        reason='absolute_deadline' if time.time()>=deadline else 'stop_file' if (goal_root/'STOP').exists() else violation(now,base)
        if reason: raise RuntimeError('inference_guard_'+reason)
        return now
    guard()
    gpu_lock=(goal_root/'.training.lock').open('a'); fcntl.flock(gpu_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    receipt=None
    if a.split=='confirmation':
        from goal_confirmation_guard import authorize
        receipt=authorize(a.selection,cp,root,out,goal_root,time.time(),decoding=decoding)
    tok=Tokenizer.from_file(str(ROOT/'data/sft-v3/tokenizer.json')); model=Model(768,12,16384); model.load_weights(str(cp/'model.safetensors')); model.set_dtype(mx.bfloat16); mx.eval(model.parameters())
    all_rows=[]; started=receipt['started_unix'] if receipt else time.time()
    partial_path=out/'completed-cases.json'
    if receipt and partial_path.exists():
        all_rows=json.loads(partial_path.read_text())
        from goal_confirmation_guard import validate_completed_prefix
        validate_completed_prefix(all_rows,records)
    completed_before_resume=len(all_rows)
    for number,r in enumerate(records,1):
        if number<=completed_before_resume: continue
        guard(); messages=[]; turns=[]
        if r['tool_mode']: messages.append({'role':'system','content':system(list(r['available_tools']))})
        for turn_no,t in enumerate(r['turns'],1):
            guard()
            messages.append({'role':'user','content':t['user']}); g=decode(model,tok,messages,penalty=penalty_for(decoding,r['tool_mode']),mode='greedy',seed=20261102,cap=96)
            event={'turn':turn_no,'user':t['user'],'student_reply':g,'tool_events':[]}
            text=g['output']; messages.append({'role':'assistant','content':text})
            # A tool call is evaluated against this turn only.  The fixture is
            # executed exclusively after the exact call parser accepts it.
            if text.strip().startswith('<|tool_call|>'):
                try:
                    call=parse_call(text); result=execute(call); event['tool_events'].append({'call':call,'result':result,'accepted_fixture':True})
                    messages.append({'role':'tool','content':json.dumps(result,separators=(',',':'))})
                    guard()
                    final=decode(model,tok,messages,penalty=penalty_for(decoding,r['tool_mode']),mode='greedy',seed=20261102,cap=96)
                    event['post_tool_student_reply']=final; messages.append({'role':'assistant','content':final['output']})
                except Exception as exc: event['tool_events'].append({'accepted_fixture':False,'error':type(exc).__name__})
            turns.append(event)
        all_rows.append({'id':r['id'],'family':r['family'],'tool_mode':r['tool_mode'],'turns':turns,'semantic_review':'required: read each full turn against its explicit frozen criteria; no heuristic label is a semantic score'})
        if receipt: atomic_write(partial_path,all_rows)
        atomic_write(out/'progress.json',{'pid':os.getpid(),'completed_conversations':len(all_rows),'total_conversations':len(records),'updated_unix':time.time()})
    tool_turns=[e for r in all_rows for e in r['turns'] if e['tool_events']]
    report={'kind':'eight_hour_v3_sequential_raw_student_decode','split':a.split,'evaluation_sha256':manifest[a.split]['sha256'],'checkpoint':str(cp.relative_to(ROOT)),'checkpoint_sha256':sha(cp/'model.safetensors'),'decoding':decoding,'counts':{'conversations':len(all_rows),'student_turns':sum(len(r['turns']) for r in all_rows),'emitted_tool_turns':len(tool_turns),'accepted_fixture_calls':sum(e['tool_events'][0].get('accepted_fixture',False) for e in tool_turns)},'semantic_scoring':'not automated; raw outputs require full reply, criterion-specific assistant review per case','initial_health':base,'final_health':guard(),'elapsed_seconds':time.time()-started}
    if receipt: report['confirmation_receipt']=receipt; report['resumed_completed_cases']=completed_before_resume
    atomic_write(out/'raw-outputs.json',all_rows); atomic_write(out/'report.json',report); print(json.dumps(report,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--checkpoint',required=True); p.add_argument('--split',choices=['development','confirmation'],required=True); p.add_argument('--output',required=True); p.add_argument('--evaluation-root'); p.add_argument('--selection'); p.add_argument('--prompt-format',choices=['special_roles_v1','plain_roles_v1'],default='special_roles_v1'); p.add_argument('--prose-penalty',type=float,default=1.2); p.add_argument('--tool-penalty',type=float,default=1.2); main(p.parse_args())
