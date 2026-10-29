import campaign as c
import numpy as np,time,json
s=c.s;ROOT=c.ROOT
from sentencepiece import SentencePieceProcessor
assert not (ROOT/'cycle4-started.json').exists()
s.assert_frozen();s.save(ROOT/'cycle4-started.json',dict(started=time.time()));meter=c.Meter('cycle4')
try:
    rows=s.read(s.PRIVATE/'original-rehearsal.json');order=[j for b in s.read(s.PRIVATE/'cycle3-rehearsal-schedule.json')[:192] for j in b];assert len(set(order))==384
    replay=np.load(s.PRIVATE/'replay.npy').astype(np.int32);sp=SentencePieceProcessor(model_file=str(s.serializer.TOK));e,common=s.load(mode='fresh');_,gfn=s.serializer.loss_functions(e);hist=[]
    for i in range(200):
        chosen=[rows[order[(8*i+j)%384]] for j in range(8)]
        stats=s.update(e,common,gfn,[('original_rehearsal',.5,chosen)],replay[i],2e-5,meter)
        with (ROOT/'cycle4-updates.jsonl').open('a') as f:f.write(json.dumps(stats)+'\n')
        if (i+1)%50:continue
        label='cycle4-'+str(i+1);path=s.checkpoint(e,meter,label);nll=s.foundation(e,meter);ret=s.generate(e,common,c.repair.run.bank('retention'),sp,16,meter,label+'-retention',legacy=True)
        row=dict(step=i+1,narrative_nll=nll,retention=ret,checkpoint=str(path.relative_to(s.PROJECT)),sha256=s.sha(path));hist.append(row);s.save(ROOT/'cycle4-history.json',hist);print(json.dumps(row),flush=True)
        assert nll<=s.ORIGINAL_NLL*1.05 and ret['content']>=72,'CYCLE4_PRESERVATION_GUARD'
        if ret['strict']>=77 and ret['content']>=77:
            row['development']=s.generate(e,common,c.repair.run.bank('development'),sp,48,meter,label+'-development')
            row['secondary']=s.generate(e,common,c.repair.run.bank('secondary'),sp,48,meter,label+'-secondary')
            s.save(ROOT/'cycle4-history.json',hist);s.save(ROOT/'cycle4-result.json',dict(status='PASS',selected=row,not_conversation_acceptance=True));break
    else:s.save(ROOT/'cycle4-result.json',dict(status='TARGET_NOT_MET',history=hist))
except BaseException as ex:
    s.save(ROOT/'cycle4-stop.json',dict(reason=str(ex),type=type(ex).__name__,updates=meter.data['updates']));raise
finally:meter.close()
