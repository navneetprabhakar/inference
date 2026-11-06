"""Tiny CPU-only tests; never inspect production runs or allocate full models."""
import os
os.environ['OMP_NUM_THREADS']='1'
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import numpy as np
import torch
from torch.nn import functional as F
import own_base_sft_train as t
from own_base_sft_control import SFTCampaign,WORK
from base_run_control import CampaignStop
from gpt2 import Config,GPT2
from train import optimizer_for
from verify_base_run_control import Guard

torch.set_num_threads(1)
CFG=Config(vocabulary=19,context=32,width=12,heads=3,depth=1)

class Data:
    def __init__(self):
        self.values=[(np.array([1,2,3]),np.array([-100,3,4])),(np.array([4,5,6,7,8]),np.array([-100,-100,7,8,9])),(np.array([2,3]),np.array([-100,4]))]
        self.rows={split:[dict(length=len(x),target_count=int((y!=-100).sum()),_source='a' if i<2 else 'b') for i,(x,y) in enumerate(self.values)] for split in ('train','validation')}
    def row(self,split,index):return self.values[index]


def limits():return dict(assistant_targets=1000,input_tokens=10000,padded_tokens=20000,attention_cells=100000,evaluation_targets=1000)
def identity(lim):return dict(initialization='random',seed=1,model=asdict(CFG),tokenizer='fixture',corpus='fixture',scheduler='fixture',work_limits=lim,source_work_limits={'a':deepcopy(lim),'b':deepcopy(lim)})
def campaign(path,lim=None,resume=False):
    lim=lim or limits()
    return SFTCampaign(path,identity(lim),limits=lim,active_seconds=1000,calendar_seconds=10000,lease_seconds=100,resume=resume,guard_factory=Guard)
def spec():return dict(seed=17,schedule_rows_limit=100,microbatch=2,evaluation_microbatch=1,accumulation=1,mixing='proportional_source_update_midpoints',datasets=[dict(name='a',passes=2,validation_rows=2,development_split='validation'),dict(name='b',passes=1,validation_rows=1,development_split='exposed-development')],bf16=False,scheduler=dict(kind='warmup_cosine_updates',warmup_updates=0,peak_lr=.0001,end_fraction=.1))

