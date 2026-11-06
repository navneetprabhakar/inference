"""Synthetic CPU checkpoint export tests; no production run/model/endpoint reads."""
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import weakref
from unittest.mock import patch
import numpy as np
import torch
from gpt2 import Config,GPT2
from train import optimizer_for
import checkpoint
import own_base_sft_export as e
from own_base_sft_control import SFTCampaign,WORK
from verify_base_run_control import Guard

torch.set_num_threads(1)
CFG=Config(vocabulary=19,context=16,width=8,heads=2,depth=1)

class Data:
    def __init__(self):self.rows={split:[dict(_source='chat',length=3,target_count=2,doc_id=split,family=split)] for split in ('train','validation')}
    def row(self,split,index):return np.array([1,2,3]),np.array([-100,3,4])


def fixture(root):
    (root/'runs').mkdir();(root/'runs/mps.lock').touch();assets={}
    (root/'data/tokenizer').mkdir(parents=True)
    for name in ('encoder.json','vocab.bpe'):
        path=root/'data/tokenizer'/name;path.write_bytes(name.encode());assets[name]=e.digest(path)
    dummy=root/'evidence.json';dummy.write_text('{}');p=dict(path=str(dummy),sha256=e.digest(dummy))
    parent_file=root/'runs/own-parent.pt';parent_file.write_bytes(b'synthetic CPU own parent fixture')
    parent_receipt=dict(run=str(root/'runs'),checkpoint=dict(file=parent_file.name,sha256=e.digest(parent_file),bytes=parent_file.stat().st_size),ledger_sha256='fixture')
    lineage=dict(mode='own_pretraining',path=str(parent_file),sha256=e.digest(parent_file),random_lineage_root='f'*64)
    lim=dict(assistant_targets=100,input_tokens=100,padded_tokens=100,attention_cells=1000,evaluation_targets=100)
    run=root/'runs/sft'
    source=dict(name='chat',receipt=p,admission=p,verification=p,passes=1,validation_rows=1,development_split='validation',work_limits=lim)
    spec=dict(run=str(run),model=asdict(CFG),seed=3,datasets=[source],mixing='proportional_source_update_midpoints',microbatch=1,accumulation=1,schedule_rows_limit=10,evaluation_microbatch=1,validation_updates=1,work_limits=lim,scheduler=dict(kind='warmup_cosine_updates',peak_lr=.0001,end_fraction=1.,warmup_updates=0),active_seconds=1000,calendar_seconds=10000,lease_seconds=100,hardware_preflight=p,optimizer_report=p,optimizer_experiment=p,code_sha256={})
    identity=dict(seed=3,model=asdict(CFG),tokenizer=assets,torch_version=str(torch.__version__),initialization=lineage,parent=parent_receipt,optimizer_initialization='fresh_selected_beta2',beta2=.95,work_limits=lim,source_work_limits={'chat':lim},protocol=spec,corpus=spec['datasets'],scheduler=spec['scheduler'])
    data=Data();model=GPT2(CFG);opt=optimizer_for(model);cpu=torch.get_rng_state();mps=torch.zeros(16,dtype=torch.uint8)
    history=[dict(step=step,sources={'chat':dict(masked_ce=1.,targets=2,rows=1,physical_split='validation',precision='fp32')}) for step in (0,1)]
    with SFTCampaign(run,identity,limits=lim,active_seconds=1000,calendar_seconds=10000,lease_seconds=100,guard_factory=Guard) as campaign:
        campaign.reserve_evaluation(e.trainer.work_for(data,[0],1,'validation'),'chat')
        campaign.reserve_work(e.trainer.work_for(data,[0],1),'chat')
        e.trainer.update(model,opt,data,[0],dict(spec,bf16=False),0,1,lambda:None,'cpu');campaign.commit_work(1)
        campaign.reserve_evaluation(e.trainer.work_for(data,[0],1,'validation'),'chat')
        campaign.save(dict(step=1,cursor=1,model=model.state_dict(),optimizer=opt.state_dict(),cpu_rng=cpu,mps_rng=mps,history=history,position_exposure=[2,0,0,0]));checkpoint.protect(run);campaign.finish('completed')
    parent=dict(identity={'initialization':lineage},mps_rng=mps)
    def artifacts(run,spec,check=lambda:None):
        entry=json.loads((run/'latest.json').read_text())[0]
        paths=[run/name for name in ('campaign.json','campaign-spec.json','latest.json','protected.json',entry['file'])]+[dummy,parent_file]+[root/'data/tokenizer'/name for name in assets]
        return [e.pin(path,check) for path in sorted(paths)]
    stack=ExitStack();stack.enter_context(patch.object(e,'ROOT',root));stack.enter_context(patch.object(e,'ASSETS',assets));stack.enter_context(patch.object(e.os,'nice',return_value=10));stack.enter_context(patch.object(e.shutil,'disk_usage',return_value=type('Disk',(),{'free':100*1024**3})()))
    stack.enter_context(patch.object(e.trainer,'validate_launch',return_value=None));stack.enter_context(patch.object(e.trainer,'verified_parent',return_value=(parent,'reset-095',parent_receipt)));stack.enter_context(patch.object(e.trainer,'Sources',return_value=data));stack.enter_context(patch.object(e,'proof_artifacts',side_effect=artifacts))
    return stack,run,model


