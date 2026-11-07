"""CPU-only production-shaped source loader for the disposable MLX benchmark.

No CLI or live conversion on import. Existing ancestry verifier selects the exact
protected foundation endpoint; neutral exports map actual optimizer objects.
"""
from dataclasses import asdict
from pathlib import Path
import copy
import torch
from gpt2 import GPT2,Config
from train import optimizer_for
import own_base_neutral_state as neutral
from optimizer_ablation_train import verify_parent


def load_verified(spec):
    payload,receipt=verify_parent(spec,Config())
    if len(payload['model'])!=148:raise ValueError('full model tensor inventory')
    with torch.device('meta'):model=GPT2(Config())
    model.to_empty(device='cpu');model.load_state_dict(payload['model'],strict=True)
    opt=optimizer_for(model)
    saved=payload['optimizer'];ids=[x for group in saved['param_groups'] for x in group['params']]
    if len(ids)!=148 or len(set(ids))!=148 or set(ids)!=set(saved['state']):raise ValueError('source optimizer serialized inventory')
    # load_state_dict maps saved IDs through the actual instantiated groups.
    # The historical optimizer constructor is code-pinned by verify_parent.
    opt.load_state_dict(saved)
    for state in opt.state.values():
        for key,value in state.items():state[key]=value.detach().clone() if isinstance(value,torch.Tensor) else copy.deepcopy(value)
    source=dict(path=str(Path(receipt['run'])/receipt['checkpoint']),sha256=receipt['sha256'],bytes=receipt['bytes'])
    step=payload['step'];tokens=payload['trained_tokens'];effective=payload['identity']['protocol']['targets_per_update']
    progress=dict(campaign_step=step,optimizer_step=step,initial_optimizer_step=0,trained_tokens=tokens,reserved_tokens=tokens,targets_per_update=effective,initial_source_offset=0,source_offset=payload['offset'])
    expected=dict(expected_identity=payload['identity'],expected_source=source,expected_progress=progress,expected_optimizer=neutral.optimizer_policy(opt))
    meta,arrays=neutral.export_objects(model,opt,identity=payload['identity'],source=source,progress=progress,cpu_rng=payload['cpu_rng'],mps_rng=payload['mps_rng'],**expected)
    if sum(p.numel() for p in model.parameters())!=124439808:raise ValueError('architecture count changed')
    del payload
    return model,opt,meta,arrays,expected


def exact_torch_roundtrip(meta,arrays,pinned):
    """Exact neutral→Torch→neutral check, including source double LR and RNG.

    This does NOT assert native MLX float32 LR is byte-identical to Torch scalar.
    """
    with torch.device('meta'):model=GPT2(Config(**meta['identity']['model']))
    model.to_empty(device='cpu');optimizer=optimizer_for(model)
    rng=neutral.import_objects(model,optimizer,meta,arrays,**pinned)
    other_meta,other=neutral.export_objects(model,optimizer,identity=meta['identity'],source=meta['source'],progress=meta['progress'],cpu_rng=rng['cpu_rng'],mps_rng=rng['mps_rng'],**pinned)
    if meta!=other_meta:raise ValueError('neutral exact metadata roundtrip')
    import numpy as np
    for name in arrays:
        if arrays[name].dtype!=other[name].dtype or arrays[name].shape!=other[name].shape or arrays[name].tobytes()!=other[name].tobytes():raise ValueError('neutral exact array roundtrip: '+name)
    lr=meta['optimizer'][0]['learning_rate'];native=float(np.float32(lr))
    return dict(exact_torch_roundtrip=True,tensors=len(meta['parameter_order']),arrays=len(arrays),source_scalar_learning_rate=lr,native_float32_learning_rate=native,native_lr_absolute_difference=abs(lr-native),native_lr_byte_exact=False if lr!=native else True,rng_policy='opaque preserved bytes; no equivalent MLX random stream claimed')
