"""Conversation-focused allocation, fixed duration and unchanged candidate gates."""
import campaign as c
import numpy as np,time,json,torch,gc
s=c.s;ROOT=c.ROOT
from sentencepiece import SentencePieceProcessor
PARENT=s.PROJECT/s.read(ROOT/'cycle4-result.json')['selected']['checkpoint']
parent=torch.load(PARENT,map_location='cpu',weights_only=False)
base_updates=parent['cumulative_sft_updates'];base_targets=parent['cumulative_sft_targets'];base_replay=parent['cumulative_foundation_replay_targets'];parent_sha=s.sha(PARENT);del parent
old_snapshot=s.snapshot
def snapshot(e,meter):
    state=old_snapshot(e,meter);state.update(parent_checkpoint_sha256=parent_sha,cumulative_sft_updates=base_updates+e.bridge_cursor,cumulative_sft_targets=base_targets+e.bridge_sft,cumulative_foundation_replay_targets=base_replay+e.bridge_replay);return state
s.snapshot=snapshot
assert not (ROOT/'cycle7-started.json').exists()
s.assert_frozen();s.save(ROOT/'cycle7-started.json',dict(started=time.time()));meter=c.Meter('cycle7')
try:
    teacher=s.read(s.PRIVATE/'teacher.json');old=s.read(s.PRIVATE/'original-rehearsal.json');schedule=s.read(s.PRIVATE/'cycle7-schedule.json');replay=np.load(s.PRIVATE/'replay.npy').astype(np.int32);sp=SentencePieceProcessor(model_file=str(s.serializer.TOK))
    e,common=s.load(PARENT,mode='fresh',cursor=0);_,gfn=s.serializer.loss_functions(e);hist=[]
    for i in range(1600):
        groups=[('rehearsal',.25,[old[j] for j in schedule[i]['rehearsal']]),('conversation',.25,[teacher[j] for j in schedule[i]['teacher']])]
        stats=s.update(e,common,gfn,groups,replay[i%len(replay)],2e-5,meter)
        with (ROOT/'cycle7-updates.jsonl').open('a') as f:f.write(json.dumps(stats)+'\n')
        if (i+1)%100:continue
        label='cycle7-'+str(i+1);path=s.checkpoint(e,meter,label);nll=s.foundation(e,meter);ret=s.generate(e,common,c.repair.run.bank('retention'),sp,16,meter,label+'-retention',legacy=True)
        row=dict(step=i+1,narrative_nll=nll,retention=ret,checkpoint=str(path.relative_to(s.PROJECT)),sha256=s.sha(path),retention_eligible=ret['content']>=72 and ret['strict']>=73);hist.append(row);s.save(ROOT/'cycle7-history.json',hist);print(json.dumps(row),flush=True)
        assert nll<=s.ORIGINAL_NLL*1.05,'CYCLE7_NARRATIVE_GUARD'
        if i+1 in [200,400,800,1200,1600]:
            row['development']=s.generate(e,common,c.repair.run.bank('development'),sp,48,meter,label+'-development')
            row['secondary']=s.generate(e,common,c.repair.run.bank('secondary'),sp,48,meter,label+'-secondary')
            row['seen_dialogue']=s.generate(e,common,s.read(s.PRIVATE/'probe-seen.json'),sp,48,meter,label+'-seen')
            s.save(ROOT/'cycle7-history.json',hist)
        # Keep evaluation checkpoints and latest only; preserve hashes/metrics.
        for previous in hist[:-1]:
            if previous['step'] in [200,400,800,1200,1600]:continue
            pp=s.PROJECT/previous['checkpoint']
            if pp.exists():
                assert s.sha(pp)==previous['sha256'];pp.unlink()
                with (ROOT/'cycle7-pruned.jsonl').open('a') as f:f.write(json.dumps(dict(path=str(pp),sha256=previous['sha256'],reason='superseded non-selection campaign intermediate'))+'\n')
    s.save(ROOT/'cycle7-result.json',dict(status='COMPLETED',manual_review_required=True));s.assert_frozen()
except BaseException as ex:
    s.save(ROOT/'cycle7-stop.json',dict(reason=str(ex),type=type(ex).__name__,updates=meter.data['updates']));raise
finally:meter.close()
