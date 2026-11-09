"""Explicit frozen own-language checkpoint handoff; no fallback or mutation."""
import hashlib
import json
from pathlib import Path

import torch
from own_base_language_data import require, digest, ContinuedSchedule
from own_base_language_streams import pinned,sha
from optimizer_ablation_train import parent_lock

ROOT=Path(__file__).resolve().parent


def verify_payload(payload, campaign, ledger, entry):
    require(payload['identity']==campaign['identity'] and ledger['spec']==campaign,'language parent identity differs')
    require(payload['campaign_id']==ledger['campaign_id'] and payload['spec_sha256']==digest(campaign),'language parent campaign differs')
    require(payload['step']==ledger['step'] and payload['trained_tokens']==ledger['trained_tokens']==payload['step']*8192,'language parent accepted counters differ')
    require(entry in ledger['checkpoints'],'language parent checkpoint not committed')
    origin=payload['identity']['initialization']
    require(origin.get('mode')=='own_pretraining' and bool(origin.get('random_lineage_root')),'own random lineage required')
    expected=payload['initial_optimizer_step']+payload['step']
    states=payload['optimizer']['state']
    require(bool(states),'full parent optimizer required')
    for state in states.values():
        require(set(state)=={'step','exp_avg','exp_avg_sq'} and float(state['step'])==expected,'parent optimizer step/state mismatch')
        for key in ['exp_avg','exp_avg_sq']:
            value=state[key];require(value.dtype==torch.float32 and bool(torch.isfinite(value).all()),'invalid parent moments')
        require(bool((state['exp_avg_sq']>=0).all()),'negative parent second moment')
    for name in ['cpu_rng','mps_rng']:
        value=payload[name];require(isinstance(value,torch.Tensor) and value.dtype==torch.uint8 and value.numel()>0,'complete parent RNG required')


def verified_language_parent(spec, data, check):
    receipt=pinned(spec['language_parent'])
    require(receipt['state']=='reviewed_language_checkpoint_handoff' and receipt['capability_promoted'] is False,'reviewed handoff required')
    run=Path(receipt['run']);require(run==run.resolve() and run.parent==ROOT/'runs' and run!=Path(spec['run']),'canonical distinct parent run')
    for key,name in [('campaign_spec','campaign-spec.json'),('ledger','campaign.json')]:
        require(receipt[key]['path']==str(run/name),'parent receipt path differs')
    require(str(run/'STOP') in spec['stop_paths'],'parent STOP must be inherited')
    for item in receipt['audit_receipts']:check();pinned(item)
    with parent_lock(run):
        check();campaign=pinned(receipt['campaign_spec']);ledger=pinned(receipt['ledger'])
        unsigned=dict(ledger);signature=unsigned.pop('sha256');require(digest(unsigned)==signature,'parent ledger checksum')
        require(ledger['state'] in ('paused-milestone','completed'),'quiescent accepted language parent required')
        request=pinned(receipt['request']);decision=pinned(receipt['decision'])
        require(request['checkpoint']==receipt['checkpoint'] and request['trained_tokens']==ledger['trained_tokens'],'parent milestone checkpoint differs')
        require(decision['request_sha256']==receipt['request']['sha256'] and decision['protocol_sha256']==request['protocol']['sha256'],'parent reviewed milestone binding')
        require(decision['state']=='root_reviewed_external_milestone','parent review missing')
        for pin in decision['result_receipts']:pinned(pin)
        entry=receipt['checkpoint'];path=run/entry['file']
        require(path.parent==run and not path.is_symlink() and path.stat().st_size==entry['bytes'] and sha(path)==entry['sha256'],'parent checkpoint bytes differ')
        payload=torch.load(path,map_location='cpu',weights_only=True,mmap=True);verify_payload(payload,campaign,ledger,entry)
    old=payload['identity']['protocol']
    for key in ['sources','seed','length','row_source_cycle','tokenizer','model']:
        require(spec[key]==old[key],'continued source/model contract changed: '+key)
    require(isinstance(data.schedule,ContinuedSchedule) and data.schedule.start_updates==payload['step'],'inherited source offset differs')
    require(payload['cursor']==data.schedule.base.state_at(payload['step']),'parent data cursor not reproduced')
    require(spec['initialization']==dict(mode='own_pretraining',path=str(path),sha256=entry['sha256'],random_lineage_root=payload['identity']['initialization']['random_lineage_root']),'new initialization lineage differs')
    check();return payload
