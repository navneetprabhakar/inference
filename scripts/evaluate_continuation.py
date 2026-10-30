"""Frozen old/new held-out diagnostics and actual outputs at each milestone."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
import mlx.core as mx
from tokenizers import Tokenizer
from benchmark_mlx import Model
from evaluate_pilot import PROMPTS,score,generate
ROOT=Path(__file__).resolve().parents[1]
def sets():
    data=ROOT/'data/continuation-v1';path=data/'evaluation-sets.npz'
    if path.exists():
        metadata=json.loads((data/'evaluation-sets.json').read_text());assert hashlib.sha256(path.read_bytes()).hexdigest()==metadata['sha256'];return dict(np.load(path))
    # Reuse exactly the old evaluation arrays; never rebuild them using future data.
    old=dict(np.load(ROOT/'runs/evaluation-v1/loss_sets.npz'));out={'legacy_'+k:v for k,v in old.items()};rng=np.random.default_rng(3002026);indices={}
    for s in ['fineweb','wikipedia','pressbooks']:
        a=np.memmap(data/f'{s}-validation.bin',dtype=np.uint16,mode='r');ix=rng.choice(np.arange(32,(len(a)-1)//512),128,replace=False);indices[s]=ix.tolist();out['new_'+s]=np.stack([np.asarray(a[i*512:i*512+513],dtype=np.int32) for i in ix])
    np.savez(path,**out);(data/'evaluation-sets.json').write_text(json.dumps({'new_validation_block_indices':indices,'seed':3002026,'monitor_prefix_excluded':True,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()},indent=2)+'\n');return out

def main(a):
    assert json.loads((a.checkpoint/'state.json').read_text())['tokens']==a.total_tokens
    out=a.output;out.mkdir(parents=True,exist_ok=True);arrays=sets();tok=Tokenizer.from_file(str(ROOT/'data/continuation-v1/tokenizer.json'))
    m=Model(768,12,16384);m.load_weights(str(a.checkpoint/'model.safetensors'));m.set_dtype(mx.bfloat16);mx.eval(m.parameters())
    report={'total_tokens':a.total_tokens,'checkpoint':str(a.checkpoint),'model_sha256':hashlib.sha256((a.checkpoint/'model.safetensors').read_bytes()).hexdigest(),'scores':{},'cloud_spend_usd':0,'note':'Same frozen sets and prompts across 100M/200M/300M. Legacy Wikipedia is now a held-out subset of a trained source, not an unseen domain. Loss and tiny prompt suite are diagnostic, not general capability benchmarks.'}
    for name,arr in arrays.items():report['scores'][name]=score(m,arr);print(name,report['scores'][name],flush=True)
    (out/'loss-results.json').write_text(json.dumps(report,indent=2)+'\n');samples=[]
    for i,(category,prompt) in enumerate(PROMPTS):
        for mode in ['greedy','sampled']:
            samples.append({'category':category,'prompt':prompt,'decoding':mode,'seed':100+i,**generate(m,tok,prompt,mode,100+i)})
            (out/'generations.json').write_text(json.dumps(samples,indent=2)+'\n')
    # Original master weights are also checked to expose precision-sensitive outputs.
    m=Model(768,12,16384);m.load_weights(str(a.checkpoint/'model.safetensors'));mx.eval(m.parameters());fp=[]
    for i,(category,prompt) in enumerate(PROMPTS):fp.append({'category':category,'prompt':prompt,'decoding':'greedy_fp32',**generate(m,tok,prompt,'greedy',100+i)})
    (out/'fp32-generations.json').write_text(json.dumps(fp,indent=2)+'\n')
    baseline=ROOT/'reports/continuation-v1/100m/loss-results.json';old=json.loads(baseline.read_text())['scores'] if baseline.exists() else report['scores']
    lines=[f'# {a.total_tokens//1000000}M-token evaluation','',report['note'],'','| Set | 100M perplexity | Current perplexity |','|---|---:|---:|']
    for name,v in report['scores'].items():lines.append(f"| {name} | {old[name]['perplexity']:.2f} | {v['perplexity']:.2f} |")
    lines+=['','## Actual outputs, unedited','','Every fixed prompt appears below. No best-of selection. BF16 sampled mode uses temperature 0.8/top-k 40; all generations capped at 96 tokens.']
    for r in samples+fp:lines += ['',f"### {r['category']} — {r['decoding']}",'','Prompt:','```text',r['prompt'],'```','','Output:','```text',r['output'],'```']
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n');(out/'completed.json').write_text(json.dumps({'total_tokens':a.total_tokens,'generations':len(samples)+len(fp),'loss_sets':len(arrays),'complete':True},indent=2)+'\n')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--checkpoint',type=Path,required=True);p.add_argument('--total-tokens',type=int,required=True);p.add_argument('--output',type=Path,required=True);main(p.parse_args())
