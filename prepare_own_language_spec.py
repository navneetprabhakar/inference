"""Metadata-only continuation preparation. No model, checkpoint tensor or token reads.

Writes a non-runnable draft. Root must review budgets and all pins before changing
state. The trainer re-verifies full sources and checkpoint ancestry at execution.
"""
import argparse
import json
import math
import sys
from pathlib import Path
from own_base_language_data import MixedSchedule, validation_manifest, require
from own_base_language_streams import pinned, sha, verify_custody
ROOT=Path(__file__).resolve().parent
GOAL=299999232
UPDATES=36621
MILESTONES=[0,99999744,199999488,299999232]
PROTOCOL_SHA='d7e84b1f817e8d3c52a7b443e9110338a5d1ea5fe1c084d74dc8015f1cd3545e'


def pin(path):
    path=Path(path).resolve(strict=True)
    return dict(path=str(path),sha256=sha(path))


def finite_passes(tokens,required):
    require(type(tokens)is int and tokens>512,'insufficient shifted source capacity')
    capacity=((tokens-1)//512)*512
    passes=(required+capacity-1)//capacity
    require(1<=passes<=4,f'four-pass source ceiling: need {required} targets, available {4*capacity}; shortfall {max(0,required-4*capacity)}')
    return passes,capacity


def source_metadata(directory,name,required):
    directory=Path(directory)
    descriptor=dict(name=name,manifest=pin(directory/'language-manifest.json'),verification=pin(directory/'language-manifest-verification.json'),admission=pin(directory/'language-admission.json'))
    m=pinned(descriptor['manifest']);v=pinned(descriptor['verification']);a=pinned(descriptor['admission'])
    require(m['schema']==1 and m['name']==name and m['state']=='packed_pending_training_admission','source manifest identity')
    require(v['state']=='PASS_canonical_manifest_projection' and v['failures']==[] and v['manifest_sha256']==descriptor['manifest']['sha256'],'actual independent source verification')
    require(v['excluded_ids_absent'] is True and v['full_document_tokens_verified'] is True,'full packing verification')
    underlying=pinned(v['underlying_packing_proof']);pinned(v['underlying_packing_manifest'])
    field={'PASS_independent_narrative_packing_not_admitted':'manifest_sha256','PASS_separate_full_replay_not_admitted':'dataset_sha256'}.get(underlying['state'])
    require(field and underlying['failures']==[] and underlying[field]==v['underlying_packing_manifest']['sha256'],'underlying packing proof binding')
    require(a['training_admitted'] is True and a['manifest_sha256']==descriptor['manifest']['sha256'] and a['verification_sha256']==descriptor['verification']['sha256'],'actual root admission required')
    require(a['custody_receipts']==m['custody_receipts'] and a['quality_policy']==m['quality_policy'],'admission custody/quality pins')
    excluded=verify_custody(m['custody_receipts'],m['candidate_sha256']);pinned(m['quality_policy'])
    require(all(d['original_id'] not in excluded for d in m['documents']),'excluded source document')
    docs=[{k:d[k] for k in ('id','tokens','family','split','sha256')} for d in m['documents'] if d['split']=='train']
    passes,capacity=finite_passes(sum(d['tokens'] for d in docs),required);descriptor['passes']=passes
    selection_pin=pin(directory/'language-validation-selection.json');selected=pinned(selection_pin)
    held=[dict(d,source=name) for d in m['documents'] if d['split']=='validation']
    require(selected['manifest']==validation_manifest(held,selected['windows'],512),'source validation identity')
    return descriptor,m,docs,held,selected['windows'],selection_pin


def prepare(narrative,explanatory,output):
    # Importing these modules instantiates no model/device. Never verified_parent().
    import numpy as np
    import torch
    import own_base_language_continue as trainer
    from tokenizer import ASSETS
    old=json.loads((ROOT/'reports/own-base-sft-diagnostic-v1/activation.json').read_text())
    report=pinned(old['optimizer_report']);pinned(old['optimizer_experiment'])
    require(report['state']=='screen-completed' and report['selected_optimizer_recipe']=='preserve-095','selected own optimizer parent')
    parent=report['receipts']['preserve-095'];require(parent==old['parent'],'selected endpoint changed')
    ledger_pin=pin(Path(parent['run'])/'campaign.json');require(ledger_pin['sha256']==parent['ledger_sha256'],'parent ledger changed')
    ledger=pinned(ledger_pin);origin=ledger['spec']['identity']['initialization']
    require(ledger['state']=='completed' and origin['mode']=='own_pretraining','completed own parent required')
    protocol_pin=pin(ROOT/'reports/language-milestone-v1/activation.json');require(protocol_pin['sha256']==PROTOCOL_SHA,'root-reviewed external protocol changed')
    protocol=pinned(protocol_pin);require(protocol['planned_events']==4,'exact four actual external events')
    descriptors=[];sources=[];held=[];windows=[];selection_pins=[];manifests=[]
    for directory,name,rows in [(explanatory,'explanatory',12),(narrative,'narrative',4)]:
        d,m,docs,h,w,p=source_metadata(directory,name,UPDATES*rows*512)
        require(m['tokenizer']==dict(vocabulary=50257,eot=50256,identity=ASSETS),'tokenizer binding')
        descriptors.append(d);sources.append(dict(name=name,passes=d['passes'],documents=docs));held+=h;windows+=w;selection_pins.append(p);manifests.append(m)
    train_families={d['family'] for m in manifests for d in m['documents'] if d['split']=='train'}
    train_hashes={d['text_sha256'] for m in manifests for d in m['documents'] if d['split']=='train'}
    require(not train_families&{d['family']for d in held} and not train_hashes&{d['text_sha256']for d in held},'cross-source heldout overlap')
    cycle=['explanatory']*12+['narrative']*4
    schedule=MixedSchedule(dict(schema=1,seed=20261106,length=512,sources=sources,row_source_cycle=cycle))
    exposure=schedule.state_at(UPDATES);validation=validation_manifest(held,windows,512)
    output=Path(output).resolve();require(not output.exists(),'never overwrite prepared spec');output.mkdir(parents=True)
    selection=output/'validation-selection.json';selection.write_text(json.dumps(dict(windows=windows,manifest=validation,source_selections=selection_pins),indent=2)+'\n')
    run=ROOT/'runs/own-base-language-300m-01'
    spec=dict(schema=1,state='prepared_pending_root_review',run=str(run),model=old['model'],seed=20261106,
        python=str(Path(sys.executable).absolute()),python_version=sys.version,torch_version=str(torch.__version__),numpy_version=np.__version__,
        tokenizer=dict(vocabulary=50257,eot=50256,identity=ASSETS),code_sha256={n:sha(ROOT/n)for n in (*trainer.REQUIRED_CODE,'prepare_own_language_spec.py','verify_prepare_own_language_spec.py')},
        optimizer_report=old['optimizer_report'],optimizer_experiment=old['optimizer_experiment'],parent=parent,
        initialization=dict(mode='own_pretraining',path=str(Path(parent['run'])/parent['checkpoint']['file']),sha256=parent['checkpoint']['sha256'],random_lineage_root=origin['random_lineage_root']),
        hardware_evidence=dict(kind='completed_optimizer_screen_torch512',report=old['optimizer_report']),sources=descriptors,row_source_cycle=cycle,
        validation_selection=pin(selection),length=512,microbatch=2,accumulation=8,bf16=True,scheduler=dict(mode='constant',lr=6e-5),
        training_goal=GOAL,attempted_targets=GOAL+512*8192,evaluation_targets=6*validation['evaluation_targets'],evaluation_milestones=MILESTONES,
        active_seconds=84*3600,calendar_seconds=10*86400,lease_seconds=14400,checkpoint_seconds=600,checkpoint_margin_seconds=120,
        checkpoint_bytes=math.ceil(parent['checkpoint']['bytes']*1.1)+16*1024**2,disk_headroom_bytes=20*1024**3,cpu_rss_limit_bytes=18*1024**3,
        stop_paths=sorted(set(old['stop_paths']+[str(ROOT/'runs/STOP'),str(run/'STOP')])),external_milestone_gate=dict(milestones=MILESTONES,protocol=protocol_pin))
    # In-memory metadata validation only; disk draft remains non-runnable.
    trainer.validate_launch(dict(spec,state='reviewed_for_own_language_continuation'),run)
    allocation=dict(state='prospective_not_activated',updates=UPDATES,source_exposure=exposure['sources'],source_capacity={n:schedule.capacity(n)for n in schedule.sources},source_validation_events_nominal=4,source_validation_pass_budget=6,
        nominal_train_hours_at_1425=GOAL/1425/3600,attempt_ceiling_hours_at_1425=spec['attempted_targets']/1425/3600,
        external_protocol_active_seconds=protocol['budgets']['active_seconds'],limitations=['Metadata preparation does not hash token streams or load parent tensors; trainer performs these before execution.','Reserve is cumulative work, not a guarantee of any recovery count.','84 active hours include lease startup/checkpoint/evaluation work; calendar includes pauses and external evaluation.','No assistant usability claim.'])
    (output/'allocation.json').write_text(json.dumps(allocation,indent=2)+'\n');(output/'activation-draft.json').write_text(json.dumps(spec,indent=2)+'\n')
    return pin(output/'activation-draft.json')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--narrative',default=str(ROOT/'data/narrative-packed-v1'));p.add_argument('--explanatory',default=str(ROOT/'data/explanatory-packed-v3'));p.add_argument('--output',required=True);a=p.parse_args()
    print(json.dumps(prepare(a.narrative,a.explanatory,a.output),indent=2))
