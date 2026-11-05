"""Frozen-decoding comparator. Confirmation requires a prior frozen development decision."""
import argparse, hashlib, json, time
from pathlib import Path
import mlx.core as mx
from tokenizers import Tokenizer
from benchmark_mlx import Model
from sft_common import ROOT, configure_memory
from run_author_dev_decode import run_case, summary, sha

DECODING={'mode':'greedy','seed':20261101,'cap':96,'tool_penalty':1.2,'prose_penalty':1.2,'max_turns':6}
def load(path):
    m=Model(768,12,16384);m.load_weights(str(path/'model.safetensors'));m.set_dtype(mx.bfloat16);mx.eval(m.parameters());return m
def checkpoint(path):
    """Accept a checkpoint directory or a run directory with immutable latest.json."""
    path=Path(path)
    if (path/'model.safetensors').exists(): return path
    latest=path/'latest.json'
    if latest.exists(): return path/json.loads(latest.read_text())['directory']
    raise RuntimeError('missing checkpoint or latest.json: '+str(path))
def decode(model,tok,records): return [run_case(model,tok,r,DECODING['prose_penalty']) for r in records]
def main(a):
    out=Path(a.output);out.mkdir(parents=True,exist_ok=True);split=a.split
    if split=='confirmation':
        decision=Path(a.selection)
        if not decision.exists():raise RuntimeError('confirmation prohibited until a frozen development selection exists')
        if json.loads(decision.read_text()).get('split')!='development':raise RuntimeError('invalid selection freeze')
    cases=ROOT/f'data/author-review-v3/{split}-cases.jsonl';records=[json.loads(x) for x in cases.read_text().splitlines() if x]
    tok=Tokenizer.from_file(str(ROOT/'data/sft-v3/tokenizer.json')); models={'baseline':checkpoint(a.baseline),'experiment':checkpoint(a.experiment)}; result={'kind':'frozen_baseline_vs_experiment','split':split,'decoding':DECODING,'case_sha256':sha(cases),'models':{},'semantic_scoring':'manual review required; strict automated score is reported separately and is not semantic correctness','started_unix':time.time()}
    for name,path in models.items():
        h=sha(path/'model.safetensors'); rows=decode(load(path),tok,records);(out/f'{split}-{name}-outputs.json').write_text(json.dumps(rows,indent=2)+'\n');result['models'][name]={'checkpoint':str(path),'sha256':h,'strict':summary(rows),'outputs':str((out/f'{split}-{name}-outputs.json'))}
    result['ended_unix']=time.time();(out/f'{split}-report.json').write_text(json.dumps(result,indent=2)+'\n')
    if split=='development':
        b=result['models']['baseline']['strict'];e=result['models']['experiment']['strict']; promote=e['tools']['full_success']>=b['tools']['full_success'] and e['tools']['exact_call_trace']>=b['tools']['exact_call_trace'] and e['prose']['diagnostic_rubric_passes']>=b['prose']['diagnostic_rubric_passes']
        frozen={'split':'development','baseline_sha256':result['models']['baseline']['sha256'],'experiment_sha256':result['models']['experiment']['sha256'],'automatic_gate':promote,'selection':'provisional_only_pending_manual_semantic_review','confirmation_not_opened':True,'created_unix':time.time()};(out/'development-selection.json').write_text(json.dumps(frozen,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--baseline',required=True);p.add_argument('--experiment',required=True);p.add_argument('--split',choices=['development','confirmation'],required=True);p.add_argument('--output',required=True);p.add_argument('--selection',default='runs/approved-next-three-v1/evaluation/development-selection.json');main(p.parse_args())