class Checks(unittest.TestCase):
    def test_full_tiny_export_loader_and_immutable_output(self):
        with TemporaryDirectory() as directory:
            root=Path(directory).resolve();stack,run,model=fixture(root)
            with stack:
                dest=root/'own-base-candidates/tiny';result=e.export_candidate(run,dest);state,manifest=e.load_candidate(result['manifest'],result['manifest_sha256'])
                self.assertEqual(manifest['status'],e.STATUS);self.assertFalse(manifest['release_approved']);self.assertEqual(manifest['parameter_count'],sum(p.numel() for p in model.parameters()))
                for name,value in model.state_dict().items():self.assertTrue(torch.equal(state[name],value))
                self.assertEqual(manifest['verification']['committed_work']['assistant_targets'],2)
                with self.assertRaises(FileExistsError):e.export_candidate(run,dest)
                with self.assertRaises(ValueError):e.load_candidate(result['manifest'],'0'*64)
    def test_checkpoint_state_counter_optimizer_rng_rejections(self):
        with TemporaryDirectory() as directory:
            root=Path(directory).resolve();stack,run,model=fixture(root)
            with stack:
                entry=json.loads((run/'latest.json').read_text())[0];payload=torch.load(run/entry['file'],weights_only=True,mmap=True)
                variants=[]
                q=deepcopy(payload);q['cursor']=0;variants.append(q)
                q=deepcopy(payload);q['committed_work']['input_tokens']+=1;variants.append(q)
                q=deepcopy(payload);q['position_exposure']=[0,2,0,0];variants.append(q)
                q=deepcopy(payload);q['mps_rng']=torch.zeros(2,dtype=torch.uint8);variants.append(q)
                q=deepcopy(payload);q['cpu_rng']=torch.zeros(2);variants.append(q)
                q=deepcopy(payload);next(iter(q['optimizer']['state'].values()))['exp_avg_sq'].flatten()[0]=-1;variants.append(q)
                q=deepcopy(payload);q['model']['tokens.weight'][0,0]=float('nan');variants.append(q)
                for flag in ('maximize','amsgrad'):
                    q=deepcopy(payload);q['optimizer']['param_groups'][0][flag]=True;variants.append(q)
                for altered in variants:
                    with self.subTest(keys=altered.keys()),patch.object(e.torch,'load',return_value=altered):
                        with self.assertRaises((ValueError,RuntimeError)):e.verify_source(run)
    def test_parent_tensor_storage_released_before_sft_load(self):
        with TemporaryDirectory() as directory:
            root=Path(directory).resolve();stack,run,model=fixture(root)
            with stack:
                frozen=json.loads((run/'campaign-spec.json').read_text());identity=frozen['identity'];seen={};real_load=torch.load
                def parent():
                    tensor=torch.ones(32);seen['tensor']=weakref.ref(tensor)
                    return dict(model={'fixture':tensor},optimizer={'fixture':tensor},identity={'initialization':deepcopy(identity['initialization'])},mps_rng=torch.zeros(16,dtype=torch.uint8)),'reset-095',identity['parent']
                def load(*args,**kwargs):
                    self.assertIsNone(seen['tensor']())
                    return real_load(*args,**kwargs)
                with patch.object(e.trainer,'verified_parent',side_effect=lambda spec:parent()),patch.object(e.torch,'load',side_effect=load):
                    e.verify_source(run)
    def test_completed_protected_ledger_requirements(self):
        with TemporaryDirectory() as directory:
            root=Path(directory).resolve();stack,run,model=fixture(root)
            with stack:
                protected=run/'protected.json';protected.write_text('[]')
                with self.assertRaises(ValueError):e.verify_source(run)
        with TemporaryDirectory() as directory:
            root=Path(directory).resolve();stack,run,model=fixture(root)
            with stack:
                p=run/'campaign.json';ledger=json.loads(p.read_text());ledger['state']='running';ledger.pop('sha256');ledger['sha256']=hashlib.sha256(e.canonical(ledger)).hexdigest();p.write_text(json.dumps(ledger))
                with self.assertRaises(ValueError):e.verify_source(run)
    def test_weights_tamper_and_failure_evidence_refused(self):
        with TemporaryDirectory() as directory:
            root=Path(directory).resolve();stack,run,model=fixture(root)
            with stack:
                result=e.export_candidate(run,root/'own-base-candidates/tiny');manifest=json.loads(Path(result['manifest']).read_text());weights=Path(result['manifest']).parent/manifest['weights']['file'];weights.write_bytes(b'tampered')
                with self.assertRaises(ValueError):e.load_candidate(result['manifest'],result['manifest_sha256'])
    def test_source_proof_changes_refused(self):
        with TemporaryDirectory() as directory:
            root=Path(directory).resolve();stack,run,model=fixture(root)
            with stack:
                result=e.export_candidate(run,root/'own-base-candidates/tiny');(root/'evidence.json').write_text('{"changed":true}')
                with self.assertRaises(ValueError):e.verify_candidate_manifest(result['manifest'],result['manifest_sha256'])
    def test_weights_replaced_after_manifest_verification_refused(self):
        with TemporaryDirectory() as directory:
            root=Path(directory).resolve();stack,run,model=fixture(root)
            with stack:
                result=e.export_candidate(run,root/'own-base-candidates/tiny');real_verify=e.verify_candidate_manifest
                def replace(*args,**kwargs):
                    manifest=real_verify(*args,**kwargs)
                    changed={key:value.clone()+1 for key,value in model.state_dict().items()}
                    torch.save(changed,Path(result['manifest']).parent/manifest['weights']['file'])
                    return manifest
                with patch.object(e,'verify_candidate_manifest',side_effect=replace):
                    with self.assertRaisesRegex(ValueError,'opened candidate weights changed'):e.load_candidate(result['manifest'],result['manifest_sha256'])
    def test_stop_alias_and_cap(self):
        with TemporaryDirectory() as directory:
            root=Path(directory).resolve();stack,run,model=fixture(root)
            with stack:
                (root/'runs/STOP').touch()
                with self.assertRaises(RuntimeError):e.export_candidate(run,root/'own-base-candidates/tiny')
                self.assertFalse((root/'own-base-candidates/tiny').exists())
                alias=root/'alias';alias.symlink_to(run,target_is_directory=True)
                with self.assertRaises(ValueError):e.own_path(alias)
                with self.assertRaises(ValueError):e.output_path(root/'elsewhere')
                with self.assertRaises(ValueError):e.state_shapes(dict(vocabulary=1000000,context=1024,width=1024,heads=16,depth=12))

if __name__=='__main__':unittest.main(verbosity=2)
