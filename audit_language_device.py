"""Bounded full124M B2/T512 CPU versus MPS gradient audit, no optimizer step."""
import argparse
import fcntl
import json
from pathlib import Path
import shutil
import sys
import time

import own_base_dev_run as rt
from own_base_language_milestone import sha,require_ac_power

ROOT=Path(__file__).resolve().parent
RUN=ROOT/'runs/own-base-fresh-broad-language-100m-01'
OUT=ROOT/'runs/post-25m-device-audit-v1'
REQUEST=RUN/'milestone-24993792-request.json'
REQUEST_SHA='cc02a3b005bcbd02036f9fdc173ae63649d7a0c6f23cb1f2dc9fb063e7c6e87b'


def launch():
    assert not OUT.exists() and sha(REQUEST)==REQUEST_SHA
    OUT.mkdir();ticket=rt.make_ticket(300,sha(Path(__file__)));ticket['heartbeat']=str(OUT/'heartbeat')
    rt.atomic(OUT/'reservation.json',dict(max_forward_backward_passes=3,max_targets=3072,seconds=300,
              model_parameters=124439808,layout=dict(batch=2,length=512),optimizer_steps=0,
              request_sha256=REQUEST_SHA,code_sha256=sha(Path(__file__)),automatic_retries=False))
    result=rt.supervise(lambda fd:[sys.executable,str(Path(__file__).resolve()),'--worker','--ticket-fd',str(fd)],
                        OUT,ticket=ticket,heartbeat_seconds=90,grace_seconds=10,max_rss_bytes=18*1024**3)
    rt.atomic(OUT/'watchdog.json',result);print(json.dumps(result))


def worker(fd):
    import torch
    import numpy as np
    from torch.nn import functional as F
    from gpt2 import GPT2
    from base_train import precision
    from guards import thermal,swap_mib
    ticket=rt.consume_ticket(fd);assert ticket['spec_sha256']==sha(Path(__file__))
    lock=(ROOT/'runs/mps.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    initial_swap=swap_mib();last=0.;torch.set_num_threads(1)
    stops=json.loads((ROOT/'reports/fresh-broad-language-100m-v1/activation.json').read_text())['stop_paths']+[str(OUT/'STOP')]
    def check():
        nonlocal last
        assert rt.remaining(ticket)>10 and not any(Path(p).exists() for p in stops)
        assert shutil.disk_usage(ROOT).free>20*1024**3
        Path(ticket['heartbeat']).write_text(str(time.time()))
        if time.monotonic()-last>5:
            require_ac_power();assert thermal()<=1 and swap_mib()-initial_swap<=1024;last=time.monotonic()
    try:
        check();assert sha(REQUEST)==REQUEST_SHA
        entry=json.loads(REQUEST.read_text())['checkpoint'];path=RUN/entry['file']
        assert path.stat().st_size==entry['bytes'] and sha(path)==entry['sha256']
        payload=torch.load(path,map_location='cpu',weights_only=True,mmap=True)
        assert payload['trained_tokens']==24993792
        model=GPT2().float();model.load_state_dict(payload['model'],strict=True);del payload
        data=ROOT/'data/fresh-broad-packed-v1';manifest=json.loads((data/'manifest.json').read_text())
        source=data/'train.u16';assert sha(source)==manifest['shards']['train']['sha256']
        raw=np.memmap(source,dtype='<u2',mode='r')[:1026].astype(np.int64).reshape(2,513)
        sequence=torch.from_numpy(raw);references={};results=[]
        for label,device,bf16 in [('cpu_fp32','cpu',False),('mps_fp32','mps',False),('mps_bf16','mps',True)]:
            check();model=model.to(device);model.train();model.zero_grad(set_to_none=True);batch=sequence.to(device)
            with precision(bf16):
                logits=model(batch[:,:-1]);loss=F.cross_entropy(logits.flatten(0,1),batch[:,1:].flatten(),reduction='sum')/1024
            last_logits=logits[:,-1].detach().float().cpu();del logits
            check();loss.backward()
            if device=='mps':torch.mps.synchronize()
            check();ce=float(loss.detach().cpu());assert torch.isfinite(loss)
            if label=='cpu_fp32':
                references={name:p.grad.detach().cpu().clone() for name,p in model.named_parameters()}
                cpu_ce=ce;cpu_logits=last_logits;results.append(dict(mode=label,ce=ce))
            else:
                dot=base_sq=other_sq=diff_sq=0.
                for name,p in model.named_parameters():
                    a=references[name];b=p.grad.detach().float().cpu();assert torch.isfinite(b).all()
                    dot+=float((a*b).sum());base_sq+=float(a.square().sum());other_sq+=float(b.square().sum());diff_sq+=float((a-b).square().sum())
                cosine=dot/(base_sq*other_sq)**.5;relative=(diff_sq/base_sq)**.5
                row=dict(mode=label,ce=ce,ce_abs_difference=abs(ce-cpu_ce),gradient_cosine=cosine,
                         gradient_relative_l2=relative,last_logits_max_abs_difference=float((last_logits-cpu_logits).abs().max()))
                row['within_prespecified_tolerance']=abs(ce-cpu_ce)<(.02 if bf16 else .001) and cosine>(.98 if bf16 else .999) and relative<(.2 if bf16 else .01)
                results.append(row)
            rt.atomic(OUT/'partial.json',dict(results=results,optimizer_steps=0));del loss
        check();assert sha(path)==entry['sha256']
        result=dict(state='completed_device_numerics_audit_not_quality',checkpoint=entry,results=results,
                    passed=all(x.get('within_prespecified_tolerance',True) for x in results),
                    source_sha256=manifest['shards']['train']['sha256'],forward_backward_passes=3,targets=3072,
                    optimizer_steps=0,weights_written=False,
                    limitations='One full-size B2/T512 training batch; no optimizer trajectory equivalence or behavioral success established.')
        rt.atomic(OUT/'result.json',result)
    finally:lock.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--worker',action='store_true');p.add_argument('--ticket-fd',type=int);a=p.parse_args()
    if a.worker:worker(a.ticket_fd)
    else:launch()
