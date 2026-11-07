"""Tiny CPU-only continuation fixtures; never read protected model/data artifacts."""
import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import torch
import checkpoint
from gpt2 import Config,GPT2
from train import optimizer_for
from own_base_language_data import MixedSchedule,validation_manifest
from own_base_language_control import LanguageCampaign,CampaignStop
from own_base_language_continue import run_training,restore,optimizer_step,validate_launch

class CPUGuard:
    def __init__(self,path,seconds,*,resume=False):
        self.path=Path(path)
        if not resume:self.path.mkdir()
    def check(self,*args,**kwargs):pass
    def close(self):pass

class Data:
    def __init__(self):
        doc=dict(id='a',tokens=24577,family='train',split='train',sha256='a'*64)
        self.schedule=MixedSchedule(dict(schema=1,seed=7,length=512,sources=[dict(name='fixture',passes=1,documents=[doc])],row_source_cycle=['fixture']*16))
        docs=[dict(source='fixture',id=str(i),tokens=33,split='validation',sha256='b'*64) for i in (1,2)]
        self.validation=validation_manifest(docs,[dict(source='fixture',id=str(i),offset=0,targets=32) for i in (1,2)])
        self.fail_row=False
    def row(self,row):
        if self.fail_row:self.fail_row=False;raise KeyboardInterrupt('fixture midupdate interruption')
        return np.arange(row['offset'],row['offset']+513,dtype=np.int64)%32
    def validation_row(self,w):return (np.arange(33,dtype=np.int64)+int(w['id']))%32