class Checks(unittest.TestCase):
    def test_masked_padding_matches_individual_gradients(self):
        d=Data();torch.manual_seed(4);a=GPT2(CFG);b=GPT2(CFG);b.load_state_dict(a.state_dict());x,y=t.padded(d,[0,1],'train','cpu');mask=y!=-100
        F.cross_entropy(a(x,prediction_mask=mask),y[mask],reduction='sum').div(5).backward()
        for index in [0,1]:
            x,y=t.padded(d,[index],'train','cpu');mask=y!=-100;F.cross_entropy(b(x,prediction_mask=mask),y[mask],reduction='sum').div(5).backward()
        for p,q in zip(a.parameters(),b.parameters()):torch.testing.assert_close(p.grad,q.grad,atol=2e-6,rtol=2e-5)
        self.assertEqual(t.work_for(d,[0,1],2),dict(assistant_targets=5,input_tokens=8,padded_tokens=10,attention_cells=50,evaluation_targets=0))
    def test_explicit_source_passes(self):
        d=Data();s=spec();plan=t.updates(d,s)
        self.assertEqual(plan,t.updates(d,s));self.assertEqual(len(plan),3)
        flat=[i for row in plan for i in row];self.assertEqual([flat.count(i) for i in range(3)],[2,2,1])
        self.assertEqual([d.rows['train'][row[0]]['_source'] for row in plan],['a','b','a'])
    def test_uneven_sources_are_spread_through_run(self):
        d=Data();s=spec();s['datasets'][0]['passes']=10;s['datasets'][1]['passes']=3
        plan=t.updates(d,s);names=[d.rows['train'][batch[0]]['_source'] for batch in plan]
        positions=[i for i,name in enumerate(names) if name=='b']
        self.assertEqual(names.count('a'),10);self.assertEqual(names.count('b'),3)
        self.assertGreater(positions[-1],len(names)*.75);self.assertLessEqual(len(names)-1-positions[-1],2)
        s['schedule_rows_limit']=2
        with self.assertRaises(ValueError):t.updates(d,s)
    def test_atomic_reservation_replay_and_source_caps(self):
        with TemporaryDirectory() as folder:
            p=Path(folder)/'run';w=t.work_for(Data(),[0,1],2)
            with campaign(p) as c:
                c.save(dict(step=0,model={'w':torch.tensor([1.])},optimizer={}))
                c.reserve_work(w,'a')
                signed=json.loads((p/'campaign.json').read_text());signature=signed.pop('sha256')
                self.assertEqual(signature,hashlib.sha256(t.canonical(signed)).hexdigest());self.assertEqual(signed['reserved_work'],w);self.assertEqual(signed['reserved_by_source']['a'],w)
                with self.assertRaises(ValueError):c.save(dict(step=0))
                c.finish('interrupted','partial optimizer update')
            with campaign(p,resume=True) as c:
                saved=c.load();self.assertEqual(saved['step'],0);self.assertEqual(c.ledger['committed_work']['input_tokens'],0);self.assertEqual(c.ledger['reserved_work'],w)
                c.reserve_work(w,'a');c.commit_work(1);c.save(dict(step=1,model={'w':torch.tensor([2.])},optimizer={}));c.finish('paused-lease')
            with campaign(p,resume=True) as c:
                self.assertEqual(c.load()['step'],1);self.assertEqual(c.ledger['reserved_work']['padded_tokens'],20);self.assertEqual(c.ledger['committed_work']['padded_tokens'],10)
                with self.assertRaises(ValueError):c.reserve_work(w,'unknown')
    def test_committed_without_checkpoint_rolls_back_but_charges(self):
        with TemporaryDirectory() as folder:
            p=Path(folder)/'run';w=t.work_for(Data(),[0],1)
            with campaign(p) as c:
                c.save(dict(step=0,model={'x':torch.tensor([1.])},optimizer={}))
                c.reserve_work(w,'a');c.commit_work(1);c.finish('interrupted')
            with campaign(p,resume=True) as c:
                c.load();self.assertEqual(c.ledger['step'],0);self.assertEqual(c.ledger['committed_work']['assistant_targets'],0);self.assertEqual(c.ledger['reserved_tokens'],2)
    def test_compute_ceiling_refuses_before_work(self):
        with TemporaryDirectory() as folder:
            lim=limits();lim['padded_tokens']=9;lim['input_tokens']=9
            with campaign(Path(folder)/'run',lim) as c:
                with self.assertRaises(CampaignStop):c.reserve_work(t.work_for(Data(),[0,1],2),'a')
                self.assertEqual(c.ledger['reserved_tokens'],0)
    def test_validation_is_charged_and_source_reported(self):
        with TemporaryDirectory() as folder:
            with campaign(Path(folder)/'run') as c:
                r=t.evaluate(GPT2(CFG),Data(),spec(),c,'cpu');self.assertEqual(set(r['sources']),{'a','b'})
                self.assertEqual(c.ledger['reserved_work']['evaluation_targets'],6);self.assertEqual(c.ledger['reserved_tokens'],0)
                self.assertGreater(c.ledger['reserved_work']['input_tokens'],0)
    def test_exact_optimizer_rng_resume(self):
        d=Data();s=spec();torch.manual_seed(12);base=GPT2(CFG).state_dict()
        a=GPT2(CFG);a.load_state_dict(base);ao=optimizer_for(a)
        t.update(a,ao,d,[0,1],s,0,2,lambda:None,'cpu');t.update(a,ao,d,[2],s,1,2,lambda:None,'cpu')
        with TemporaryDirectory() as folder:
            p=Path(folder)/'run';b=GPT2(CFG);b.load_state_dict(base);bo=optimizer_for(b)
            with campaign(p) as c:
                c.reserve_work(t.work_for(d,[0,1],2),'a');t.update(b,bo,d,[0,1],s,0,2,c.check,'cpu');c.commit_work(1)
                c.save(dict(step=1,cursor=1,model=b.state_dict(),optimizer=bo.state_dict(),cpu_rng=torch.get_rng_state()));c.finish('paused-lease')
            with campaign(p,resume=True) as c:
                saved=c.load();b=GPT2(CFG);b.load_state_dict(saved['model']);bo=optimizer_for(b);bo.load_state_dict(saved['optimizer']);torch.set_rng_state(saved['cpu_rng'])
                c.reserve_work(t.work_for(d,[2],2),'b');t.update(b,bo,d,[2],s,1,2,c.check,'cpu');c.commit_work(2)
                for x,y in zip(a.parameters(),b.parameters()):self.assertTrue(torch.equal(x,y))
                for pid,state in ao.state_dict()['state'].items():
                    for key,value in state.items():self.assertTrue(torch.equal(value,bo.state_dict()['state'][pid][key]))
    def test_stop_and_unreviewed_launch_refusal(self):
        with TemporaryDirectory() as folder:
            with campaign(Path(folder)/'run') as c:
                (c.path/'STOP').touch()
                with self.assertRaises(CampaignStop):c.reserve_work(t.work_for(Data(),[0],1),'a')
            with self.assertRaises(ValueError):t.validate_launch(dict(state='candidate'),Path(folder)/'future')
    def test_stream_roundtrip_and_tamper(self):
        with TemporaryDirectory() as folder:
            root=Path(folder);outputs={}
            for split in ('train','validation'):
                x=np.array([1,2,3],dtype='<u2');y=np.array([65535,3,4],dtype='<u2')
                for suffix,array in [('inputs.u16',x),('labels.u16',y)]:array.tofile(root/f'{split}.{suffix}')
                (root/f'{split}.index.jsonl').write_text(json.dumps(dict(offset=0,length=3,target_count=2,split=split,family=split,doc_id=split))+'\n')
            for p in root.iterdir():outputs[p.name]=dict(bytes=p.stat().st_size,sha256=t.digest(p))
            receipt=root/'receipt.json';receipt.write_text(json.dumps(dict(outputs=outputs)));pin=dict(path=str(receipt),sha256=t.digest(receipt))
            stream=t.Streams(pin,vocabulary=19,context=32);self.assertEqual(stream.row('train',0)[1].tolist(),[-100,3,4])
            (root/'train.labels.u16').write_bytes(b'changed')
            with self.assertRaises(ValueError):t.Streams(pin,vocabulary=19,context=32)
    def test_selected_payload_finite_moments_and_cursor(self):
        model=GPT2(CFG);opt=optimizer_for(model);d=Data();t.update(model,opt,d,[0],spec(),0,1,lambda:None,'cpu')
        state=opt.state_dict()
        for row in state['state'].values():row['step']=torch.tensor(t.TARGET//8192.)
        frozen=dict(identity=dict(protocol=dict(branch='reset-095',source_offset=99999744)))
        ledger=dict(campaign_id='tiny');payload=dict(identity=frozen['identity'],campaign_id='tiny',spec_sha256=hashlib.sha256(t.canonical(frozen)).hexdigest(),trained_tokens=t.TARGET,step=t.TARGET//8192,initial_optimizer_step=0,offset=99999744+t.TARGET,model=model.state_dict(),optimizer=state)
        t.validate_parent_payload(payload,frozen,{},ledger,CFG)
        wrong=deepcopy(payload);wrong['offset']+=1
        with self.assertRaises(ValueError):t.validate_parent_payload(wrong,frozen,{},ledger,CFG)
        wrong=deepcopy(payload);next(iter(wrong['optimizer']['state'].values()))['exp_avg_sq'].flatten()[0]=-1
        with self.assertRaises(ValueError):t.validate_parent_payload(wrong,frozen,{},ledger,CFG)
    def test_exposed_development_physical_stream_label(self):
        with TemporaryDirectory() as folder:
            root=Path(folder);outputs={}
            for split in ('train','exposed-development'):
                np.array([1,2,3],dtype='<u2').tofile(root/f'{split}.inputs.u16')
                np.array([65535,3,4],dtype='<u2').tofile(root/f'{split}.labels.u16')
                (root/f'{split}.index.jsonl').write_text(json.dumps(dict(offset=0,length=3,target_count=2,split=split,family=split,doc_id=split))+'\n')
            for file in root.iterdir():outputs[file.name]=dict(bytes=file.stat().st_size,sha256=t.digest(file))
            receipt=root/'receipt.json';receipt.write_text(json.dumps(dict(outputs=outputs)));pin=dict(path=str(receipt),sha256=t.digest(receipt))
            data=t.Streams(pin,development_split='exposed-development',vocabulary=19,context=32)
            self.assertEqual(data.rows['validation'][0]['split'],'exposed-development')
    def test_per_source_ceiling_and_stop_classification(self):
        with TemporaryDirectory() as folder:
            lim=limits();ident=identity(lim);ident['source_work_limits']['a']['assistant_targets']=1
            with SFTCampaign(Path(folder)/'run',ident,limits=lim,active_seconds=1000,calendar_seconds=10000,lease_seconds=100,guard_factory=Guard) as c:
                with self.assertRaises(CampaignStop):c.reserve_work(t.work_for(Data(),[0],1),'a')
                self.assertEqual(c.ledger['reserved_tokens'],0)
            marker=Path(folder)/'stop';marker.touch()
            with self.assertRaises(CampaignStop) as raised:t.stop_check(dict(stop_paths=[str(marker)]))
            self.assertEqual(raised.exception.state,'interrupted')
    def test_canonical_shared_lock_run_path(self):
        with TemporaryDirectory() as folder:
            root=Path(folder).resolve();(root/'runs').mkdir();valid=root/'runs'/'future-sft'
            with patch.object(t,'ROOT',root):
                self.assertEqual(t.validate_run_path(dict(run=str(valid)),valid),valid)
                invalid=[root/'outside',root/'runs'/'nested'/'worker',Path('runs/relative'),root/'runs'/'nested'/'..'/'worker']
                (root/'alias').symlink_to(root/'runs',target_is_directory=True);invalid.append(root/'alias'/'worker')
                target=root/'external';target.mkdir();link=root/'runs'/'linked';link.symlink_to(target,target_is_directory=True);invalid.append(link)
                for path in invalid:
                    with self.subTest(path=path),patch.object(t,'pinned_json') as io:
                        with self.assertRaises(ValueError):t.validate_launch(dict(run=str(path)),path)
                        io.assert_not_called()
                with self.assertRaises(ValueError):t.validate_run_path(dict(run=str(valid)+'-other'),valid)
                (root/'runs').rename(root/'real-runs');(root/'runs').symlink_to(root/'real-runs',target_is_directory=True)
                with self.assertRaises(ValueError):t.validate_run_path(dict(run=str(valid)),valid)
    def test_missing_multidimensional_budget(self):
        with TemporaryDirectory() as folder:
            lim=limits();del lim['padded_tokens']
            with self.assertRaises(ValueError):campaign(Path(folder)/'run',lim)

if __name__=='__main__':unittest.main(verbosity=2)
