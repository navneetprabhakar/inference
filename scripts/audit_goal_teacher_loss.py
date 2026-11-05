"""Teacher-forced training-data diagnostic, never a conversation-accuracy metric."""
import hashlib,json,time,gc
from pathlib import Path
import numpy as np
import mlx.core as mx
from tokenizers import Tokenizer
from benchmark_mlx import Model
from sft_common import ROOT,configure_memory,memory_stats,encode_episode,masked_loss
from train_local import health
from inference_guard import violation

def main():
    goal=ROOT/'runs/eight-hour-improvement-v1';deadline=json.loads((goal/'authorization.json').read_text())['deadline_unix'];configure_memory();initial={**health(),**memory_stats()}
    def guard():
        if time.time()>=deadline or (goal/'STOP').exists():raise RuntimeError('deadline or STOP')
        reason=violation({**health(),**memory_stats()},initial)
        if reason:raise RuntimeError(reason)
    tok=Tokenizer.from_file(str(ROOT/'data/sft-v3/tokenizer.json'))
    fresh=[]
    for p in sorted((ROOT/'data/eight-hour-improvement-v5-authored').glob('batch-*.jsonl')):fresh += [json.loads(x) for x in p.read_text().splitlines()]
    prior=[json.loads(x) for x in (ROOT/'data/eight-hour-improvement-v3-reviewed/records.jsonl').read_text().splitlines() if x][:len(fresh)]
    latest=json.loads((ROOT/'runs/eight-hour-improvement-v3/training/latest.json').read_text())['directory']
    checkpoints={'baseline':ROOT/'runs/sft-v3/repair-lr3/milestones/2000000','v3':ROOT/'runs/eight-hour-improvement-v3/training'/latest}
    results={}
    for label,cp in checkpoints.items():
        guard();model=Model(768,12,16384);model.load_weights(str(cp/'model.safetensors'));model.set_dtype(mx.bfloat16);mx.eval(model.parameters());groups={}
        for name,rows in [('new_authored',fresh),('previously_used_keeps',prior)]:
            summed=0.;targets=0;used=0
            for row in rows:
                guard();encoded=encode_episode(tok,row['messages'])
                if encoded is None:raise RuntimeError('unencodable diagnostic row')
                ids,mask,n=encoded;tokens=mx.array(ids[None,:n]);weights=mx.array(mask[None,:n-1]);loss=masked_loss(model,tokens,weights);mx.eval(loss);nt=int(mask[:n-1].sum());summed+=float(loss)*nt;targets+=nt;used+=1
            groups[name]={'records':used,'supervised_tokens':targets,'mean_nll':summed/targets,'data_sha256':hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()}
        results[label]={'checkpoint_sha256':hashlib.sha256((cp/'model.safetensors').read_bytes()).hexdigest(),'groups':groups};del model;gc.collect();mx.clear_cache()
    report={'kind':'teacher_forced_training_data_diagnostic','results':results,'limitation':'Different example content and prior exposure; descriptive loss contrast, not controlled causal proof or held-out conversation accuracy.','final_health':{**health(),**memory_stats()}}
    out=goal/'parent-teacher-loss-diagnostic.json';out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
