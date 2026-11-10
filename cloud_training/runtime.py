"""Bounded portable training primitives; separate from frozen local campaigns."""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import signal
import time

import numpy as np
import torch
import torch.nn.functional as F


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def atomic_json(path, value):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + '.tmp')
    with tmp.open('w') as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


class Guard:
    def __init__(self, root, seconds, *, min_free=5*1024**3):
        if not 0 < seconds <= 3*3600:
            raise ValueError('worker lease must be positive and <=3 hours')
        self.root = Path(root)
        self.deadline = time.monotonic() + seconds
        self.min_free = min_free
        self.interrupted = False

    def install_signals(self):
        def stop(signum, frame):
            self.interrupted = True
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)

    def check(self):
        if self.interrupted or time.monotonic() >= self.deadline:
            raise InterruptedError('worker stopped or lease expired')
        if any((p/'STOP').exists() for p in (self.root, *self.root.parents)):
            raise InterruptedError('STOP file')
        if shutil.disk_usage(self.root).free < self.min_free:
            raise InterruptedError('insufficient checkpoint disk headroom')


def precision(device, bf16):
    return torch.autocast(device_type=torch.device(device).type, dtype=torch.bfloat16) if bf16 else contextlib.nullcontext()


def synchronize(device):
    if torch.device(device).type == 'cuda':
        torch.cuda.synchronize(device)


def optimizer(model):
    return torch.optim.AdamW([
        {'params':[p for p in model.parameters() if p.ndim >= 2], 'weight_decay':.1},
        {'params':[p for p in model.parameters() if p.ndim < 2], 'weight_decay':0.}
    ], lr=6e-5, betas=(.9,.95), eps=1e-8, foreach=False)


def restore(model, opt, payload, device, *, restore_rng=True):
    model.load_state_dict(payload['model'], strict=True)
    opt.load_state_dict(payload['optimizer'])
    # load_state_dict casts optimizer moments to the parameter device. Keep Adam's
    # scalar step on CPU for the non-capturable implementation.
    for state in opt.state.values():
        for key in ('exp_avg','exp_avg_sq'):
            state[key] = state[key].detach().to(device=device, dtype=torch.float32).clone()
        state['step'] = state['step'].detach().cpu().clone()
    if restore_rng:
        torch.set_rng_state(payload['cpu_rng'])
        if payload.get('cuda_rng') is not None and torch.device(device).type == 'cuda':
            torch.cuda.set_rng_state_all(payload['cuda_rng'])
        if 'python_rng' in payload:
            random.setstate(payload['python_rng'])
        # NumPy state encoded without NumPy pickle globals (weights_only safe).
        if 'numpy_rng' in payload:
            name, keys, pos, has_gauss, cached = payload['numpy_rng']
            np.random.set_state((name, np.array(keys,dtype=np.uint32),pos,has_gauss,cached))


def update(model, opt, rows, *, device, microbatch, lr, guard, bf16=True, labels=None):
    """One optimizer boundary; caller publishes only after successful return."""
    if microbatch <= 0 or len(rows) % microbatch:
        raise ValueError('microbatch must divide effective batch')
    targets = rows[:,1:] if labels is None else labels
    count = int((targets != -100).sum())
    if count <= 0:
        raise ValueError('empty supervised update')
    model.train()
    opt.zero_grad(set_to_none=True)
    for group in opt.param_groups:
        group['lr'] = lr
    total = 0.
    for start in range(0,len(rows),microbatch):
        guard.check()
        x = torch.as_tensor(rows[start:start+microbatch,:-1],dtype=torch.long,device=device)
        y = torch.as_tensor(targets[start:start+microbatch],dtype=torch.long,device=device)
        with precision(device,bf16):
            loss = F.cross_entropy(model(x).flatten(0,1),y.flatten(),ignore_index=-100,reduction='sum') / count
        if not torch.isfinite(loss):
            raise ValueError('nonfinite training loss')
        loss.backward()
        total += float(loss.detach())
    norm = torch.nn.utils.clip_grad_norm_(model.parameters(),1.,error_if_nonfinite=True)
    opt.step()
    synchronize(device)
    return {'ce':total, 'gradient_norm':float(norm), 'supervised_targets':count}


def save(path, model, opt, *, cursor, identity):
    """Atomic local snapshot, verified before publication; backup is a separate gate."""
    path = Path(path)
    rng = np.random.get_state()
    payload = dict(model=model.state_dict(),optimizer=opt.state_dict(),cursor=cursor,
                   identity=identity,cpu_rng=torch.get_rng_state(),
                   cuda_rng=torch.cuda.get_rng_state_all() if torch.cuda.is_available() else None,
                   python_rng=random.getstate(),numpy_rng=(rng[0],rng[1].tolist(),*rng[2:]))
    tmp = path.with_suffix('.partial')
    with tmp.open('wb') as f:
        torch.save(payload,f)
        f.flush()
        os.fsync(f.fileno())
    verified = torch.load(tmp,map_location='cpu',weights_only=True)
    if verified['cursor'] != cursor or verified['identity'] != identity:
        raise ValueError('checkpoint readback differs')
    del verified
    digest = sha(tmp)
    os.replace(tmp,path)
    receipt = {'file':path.name,'sha256':digest,'bytes':path.stat().st_size,'cursor':cursor,'identity':identity}
    atomic_json(path.with_suffix('.json'),receipt)
    return receipt
