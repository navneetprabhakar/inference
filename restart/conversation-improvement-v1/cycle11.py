import adapter9 as a
from journal_meter import Meter
from sentencepiece import SentencePieceProcessor
import json,torch
import campaign as c
s=a.s;ROOT=s.ROOT
def train():
 assert s.read(ROOT/'cycle9-preflight.json')['status']=='PASS'
 assert not (ROOT/'cycle11-started.json').exists();s.assert_frozen();s.save(ROOT/'cycle11-started.json',dict(status='STARTED'));meter=Meter('cycle11')
 try:
  m=a.Adapter();saved=torch.load(s.PRIVATE/'cycle10-600.pt',weights_only=False);m.restore(saved);a.equal(saved,m.state(meter));d=a.data();ground=s.read(s.PRIVATE/'grounding.json');gs=s.read(s.PRIVATE/'cycle10-grounding-schedule.json');sp=SentencePieceProcessor(model_file=str(s.serializer.TOK));hist=[]
  for i in range(1000):
   pick=slice(0,3) if i%2==0 else slice(3,6)
   groups=[a.groups(d,i)[0],('grounding',.10,[ground[j] for j in gs[i][pick]]),('conversation',.15,a.groups(d,i)[1][2][pick])]
   stats=m.update(groups,d[3][i%len(d[3])],meter)
   with (ROOT/'cycle11-updates.jsonl').open('a') as f:f.write(json.dumps(stats)+'\n')
   if (i+1)%100:continue
   label='cycle11-'+str(i+1);p=m.save(meter,label);nll=s.foundation(m.e,meter);ret=s.generate(m.e,m.common,c.repair.run.bank('retention'),sp,16,meter,label+'-retention',legacy=True)
   row=dict(step=i+1,narrative_nll=nll,retention=ret,checkpoint=str(p.relative_to(s.PROJECT)),sha256=s.sha(p));hist.append(row);s.save(ROOT/'cycle11-history.json',hist);print(json.dumps(row),flush=True)
   assert nll<=s.ORIGINAL_NLL*1.05,'CYCLE9_NARRATIVE_GUARD'
   if (i+1)%200==0:
    row['development']=s.generate(m.e,m.common,c.repair.run.bank('development'),sp,48,meter,label+'-development');s.save(ROOT/'cycle11-history.json',hist)
  s.save(ROOT/'cycle11-result.json',dict(status='COMPLETED',manual_review_required=True))
 except BaseException as ex:s.save(ROOT/'cycle11-stop.json',dict(reason=str(ex),type=type(ex).__name__,updates=meter.data['updates']));raise
 finally:meter.close()

if __name__=="__main__":train()
