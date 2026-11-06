"""Essential CPU regressions; no MPS ownership or training."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import torch
from base_run_control import Campaign, CampaignStop
from guards import ResourceStop

class Clock:
    def __init__(self): self.now = 1000.
    def time(self): return self.now

class Guard:
    def __init__(self, path, seconds, resume=False):
        self.path = path
        if not resume: path.mkdir()
    def check(self):
        if (self.path/'STOP').exists(): raise ResourceStop('explicit STOP')
    def close(self): pass

IDENTITY = dict(initialization='random',seed=7,model={'width':2},tokenizer='pinned',corpus='pinned',scheduler={'tokens':32})

def run():
    clock = Clock()
    with TemporaryDirectory() as directory, patch('base_run_control.time.monotonic',clock.time), patch('base_run_control.time.time',clock.time):
        path=Path(directory)/'campaign'
        options=dict(token_limit=32,active_seconds=100,calendar_seconds=10000,lease_seconds=10,guard_factory=Guard)
        with Campaign(path,IDENTITY,**options) as c:
            c.save(dict(step=0,model={'x':torch.tensor([1.])},optimizer={}))
            c.reserve(8);c.commit(1,8)
            c.save(dict(step=1,model={'x':torch.tensor([2.])},optimizer={}))
            clock.now+=3
            c.finish('paused-lease')
        clock.now+=500
        c=Campaign(path,IDENTITY,resume=True,**options)
        assert c.snapshot()['active_seconds']==3
        assert c.load()['step']==1
        c.reserve(8)  # Simulate death during an update; no clean close.
        c.guard.close();c.closed=True
        clock.now+=500
        with Campaign(path,IDENTITY,resume=True,**options) as c:
            assert c.snapshot()['active_seconds']==13
            assert c.load()['step']==1
            assert c.snapshot()['reserved_tokens']==16
            c.reserve(8);c.commit(2,16)
            c.save(dict(step=2,model={'x':torch.tensor([3.])},optimizer={}))
            c.reserve(8);c.commit(3,24)
            try:c.reserve(8)
            except CampaignStop as e:assert 'token ceiling' in str(e)
            else:raise AssertionError('replay escaped token ceiling')
            c.finish('paused-resource')
        with Campaign(path,IDENTITY,resume=True,**options) as c:
            c.load();clock.now+=10
            try:c.check()
            except CampaignStop as e:assert e.state=='paused-lease'
            else:raise AssertionError('lease ignored')
            c.finish('paused-lease')
        with Campaign(path,IDENTITY,resume=True,**options) as c:
            c.load();(path/'STOP').touch()
            try:c.check()
            except CampaignStop as e:assert 'STOP' in str(e)
            else:raise AssertionError('STOP ignored')
            c.finish('paused-resource')
        (path/'STOP').unlink()
        try:Campaign(path,{**IDENTITY,'seed':8},resume=True,**options)
        except ValueError:pass
        else:raise AssertionError('identity changed')
        receipt=json.loads((path/'campaign.json').read_bytes());receipt['reserved_tokens']=0
        (path/'campaign.json').write_text(json.dumps(receipt))
        try:Campaign(path,IDENTITY,resume=True,**options)
        except ValueError:pass
        else:raise AssertionError('unsigned budget rewind allowed')
    with TemporaryDirectory() as directory:
        import checkpoint
        path = Path(directory)/'gap'
        with Campaign(path, IDENTITY, guard_factory=Guard) as c:
            c.save(dict(step=0, model={'x':torch.tensor([1.])}, optimizer={}))
            pinned = json.loads((path/'latest.json').read_bytes())[0]
            c.reserve(8); c.commit(1, 8)
            checkpoint.save(path, dict(step=1, model={'x':torch.tensor([2.])}, optimizer={},
                                       identity=c.identity, campaign_id=c.ledger['campaign_id'],
                                       spec_sha256=c.spec_sha256, trained_tokens=8))
            orphan = json.loads((path/'latest.json').read_bytes())[0]
            c.finish('interrupted', 'simulated crash after checkpoint pointer publication')
        with Campaign(path, IDENTITY, resume=True, guard_factory=Guard) as c:
            restored = c.load()
            assert restored['step'] == 0 and c.snapshot()['reserved_tokens'] == 8
            assert json.loads((path/'latest.json').read_bytes())[0] == pinned
            c.save(dict(step=0, model=restored['model'], optimizer={}))
            assert (path/orphan['file']).exists()
            c.finish('interrupted')
    print('PASS clean pause, bounded crash charge, replay ceiling, lease, STOP, identity and ledger checksum, step-save publication gap')

if __name__=='__main__':run()
