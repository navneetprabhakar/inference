"""Fresh bounded engineering validation; never edits the stopped experiment."""
from pathlib import Path
import sys,json,time,gc,hashlib
import numpy as np
ROOT=Path(__file__).resolve().parent
OLD=ROOT.parent/'teacher-bridge-execution-v1'
sys.path.insert(0,str(OLD))
import support as s
import run
from diagnose_resume import compute
from diagnose_repeat import differences
sys.path.insert(0,str(ROOT))
from probe import lookup
import mlx.nn as nn
import torch

# Embedding lookup changes only its backward accumulation. Tied output projection
# continues to use Embedding.as_linear and the same learned weight tensor.
nn.Embedding.__call__=lambda self,ids:lookup(self.weight,ids)
s.ROOT=ROOT;s.PRIVATE=ROOT/'private'
original_load=s.load
def load(*args,**kwargs):
    e,c=original_load(*args,**kwargs)
    # Match the engine's stable post-update ordering before the first gradient.
    e.params={k:e.params[k] for k in e.matrix+e.norm}
    return e,c
s.load=load
class Meter(s.Meter):
    def check(self):
        super().check()
        assert self.data['model_seconds']+time.time()-self.start<600,'REPAIR_TIME_CAP'
    def reserve(self,n,kind,updates=0,sft=0,narrative=0):
        assert self.data['positions']+n<=1000000,'REPAIR_POSITION_CAP'
        assert self.data['updates']+updates<=12,'REPAIR_UPDATE_CAP'
        super().reserve(n,kind,updates,sft,narrative)

def main():
    assert not (ROOT/'ledger.json').exists(),'No implicit retry'
    s.assert_frozen();meter=Meter('repair')
    try:
        meter.reserve(12288,'isolated-lookup-probe-already-executed')
        meter.data['model_seconds']+=sum(x['seconds'] for x in s.read(ROOT/'probe.json').values())
        replay=np.load(s.PRIVATE/'replay.npy').astype(np.int32)
        e,c=s.load();run.numerical(e,meter,replay)
        a,sa=compute(e,run.groups_at(0,'teacher'),replay[0],meter,list(e.params))
        b,sb=compute(e,run.groups_at(0,'teacher'),replay[0],meter,list(e.params))
        diff=differences(a,b);s.save(ROOT/'model-repeat.json',dict(differences=diff,first=sa,second=sb))
        assert not diff,'FULL_MODEL_REPEAT_FAILED'
        del e,c,a,b;gc.collect()
        # Three updates per trajectory; both endpoint states persisted before assertion.
        e,c=s.load();_,gfn=s.serializer.loss_functions(e)
        for i in range(3):s.update(e,c,gfn,run.groups_at(i,'teacher'),replay[i],2e-5,meter)
        path_a=s.checkpoint(e,meter,'uninterrupted-step3');del e,c,gfn;gc.collect()
        e,c=s.load();_,gfn=s.serializer.loss_functions(e)
        s.update(e,c,gfn,run.groups_at(0,'teacher'),replay[0],2e-5,meter)
        path=s.checkpoint(e,meter,'resume-step1');before=s.snapshot(e,meter)
        del e,c,gfn;gc.collect()
        e,c=s.load(path);s.exact_state(before,s.snapshot(e,meter),metadata=True)
        _,gfn=s.serializer.loss_functions(e)
        for i in range(1,3):s.update(e,c,gfn,run.groups_at(i,'teacher'),replay[i],2e-5,meter)
        path_b=s.checkpoint(e,meter,'resumed-step3')
        a=torch.load(path_a,weights_only=False);b=torch.load(path_b,weights_only=False)
        s.exact_state(a,b)
        del e,c,gfn,a,b,before;gc.collect()
        e,c=s.load(mode='fresh');_,gfn=s.serializer.loss_functions(e)
        assert e.base_step==0
        for opt,names in [(e.om,e.matrix),(e.on,e.norm)]:
            assert int(opt.state['step'])==0
            assert all(not bool(e.mx.any(opt.state[k][f])) for k in names for f in ['m','v'])
        for i in range(2):s.update(e,c,gfn,[('fit',.5,run.bank('fit')[i*8:i*8+8])],replay[i],2e-5*(i+1)/5,meter)
        state=s.snapshot(e,meter);assert state['optimizer_step']==2 and state['effective_learning_rate']==8e-6
        s.checkpoint(e,meter,'fresh-step2')
        s.save(ROOT/'result.json',dict(status='PASS',isolated_gradient_reference=True,full_model_repeat_exact=True,independent_numerical='PASS',exact_save_reload=True,three_step_trajectory_exact=True,fresh_optimizer_check=True,updates=meter.data['updates'],promoted=False))
        s.assert_frozen()
    except Exception as exc:
        s.save(ROOT/'STOP.json',dict(status='FAIL_STOP',reason=str(exc),type=type(exc).__name__,updates=meter.data['updates']))
        raise
    finally:meter.close()
if __name__=='__main__':main()
