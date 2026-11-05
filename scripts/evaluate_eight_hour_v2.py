"""One-shot raw decoder for the v2 frozen conversation evaluation."""
import argparse, hashlib, json, time
from pathlib import Path
import mlx.core as mx
from tokenizers import Tokenizer
from benchmark_mlx import Model
from sft_common import ROOT, configure_memory, generate, memory_stats
from author_eval_scoring import tool_trace
from train_local import health as host_health
from inference_guard import violation, stop_requested

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def checkpoint(p):
    p=Path(p)
    return p if (p/'model.safetensors').exists() else p/json.loads((p/'latest.json').read_text())['directory']
def main(a):
    root=ROOT/'data/eight-hour-improvement-v1/evaluation-v2'; m=json.loads((root/'manifest.json').read_text())
    if a.split=='confirmation' and not Path(a.selection).exists(): raise RuntimeError('confirmation is sealed until development selection exists')
    records=[json.loads(x) for x in (root/(a.split+'.jsonl')).read_text().splitlines() if x]
    if len(records)!=m[a.split]['cases']: raise RuntimeError('evaluation count mismatch')
    cp=checkpoint(a.checkpoint).resolve(); out=Path(a.output); out.mkdir(parents=True,exist_ok=True)
    configure_memory(); base={**host_health(),**memory_stats()}
    def guard():
        h={**host_health(),**memory_stats()}; reason='stop_file' if stop_requested(ROOT) else violation(h,base)
        if reason: raise RuntimeError('inference_guard_'+reason)
        return h
    tok=Tokenizer.from_file(str(ROOT/'data/sft-v3/tokenizer.json')); model=Model(768,12,16384);model.load_weights(str(cp/'model.safetensors'));model.set_dtype(mx.bfloat16);mx.eval(model.parameters())
    rows=[]; started=time.time()
    for r in records:
        guard(); start=time.monotonic()
        def emit(messages): return generate(model,tok,messages,penalty=1.2,mode='greedy',seed=20261102,cap=96)
        if r['kind']=='tool':
            x=tool_trace(r,emit);x.update(id=r['id'],kind='tool',family=r['family'])
        else:
            g=emit(r['messages']);x={'id':r['id'],'kind':'prose','family':r['family'],'generation':g,'output':g['output'],'semantic_review':'required; no automated semantic pass label'}
        x['latency_seconds']=time.monotonic()-start; rows.append(x)
    tools=[x for x in rows if x['kind']=='tool']; prose=[x for x in rows if x['kind']=='prose']
    report={'kind':'eight_hour_v2_raw_student_decode','split':a.split,'evaluation_sha256':m[a.split]['sha256'],'checkpoint':str(cp.relative_to(ROOT)),'checkpoint_sha256':sha(cp/'model.safetensors'),'decoding':{'greedy':True,'seed':20261102,'cap':96,'penalty':1.2},'counts':{'conversations':len(rows),'prose':len(prose),'tools':len(tools),'tool_full_success':sum(x['success'] for x in tools),'tool_exact_calls':sum(x['calls_exact'] for x in tools),'tool_final_exact':sum(x['final_answer_exact'] for x in tools)},'semantic_scoring':'not automated; each case requires full-reply human/assistant review with cited reason','initial_health':base,'final_health':guard(),'elapsed_seconds':time.time()-started}
    (out/'raw-outputs.json').write_text(json.dumps(rows,indent=2)+'\n');(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--checkpoint',required=True);p.add_argument('--split',choices=['development','confirmation'],required=True);p.add_argument('--output',required=True);p.add_argument('--selection',default='runs/eight-hour-improvement-v1/evaluation-v2-development-selection.json');main(p.parse_args())
