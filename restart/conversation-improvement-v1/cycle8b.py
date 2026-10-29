"""Conversation-focused allocation, fixed duration and unchanged candidate gates."""
import campaign as c
import numpy as np,time,json,torch,gc
s=c.s;ROOT=c.ROOT
from journal_meter import Meter
c.Meter=Meter;s.Meter=Meter
from sentencepiece import SentencePieceProcessor
PARENT=s.PROJECT/'restart/foundation-resolution-v1/B/checkpoint.pt'
parent=torch.load(PARENT,map_location='cpu',weights_only=False)
base_updates=0;base_targets=0;base_replay=0;foundation_source_step=parent['optimizer_step'];parent_sha=s.sha(PARENT);del parent
old_snapshot=s.snapshot
def snapshot(e,meter):
    state=old_snapshot(e,meter);state.update(foundation_source_optimizer_step=foundation_source_step,parent_checkpoint_sha256=parent_sha,cumulative_sft_updates=base_updates+e.bridge_cursor,cumulative_sft_targets=base_targets+e.bridge_sft,cumulative_foundation_replay_targets=base_replay+e.bridge_replay);return state
s.snapshot=snapshot
assert not (ROOT/'cycle8b-started.json').exists()
s.assert_frozen();s.save(ROOT/'cycle8b-started.json',dict(started=time.time()));meter=c.Meter('cycle8b')
try:
    teacher=s.read(s.PRIVATE/'teacher.json');old=s.read(s.PRIVATE/'original-rehearsal.json');schedule=s.read(s.PRIVATE/'cycle7-schedule.json');replay=np.load(s.PRIVATE/'replay.npy').astype(np.int32);sp=SentencePieceProcessor(model_file=str(s.serializer.TOK))
    START=ROOT/'private/cycle8-400.pt'
    e,common=s.load(START,mode='resume');assert e.bridge_cursor==400
    s.exact_state(torch.load(START,map_location='cpu',weights_only=False),s.snapshot(e,meter))
    _,gfn=s.serializer.loss_functions(e);hist=s.read(ROOT/'cycle8-history.json')
    # Finish only incomplete400-step evaluations; duplicate work stays charged.
    def metrics_for_existing(path):
        rs=s.read(path)
        return dict(turns=len(rs),strict=sum(x['strict'] for x in rs),content=sum(x['content'] for x in rs),eos=sum(x['eos'] for x in rs),overflows=sum(x['overflow'] for x in rs),families={f:dict(turns=sum(x['family']==f for x in rs),strict=sum(x['strict'] for x in rs if x['family']==f)) for f in sorted({x['family'] for x in rs})})
    for name,bank in [('development',c.repair.run.bank('development')),('secondary',c.repair.run.bank('secondary')),('seen',s.read(s.PRIVATE/'probe-seen.json'))]:
        path=s.PRIVATE/('cycle8-400-'+name+'-responses.json')
        hist[-1]['seen_dialogue' if name=='seen' else name]=metrics_for_existing(path) if path.exists() else s.generate(e,common,bank,sp,48,meter,'cycle8-400-'+name)
    s.save(ROOT/'cycle8-history.json',hist)
    for i in range(400,1600):
        groups=[('rehearsal',.25,[old[j] for j in schedule[i]['rehearsal']]),('conversation',.25,[teacher[j] for j in schedule[i]['teacher']])]
        stats=s.update(e,common,gfn,groups,replay[i%len(replay)],2e-5,meter)
        with (ROOT/'cycle8-updates.jsonl').open('a') as f:f.write(json.dumps(stats)+'\n')
        if (i+1)%100:continue
        label='cycle8-'+str(i+1);path=s.checkpoint(e,meter,label);nll=s.foundation(e,meter);ret=s.generate(e,common,c.repair.run.bank('retention'),sp,16,meter,label+'-retention',legacy=True)
        row=dict(step=i+1,narrative_nll=nll,retention=ret,checkpoint=str(path.relative_to(s.PROJECT)),sha256=s.sha(path),retention_eligible=ret['content']>=72 and ret['strict']>=73);hist.append(row);s.save(ROOT/'cycle8-history.json',hist);print(json.dumps(row),flush=True)
        assert nll<=s.ORIGINAL_NLL*1.05,'CYCLE8_NARRATIVE_GUARD'
        if i+1 in [200,400,800,1200,1600]:
            row['development']=s.generate(e,common,c.repair.run.bank('development'),sp,48,meter,label+'-development')
            row['secondary']=s.generate(e,common,c.repair.run.bank('secondary'),sp,48,meter,label+'-secondary')
            row['seen_dialogue']=s.generate(e,common,s.read(s.PRIVATE/'probe-seen.json'),sp,48,meter,label+'-seen')
            s.save(ROOT/'cycle8-history.json',hist)
        # Keep evaluation checkpoints and latest only; preserve hashes/metrics.
        for previous in hist[:-1]:
            if previous['step'] in [200,400,800,1200,1600]:continue
            pp=s.PROJECT/previous['checkpoint']
            if pp.exists():
                assert s.sha(pp)==previous['sha256'];pp.unlink()
                with (ROOT/'cycle8-pruned.jsonl').open('a') as f:f.write(json.dumps(dict(path=str(pp),sha256=previous['sha256'],reason='superseded non-selection campaign intermediate'))+'\n')
    s.save(ROOT/'cycle8b-result.json',dict(status='COMPLETED',manual_review_required=True));s.assert_frozen()
except BaseException as ex:
    s.save(ROOT/'cycle8b-stop.json',dict(reason=str(ex),type=type(ex).__name__,updates=meter.data['updates']));raise
finally:meter.close()
