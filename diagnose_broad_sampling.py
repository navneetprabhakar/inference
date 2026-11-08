"""One bounded decoding diagnostic on the completed own-base endpoint; no training."""
import argparse
from dataclasses import asdict
import fcntl
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

import own_base_dev_run as rt
from own_base_language_milestone import sha, canon, unsigned, require_ac_power

ROOT=Path(__file__).resolve().parent
RUN=ROOT/'runs/own-base-broad-language-20m-01'
OUT=ROOT/'runs/broad-sampling-diagnostic-v1'
REQUEST=RUN/'milestone-19996672-request.json'
REQUEST_SHA='625fb916089129a1a6abc4465063cbcf012d42bd97612c0a7e978d518cb2cfd6'
SECONDS=300


def launch():
    assert not OUT.exists() and sha(REQUEST)==REQUEST_SHA
    OUT.mkdir()
    ticket=rt.make_ticket(SECONDS,sha(Path(__file__)));ticket['heartbeat']=str(OUT/'heartbeat')
    # All potential forwards charged before spawn, including early EOT or failures.
    rt.atomic(OUT/'reservation.json',dict(checkpoint_request_sha256=REQUEST_SHA,
              code_sha256=sha(Path(__file__)),max_forwards=32*48*2,seconds=SECONDS,
              temperatures=[0.8,1.0],top_p=0.9,seed=20261109,
              acceptance=False,automatic_retries=False))
    result=rt.supervise(lambda fd:[sys.executable,str(Path(__file__).resolve()),'--worker','--ticket-fd',str(fd)],
         OUT,ticket=ticket,heartbeat_seconds=90,grace_seconds=10,max_rss_bytes=18*1024**3)
    rt.atomic(OUT/'watchdog.json',result);print(json.dumps(result))


def worker(fd):
    import torch
    from gpt2 import GPT2,Config
    from tokenizer import load
    from guards import thermal,swap_mib
    from optimizer_ablation_train import parent_lock
    ticket=rt.consume_ticket(fd);assert ticket['spec_sha256']==sha(Path(__file__))
    lock=(ROOT/'runs/mps.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    torch.set_num_threads(1);initial_swap=swap_mib();last=0;attempted=0;rows=[]
    stops=json.loads((ROOT/'reports/broad-language-20m-v1/activation.json').read_text())['stop_paths']
    def check():
        nonlocal last
        assert rt.remaining(ticket)>10 and not any(Path(p).exists() for p in stops)
        assert shutil.disk_usage(ROOT).free>20*1024**3
        Path(ticket['heartbeat']).write_text(str(time.time()))
        if time.monotonic()-last>5:
            require_ac_power();assert thermal()<=1 and swap_mib()-initial_swap<=1024;last=time.monotonic()
    try:
        check();assert sha(REQUEST)==REQUEST_SHA
        req=json.loads(REQUEST.read_text());e=req['checkpoint'];file=RUN/e['file']
        with parent_lock(RUN):
            ledger=unsigned(RUN/'campaign.json');spec=json.loads((RUN/'campaign-spec.json').read_text())
            assert ledger['state']=='completed' and ledger['spec']==spec and ledger['trained_tokens']==19996672
            assert e in ledger['checkpoints'] and file.stat().st_size==e['bytes'] and sha(file)==e['sha256']
            x=torch.load(file,map_location='cpu',weights_only=True,mmap=True)
            assert x['identity']==spec['identity'] and x['campaign_id']==ledger['campaign_id']
            assert x['spec_sha256']==hashlib.sha256(canon(spec)).hexdigest()
            assert x['identity']['model']==asdict(Config()) and x['identity']['initialization']['mode']=='own_pretraining'
            model=GPT2(Config());model.load_state_dict(x['model'],strict=True);del x
        model=model.to('mps').float().eval();tok=load()
        foundation=json.loads((ROOT/'reports/base-foundation-100m/budget.json').read_text())
        p=Path(foundation['diagnostics']);assert sha(p)==foundation['diagnostics_sha256']
        prefixes=json.loads(p.read_text())['prefixes'];assert len(prefixes)==32
        with torch.inference_mode():
            for temperature in (0.8,1.0):
                for i,prefix in enumerate(prefixes):
                    prefix=prefix['text'] if isinstance(prefix,dict) else prefix
                    ids=tok.encode(prefix).ids;assert 0<len(ids) and len(ids)+48<=512
                    generated=[];rng=torch.Generator(device='cpu').manual_seed(20261109+i)
                    for step in range(48):
                        check();attempted+=1;assert attempted<=3072
                        logits=model(torch.tensor([ids+generated],device='mps'))[0,-1].float().cpu()
                        assert torch.isfinite(logits).all()
                        probs=torch.softmax(logits/temperature,dim=-1)
                        probs,indices=torch.sort(probs,descending=True)
                        # Keep the first token crossing cumulative mass .9.
                        probs[(torch.cumsum(probs,0)-probs)>=0.9]=0
                        token=int(indices[torch.multinomial(probs,1,generator=rng)])
                        if token==50256:break
                        generated.append(token)
                    row=dict(prompt_index=i,prefix=prefix,temperature=temperature,seed=20261109+i,
                             top_p=0.9,generated=tok.decode(generated),tokens=generated)
                    rows.append(row);rt.atomic(OUT/'partial.json',dict(attempted=attempted,rows=rows))
        torch.mps.synchronize();check();assert sha(file)==e['sha256']
        rt.atomic(OUT/'result.json',dict(state='completed_sampling_diagnostic_not_acceptance',
                  checkpoint=e,rows=rows,attempted_forwards=attempted,reserved_forwards=3072,usable_claim=False))
    finally:lock.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--worker',action='store_true');p.add_argument('--ticket-fd',type=int);a=p.parse_args()
    if a.worker:worker(a.ticket_fd)
    else:launch()
