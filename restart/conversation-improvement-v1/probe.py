"""Read-only natural-dialogue fit/transfer probe; shared campaign accounting."""
import campaign as c
import sys,json,time,gc
s=c.s;ROOT=c.ROOT
from sentencepiece import SentencePieceProcessor
assert s.read(ROOT/'cycle6-result.json')['status']=='COMPLETED'
assert not (ROOT/'probe-started.json').exists()
for path,expected in s.read(ROOT/'probe-freeze.json').items():assert s.sha(path)==expected
s.save(ROOT/'probe-started.json',dict(started=time.time()));meter=c.Meter('natural-probe')
try:
    sp=SentencePieceProcessor(model_file=str(s.serializer.TOK));summary={}
    for name,path in [('B',s.SOURCE),('teacher400',s.PROJECT/s.read(ROOT/'cycle6-history.json')['teacher'][-1]['checkpoint'])]:
        e,common=s.load(path);summary[name]={}
        for bank in ['seen','unused']:
            summary[name][bank]=s.generate(e,common,s.read(s.PRIVATE/('probe-'+bank+'.json')),sp,48,meter,'probe-'+name+'-'+bank)
        del e,common;gc.collect()
    s.save(ROOT/'probe-automatic.json',dict(summary=summary,manual_review_required=True));print(json.dumps(summary),flush=True)
finally:meter.close()