class Tests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1);torch.manual_seed(123)
        self.config=Config(vocabulary=32,context=1024,width=8,heads=2,depth=1)
        m=GPT2(self.config);o=optimizer_for(m);loss=m(torch.tensor([[1,2,3]])).square().mean();loss.backward();o.step()
        self.parent=copy.deepcopy(dict(model=m.state_dict(),optimizer=o.state_dict(),cpu_rng=torch.get_rng_state(),mps_rng=None))
        self.spec=dict(seed=7,length=512,microbatch=2,accumulation=8,bf16=False,scheduler=dict(mode='constant',lr=6e-5),tokenizer={'fixture':True},initialization=dict(mode='own_pretraining',path='/fixture/parent',sha256='a'*64,random_lineage_root={'fixture':True}),training_goal=16384,attempted_targets=24576,evaluation_targets=1000,active_seconds=100,calendar_seconds=200,lease_seconds=100,checkpoint_seconds=99,checkpoint_margin_seconds=.01,checkpoint_bytes=100000,disk_headroom_bytes=1,cpu_rss_limit_bytes=2**40,stop_paths=[],evaluation_milestones=[0,16384])
    def execute(self,root,data=None,spec=None,callback=None):
        return run_training(spec or self.spec,root,data or Data(),self.parent,device='cpu',guard_factory=CPUGuard,model_config=self.config,after_update=callback)
    def payload(self,path):
        e=json.loads((path/'latest.json').read_text())[0];return torch.load(path/e['file'],weights_only=True)
    def test_full_moments_rng_initial_restore(self):
        m=GPT2(self.config);o,step=restore(m,self.parent,'cpu');self.assertEqual(step,1)
        for a,b in zip(o.state_dict()['state'].values(),self.parent['optimizer']['state'].values()):
            for key in a:self.assertTrue(torch.equal(a[key],b[key]))
        self.assertTrue(torch.equal(torch.get_rng_state(),self.parent['cpu_rng']))
    def test_uninterrupted_equals_boundary_resume(self):
        with tempfile.TemporaryDirectory() as td:
            a=Path(td)/'a';b=Path(td)/'b';self.assertEqual(self.execute(a),'completed')
            def stop(step,campaign):raise KeyboardInterrupt('fixture lease boundary')
            self.assertEqual(self.execute(b,callback=stop),'interrupted')
            self.assertEqual(self.execute(b,spec=dict(self.spec,_resume=True)),'completed')
            left,right=self.payload(a),self.payload(b)
            for key in left['model']:self.assertTrue(torch.equal(left['model'][key],right['model'][key]),key)
            for key,state in left['optimizer']['state'].items():
                for field,value in state.items():self.assertTrue(torch.equal(value,right['optimizer']['state'][key][field]))
            self.assertEqual(left['cursor'],right['cursor']);self.assertEqual(left['history'],right['history']);self.assertTrue(torch.equal(left['cpu_rng'],right['cpu_rng']))
    def test_inflight_reservation_not_refunded(self):
        with tempfile.TemporaryDirectory() as td:
            run=Path(td)/'run';data=Data();data.fail_row=True
            self.assertEqual(self.execute(run,data),'interrupted');before=json.loads((run/'campaign.json').read_text())
            self.assertEqual(before['reserved_tokens'],8192);self.assertEqual(before['trained_tokens'],0)
            self.assertEqual(self.execute(run,spec=dict(self.spec,_resume=True)),'completed');after=json.loads((run/'campaign.json').read_text())
            self.assertEqual(after['reserved_tokens'],24576);self.assertEqual(after['trained_tokens'],16384)
    def test_attempt_budget_exhaustion_not_success(self):
        with tempfile.TemporaryDirectory() as td:
            run=Path(td)/'run';data=Data();data.fail_row=True;spec=dict(self.spec,attempted_targets=16384)
            self.assertEqual(self.execute(run,data,spec),'interrupted')
            self.assertEqual(self.execute(run,spec=dict(spec,_resume=True)),'budget-exhausted')
            self.assertEqual(json.loads((run/'campaign.json').read_text())['trained_tokens'],8192)
    def test_evaluation_attempts_and_immutable_resume(self):
        with tempfile.TemporaryDirectory() as td:
            run=Path(td)/'run';data=Data();data.fail_row=True;self.execute(run,data)
            with self.assertRaisesRegex(ValueError,'immutable'):self.execute(run,spec=dict(self.spec,_resume=True,attempted_targets=32768))
            ledger=json.loads((run/'campaign.json').read_text());self.assertEqual(ledger['reserved_evaluation_targets'],64)
    def test_interrupted_validation_is_recharged(self):
        with tempfile.TemporaryDirectory() as td:
            run=Path(td)/'run';data=Data()
            with patch.object(data,'validation_row',side_effect=KeyboardInterrupt('fixture validation interruption')):
                self.assertEqual(self.execute(run,data),'interrupted')
            self.assertEqual(json.loads((run/'campaign.json').read_text())['reserved_evaluation_targets'],32)
            self.assertEqual(self.execute(run,spec=dict(self.spec,_resume=True)),'completed')
            self.assertEqual(json.loads((run/'campaign.json').read_text())['reserved_evaluation_targets'],160)
    def test_failed_publication_preserves_accepted_checkpoint(self):
        with tempfile.TemporaryDirectory() as td:
            run=Path(td)/'run';data=Data();data.fail_row=True;self.execute(run,data)
            accepted=(run/'latest.json').read_bytes();ledger=json.loads((run/'campaign.json').read_text())
            with patch.object(checkpoint,'save',side_effect=OSError('fixture publication failure')):
                with self.assertRaises(OSError):self.execute(run,spec=dict(self.spec,_resume=True))
            self.assertEqual((run/'latest.json').read_bytes(),accepted)
            after=json.loads((run/'campaign.json').read_text());self.assertEqual(after['checkpoints'],ledger['checkpoints'])
    def test_external_milestone_blocks_updates_until_exact_review(self):
        from own_base_language_streams import sha
        with tempfile.TemporaryDirectory() as td:
            root=Path(td).resolve();run=root/'run';protocol=root/'protocol.json';protocol.write_text('{}');result=root/'result.json';result.write_text('{}')
            pin=lambda path:dict(path=str(path),sha256=sha(path))
            spec=dict(self.spec,external_milestone_gate=dict(milestones=[0,16384],protocol=pin(protocol)))
            self.assertEqual(self.execute(run,spec=spec),'paused-milestone')
            self.assertEqual(json.loads((run/'campaign.json').read_text())['reserved_tokens'],0)
            def approve(n):
                (run/f'milestone-{n}-decision.json').write_text(json.dumps(dict(state='root_reviewed_external_milestone',decision='continue',request_sha256=sha(run/f'milestone-{n}-request.json'),protocol_sha256=sha(protocol),result_receipts=[pin(result)])))
            approve(0);self.assertEqual(self.execute(run,spec=dict(spec,_resume=True)),'paused-milestone')
            self.assertEqual(json.loads((run/'campaign.json').read_text())['trained_tokens'],16384)
            approve(16384);self.assertEqual(self.execute(run,spec=dict(spec,_resume=True)),'completed')
    def test_checkpoint_tamper_and_stop(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);run=root/'run';data=Data();data.fail_row=True;self.execute(run,data)
            e=json.loads((run/'latest.json').read_text())[0];(run/e['file']).write_bytes(b'corrupt')
            with self.assertRaises(Exception):self.execute(run,spec=dict(self.spec,_resume=True))
            stop=root/'STOP';stop.touch()
            with self.assertRaises(CampaignStop):self.execute(root/'other',spec=dict(self.spec,stop_paths=[str(stop)]))
    def test_unreviewed_cli_spec_refused(self):
        with self.assertRaisesRegex(ValueError,'reviewed'):validate_launch({'state':'draft'},'/fixture')

if __name__=='__main__':unittest.main(verbosity=2)
