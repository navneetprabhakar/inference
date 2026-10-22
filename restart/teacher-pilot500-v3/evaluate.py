"""One sealed final test evaluation of the development-selected checkpoint."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'student-run-recovery-v1'
PROJECT=ROOT.parents[1]

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')

def launch():
    from slm.restart.supervisor import TimeBudget,supervise
    result=json.loads((OUT/'result.json').read_text())
    if result['status']!='BOUNDED_TRAINING_COMPLETE_NOT_CAPABILITY_CERTIFICATION':raise ValueError('Training not completed cleanly')
    metadata=json.loads((OUT/'best.json').read_text())
    if sha(OUT/'best.safetensors')!=metadata['weights_sha256']:raise ValueError('Best checkpoint changed')
    marker=OUT/'final-test-started.json'
    ticket=dict(checkpoint_sha256=sha(OUT/'best.safetensors'),config_sha256=sha(OUT/'config.json'),
        test_sha256=sha(ROOT/'test-candidates.jsonl'),decode=dict(method='greedy',max_new_tokens=64),
        criterion='At least 40/50 conversations must have two grammatical, relevant and factually/constraint-correct responses; no final-test tuning.',
        parent_pid=os.getpid())
    with marker.open('x') as f:json.dump(ticket,f)
    parent=json.loads((OUT/'ticket.json').read_text())
    clock=TimeBudget(OUT/'time.sqlite',identity=parent['identity'],seconds_cap=parent['seconds_cap'],deadline_utc=parent['deadline'])
    try:
        done=supervise([sys.executable,str(Path(__file__).resolve()),'worker'],cwd=OUT,
           env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),heartbeat=OUT/'final-heartbeat.json',budget=clock,
           receipt=OUT/'final-supervisor.json',tick=5)
    finally:clock.db.close()
    print(json.dumps(done),flush=True)

def worker():
    ticket=json.loads((OUT/'final-test-started.json').read_text())
    if (ticket['parent_pid']!=os.getppid() or sha(OUT/'best.safetensors')!=ticket['checkpoint_sha256']
            or sha(ROOT/'test-candidates.jsonl')!=ticket['test_sha256']
            or sha(OUT/'config.json')!=ticket['config_sha256']):raise ValueError('Changed final binding')
    import mlx.core as mx
    from safetensors.numpy import load_file
    from slm.backends import mlx_backend as backend
    from slm.common.config import Config
    from slm.common.tokenizer import BPE
    mx.set_memory_limit(2147483648);mx.set_cache_limit(134217728)
    spec=importlib.util.spec_from_file_location('bounded_decode',ROOT/'train_recovery.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    c=Config(**json.loads((OUT/'config.json').read_text()));bpe=BPE.load(OUT/'tokenizer')
    if c.parameter_count!=5114112:raise ValueError('Unowned final architecture')
    params=backend.load(c,load_file(str(OUT/'best.safetensors')))
    rows=[json.loads(l) for l in (ROOT/'test-candidates.jsonl').read_text().splitlines()];results=[]
    for r in rows:
        history=[];replies=[]
        for u in r['users']:
            save(OUT/'final-heartbeat.json',dict(pid=os.getpid(),monotonic=time.monotonic()))
            history.append(dict(role='user',content=u));reply=module.generate(params,c,bpe,history)
            history.append(dict(role='assistant',content=reply));replies.append(reply);mx.clear_cache()
            if mx.get_peak_memory()>2147483648:raise RuntimeError('Final GPU peak cap')
        results.append(dict(id=r['id'],family=r['family'],users=r['users'],replies=replies,
                            references=[m['content'] for m in r['messages'] if m['role']=='assistant']))
    save(OUT/'final-test-responses.json',dict(checkpoint_sha256=ticket['checkpoint_sha256'],cases=results,
         model_parameters=c.parameter_count,semantic_grade_pending=True,mlx_peak_bytes=mx.get_peak_memory()))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['launch','worker']);a=p.parse_args()
    launch() if a.action=='launch' else worker()
