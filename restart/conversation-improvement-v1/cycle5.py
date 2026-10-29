"""Matched curriculum with fresh optimizer; cycle 1 is immutable."""
import campaign as c
import numpy as np,time,json,gc
s=c.s;ROOT=c.ROOT
import torch
PARENT=s.PROJECT/s.read(ROOT/'cycle4-result.json')['selected']['checkpoint']
parent=torch.load(PARENT,map_location='cpu',weights_only=False)
base_updates=parent['cumulative_sft_updates'];base_targets=parent['cumulative_sft_targets'];base_replay=parent['cumulative_foundation_replay_targets'];parent_sha=s.sha(PARENT)
del parent
old_snapshot=s.snapshot
def snapshot(e,meter):
    state=old_snapshot(e,meter)
    state.update(parent_checkpoint_sha256=parent_sha,cumulative_sft_updates=base_updates+e.bridge_cursor,cumulative_sft_targets=base_targets+e.bridge_sft,cumulative_foundation_replay_targets=base_replay+e.bridge_replay)
    return state
s.snapshot=snapshot
original_groups=c.repair.run.groups_at
def groups_at(i,arm):
    groups=original_groups(i,arm)
    data=s.read(s.PRIVATE/'original-rehearsal.json');indices=s.read(s.PRIVATE/'cycle3-rehearsal-schedule.json')[i]
    return [('rehearsal',.25,[data[j] for j in indices])]+groups[1:]
from sentencepiece import SentencePieceProcessor

def main():
    assert not (ROOT/'cycle5-started.json').exists()
    s.assert_frozen();s.save(ROOT/'cycle5-started.json',dict(started=time.time()))
    meter=c.Meter('cycle5')
    try:
        replay=np.load(s.PRIVATE/'replay.npy').astype(np.int32);sp=SentencePieceProcessor(model_file=str(s.serializer.TOK));hist={'control':[],'teacher':[]}
        for offset in range(0,400,50):
            for arm in ['control','teacher']:
                path=s.PROJECT/hist[arm][-1]['checkpoint'] if hist[arm] else PARENT
                e,common=s.load(path,mode='resume' if hist[arm] else 'fresh',cursor=None if hist[arm] else 0);assert e.bridge_cursor==offset
                _,gfn=s.serializer.loss_functions(e)
                for i in range(offset,offset+50):
                    stats=s.update(e,common,gfn,groups_at(i,arm),replay[i],2e-5,meter)
                    with (ROOT/('cycle5-'+arm+'-updates.jsonl')).open('a') as f:f.write(json.dumps(stats)+'\n')
                label='cycle5-'+arm+'-'+str(offset+50);path=s.checkpoint(e,meter,label)
                nll=s.foundation(e,meter);ret=s.generate(e,common,c.repair.run.bank('retention'),sp,16,meter,label+'-retention',legacy=True)
                row=dict(arm=arm,step=offset+50,narrative_nll=nll,retention=ret,checkpoint=str(path.relative_to(s.PROJECT)),sha256=s.sha(path));hist[arm].append(row);s.save(ROOT/'cycle5-history.json',hist);print(json.dumps(row),flush=True)
                assert nll<=s.ORIGINAL_NLL*1.05 and ret['content']>=72,'CYCLE5_PRESERVATION_GUARD'
                if (offset+50)%200==0:
                    row['development']=s.generate(e,common,c.repair.run.bank('development'),sp,48,meter,label+'-development')
                    row['secondary']=s.generate(e,common,c.repair.run.bank('secondary'),sp,48,meter,label+'-secondary')
                    s.save(ROOT/'cycle5-history.json',hist)
                del e,common,gfn;gc.collect()
        s.save(ROOT/'cycle5-result.json',dict(status='COMPLETED',manual_review_required=True));s.assert_frozen()
    except BaseException as ex:
        s.save(ROOT/'cycle5-stop.json',dict(reason=str(ex),type=type(ex).__name__,updates=meter.data['updates']));raise
    finally:meter.close()
if __name__=='__main__':main()
