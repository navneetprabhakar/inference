"""CPU optimizer/resume regression with synthetic tokens and a tiny model."""
import json
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import torch
import base_train
import checkpoint
from base_run_control import Campaign
from gpt2 import Config, GPT2
from verify_base_run_control import Guard

class Tokenizer:
    def encode(self,text):return SimpleNamespace(ids=[1+ord(c)%30 for c in text])
    def decode(self,ids):return ' '.join(map(str,ids))

class Corpus:
    def __init__(self,*args,device='cpu'):
        self.length=256
        self.arrays={'train':np.arange(4096)%31+1,'validation':np.arange(4096)%31+1}
        self.blocks=[dict(offset=i,tokens=257) for i in range(128)]
    def row(self,split,offset,length,batch=1):
        return torch.tensor(np.stack([self.arrays[split][offset+i*length:offset+(i+1)*length+1] for i in range(batch)]),dtype=torch.long)

class TestCampaign(Campaign):
    interrupt=None
    def __init__(self,*args,**kwargs):super().__init__(*args,guard_factory=Guard,**kwargs)
    def commit(self,*args):
        super().commit(*args)
        if self.interrupt=='commit':
            type(self).interrupt=None
            raise KeyboardInterrupt('test committed-boundary interruption')
    def save(self,state):
        super().save(state)
        if self.interrupt=='milestone-save' and state['step']==2 and len(state['history'])==3:
            type(self).interrupt=None
            raise KeyboardInterrupt('test interruption after complete milestone checkpoint')
    def reserve(self,*args):
        super().reserve(*args)
        if self.interrupt=='reserve':
            type(self).interrupt=None
            raise KeyboardInterrupt('test interrupted reserved update')

def latest(path):
    ledger=json.loads((path/'campaign.json').read_bytes())
    return checkpoint.load(path,ledger['spec']['identity']),ledger

def run():
    torch.set_num_threads(1)
    cfg=Config(vocabulary=32,context=512,width=16,heads=2,depth=1)
    torch.manual_seed(17);initial=GPT2(cfg).state_dict()
    with TemporaryDirectory() as directory, ExitStack() as stack:
        root=Path(directory)
        diagnostic=root/'diagnostics.json'
        diagnostic.write_text(json.dumps(dict(prefixes=[{'text':'Test'}],pairs=[dict(id='p',choices=[' a',' b'],members=[dict(prefix='One',correct=0),dict(prefix='Two',correct=1)])])))
        spec=dict(length=256,microbatch=1,targets_per_update=256,target_tokens=768,
                  scheduler=dict(horizon_tokens=768,warmup_tokens=256,decay_start_tokens=512,peak_lr=.00006,end_fraction=.1),
                  corpus='synthetic',manifest_sha256='test',validation_blocks_sha256='test',
                  diagnostics=str(diagnostic),diagnostics_sha256=checkpoint.checksum(diagnostic),
                  seed=17,active_seconds=300,calendar_seconds=600,lease_seconds=200,bf16=False)
        spec_path=root/'spec.json';spec_path.write_text(json.dumps(spec))
        parent=dict(path='own-test-parent',sha256='test',acceptance_report_sha256='test',target_tokens=0)
        for name,value in [('Corpus',Corpus),('Campaign',TestCampaign),('load',lambda:Tokenizer()),
                           ('continuation_parent',lambda *_:parent),('load_base',lambda *a,**k:initial)]:
            stack.enter_context(patch.object(base_train,name,value))
        def train(name,resume=False):return base_train.train(spec_path,root/name,resume=resume,device='cpu',model_config=cfg)
        assert train('whole')=='completed'
        TestCampaign.interrupt='commit'
        assert train('paused')=='interrupted'
        assert train('paused',True)=='completed'
        a,la=latest(root/'whole');b,lb=latest(root/'paused')
        assert a['step']==b['step']==3 and a['offset']==b['offset']==768
        assert all(torch.equal(a['model'][k],b['model'][k]) for k in a['model'])
        for key,state in a['optimizer']['state'].items():
            for field,value in state.items():
                other=b['optimizer']['state'][key][field]
                assert torch.equal(value,other) if torch.is_tensor(value) else value==other
        TestCampaign.interrupt='reserve'
        assert train('replay')=='interrupted'
        assert train('replay',True)=='completed'
        replay,ledger=latest(root/'replay')
        assert ledger['reserved_tokens']==768 and replay['trained_tokens']==512
        assert replay['history'][-1]['trained_tokens']==512
        assert replay['offset']==512 and replay['step']==2
        # Scale the two intermediate production review milestones down to two
        # tiny updates. Synthetic losses isolate the stop/resume transaction.
        original_ceil = base_train.math.ceil
        def small_milestone(value):
            if value == 1_000_000/256: return 1
            if value == 5_000_000/256: return 2
            return original_ceil(value)
        def increasing_loss(model, corpus, check):
            check()
            return [1+check.__self__.ledger['trained_tokens']/256]*128
        interrupt_diagnostics = [True]
        def diagnostic_interrupt(model, tokenizer, spec, check, **kwargs):
            if check.__self__.ledger['trained_tokens']==256 and interrupt_diagnostics[0]:
                interrupt_diagnostics[0]=False
                raise KeyboardInterrupt('test interruption before diagnostic completion')
            return dict(pair_accuracy=0.,pairs=[],completions=[])
        with patch.object(base_train.math,'ceil',small_milestone), \
             patch.object(base_train,'document_losses',increasing_loss), \
             patch.object(base_train,'language_diagnostics',diagnostic_interrupt):
            assert train('diagnostic-pause')=='interrupted'
            partial,_=latest(root/'diagnostic-pause')
            assert partial['trained_tokens']==256 and partial['bad_windows']==0
            assert len(partial['history'])==1 and partial['best']['trained_tokens']==0
            assert train('diagnostic-pause',True)=='diverged'
            restored,ledger=latest(root/'diagnostic-pause')
            assert restored['trained_tokens']==512 and ledger['reserved_tokens']==512
            assert restored['bad_windows']==2 and len(restored['history'])==3
            TestCampaign.interrupt='milestone-save'
            assert train('confirmation-pause')=='interrupted'
            pending,_=latest(root/'confirmation-pause')
            assert pending['bad_windows']==2 and pending['trained_tokens']==512
            assert train('confirmation-pause',True)=='diverged'
            confirmed,ledger=latest(root/'confirmation-pause')
            assert confirmed['trained_tokens']==512 and ledger['reserved_tokens']==512
        # Freeze checks reject altered code before any campaign is created.
        invalid=dict(spec,code_sha256={'base_train.py':'0'*64})
        spec_path.write_text(json.dumps(invalid))
        try: train('bad-code')
        except ValueError as error: assert 'frozen code changed' in str(error)
        else: raise AssertionError('wrong code digest accepted')
        assert not (root/'bad-code').exists()
        spec_path.write_text(json.dumps(spec))
        # Identical alternatives must fail both members, including correct index 0.
        model=GPT2(cfg).eval()
        tied=dict(prefixes=[],pairs=[dict(id='tie',choices=[' x',' x'],members=[dict(prefix='A',correct=0),dict(prefix='B',correct=1)])])
        result=base_train.language_diagnostics(model,Tokenizer(),tied,lambda:None,completions=False)
        assert not any(m['correct'] for m in result['pairs'][0]['members'])
    print('PASS CPU train/resume exact model+optimizer parity; replay-budget endpoint/cursor; strict likelihood ties; milestone interruption atomicity; pending divergence resume; frozen code')

if __name__=='__main__':run()
