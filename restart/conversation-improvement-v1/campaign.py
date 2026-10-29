"""Shared cumulative ledger and deterministic engine for an authorized campaign."""
from pathlib import Path
import sys,time,json
import numpy as np
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'resume-repair-v1'))
import validate as repair
s=repair.s;s.ROOT=ROOT;s.PRIVATE=ROOT/'private'
from sentencepiece import SentencePieceProcessor
class Meter(s.Meter):
    def reserve(self,n,kind,updates=0,sft=0,narrative=0):
        self.check()
        limits=dict(positions=50000000,updates=6000,sft_targets=1000000,narrative_targets=12500000)
        charges=dict(positions=int(n),updates=updates,sft_targets=sft,narrative_targets=narrative)
        for k,v in charges.items():assert self.data[k]+v<=limits[k],'CAMPAIGN_CAP_'+k
        if self.phase!='final':assert self.data['positions']+n<=40000000,'FINAL_RESERVATION'
        for k,v in charges.items():self.data[k]+=v
        self.data['reservations'].append(dict(phase=self.phase,kind=kind,**charges));self.flush()
s.Meter=Meter

def fit_duration():
    assert not (ROOT/'duration-started.json').exists()
    s.assert_frozen();s.save(ROOT/'duration-started.json',dict(started=time.time()))
    meter=Meter('duration')
    try:
        sp=SentencePieceProcessor(model_file=str(s.serializer.TOK));rows=s.read(s.PRIVATE/'fit.json');schedule=s.read(s.PRIVATE/'schedule.json')['fit'];replay=np.load(s.PRIVATE/'replay.npy').astype(np.int32)
        source=s.PROJECT/'restart/eos-loss-ablation-v2/private/control-200.pt'
        e,c=s.load(source);assert e.bridge_cursor==200 and e.base_step==200
        _,gfn=s.serializer.loss_functions(e);history=[]
        for i in range(200,1000):
            stats=s.update(e,c,gfn,[('fit',.5,[rows[k] for k in schedule[i%len(schedule)]])],replay[i%len(replay)],2e-5,meter)
            with (ROOT/'duration-updates.jsonl').open('a') as h:h.write(json.dumps(stats)+'\n')
            if (i+1)%100:continue
            path=s.checkpoint(e,meter,'duration-'+str(i+1));nll=s.foundation(e,meter);metrics=s.generate(e,c,rows,sp,16,meter,'duration-'+str(i+1))
            row=dict(step=i+1,narrative_nll=nll,fit=metrics,checkpoint=str(path.relative_to(s.PROJECT)),sha256=s.sha(path));history.append(row);s.save(ROOT/'duration-history.json',history);print(json.dumps(row),flush=True)
            assert nll<=s.ORIGINAL_NLL*1.05,'DURATION_NARRATIVE_GUARD'
            if all(metrics['families'][f]['strict']>=15 for f in ['full_name','printed_time']):
                s.save(ROOT/'duration-result.json',dict(status='PASS',history=history,sacrificial=True,main_source='original B'));return
        s.save(ROOT/'duration-result.json',dict(status='FIT_GATE_FAILED',history=history))
    except BaseException as ex:
        s.save(ROOT/'duration-stop.json',dict(reason=str(ex),type=type(ex).__name__,updates=meter.data['updates']));raise
    finally:meter.close()
if __name__=='__main__':fit_duration()
