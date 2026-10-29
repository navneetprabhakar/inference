import json,sys
from pathlib import Path
P=Path(__file__).resolve().parent
from metrics import score,summarize,select_lr
from inputs import TinyInputs
rows=json.loads((P/'private/fit.json').read_text());dev=json.loads((P/'private/transfer.json').read_text());inp=TinyInputs();totals={};checks=0
for family in ['name','time']:
 count=dict(positions=0,assistant=0,narrative=0)
 for step in range(128):
  (x,y,m),replay=inp.batch(family,step,.5);assert x.shape==y.shape==m.shape and x.shape[0]==4;assert replay.shape==(8,257);count['positions']+=x.size;count['assistant']+=int(m.sum());count['narrative']+=replay[:,:-1].size;checks+=2
 totals[family]=count
for rs in [rows,dev]:
 good=[dict(id=r['id'],response=r['value'],eos=True) for r in rs];assert all(c['passes'] for c in summarize(rs,good).values());checks+=1
 bad=[{**o,'response':'WRONG'} for o in good];assert not any(c['passes'] for c in summarize(rs,bad).values());checks+=1
 unterminated=[{**o,'eos':False} for o in good];assert not any(c['passes'] for c in summarize(rs,unterminated).values());checks+=1
a=[dict(id=r['id'],response=r['value'],eos=True) for r in dev];a[0]['response']='WRONG';assert summarize(dev,a)['name|recombination|simple']['passes'];checks+=1
# One changed paired member invalidates strict fit; same answer for both is counted as invariant failure.
a=[dict(id=r['id'],response=r['value'],eos=True) for r in rows];a[1]['response']=a[0]['response'];cells=summarize(rows,a);assert cells['name|fit|simple']['both_correct']==7 and cells['name|fit|simple']['unchanged_answer']==1 and not cells['name|fit|simple']['passes'];checks+=3
assert not score('03:07','3:07',True)['complete'];assert not score('Alicia Abbott','Alicia',True)['complete'];checks+=2
assert select_lr([dict(lr=lr,family=f,loss=1.) for lr in [.0001,.0005] for f in ['name','time']],dict(name=2.,time=2.))==.0001;checks+=1
budget=json.loads((P/'budget.json').read_text());assert 2*sum(r['assistant'] for r in totals.values())==budget['new_assistant_target_cap'];assert 2*sum(r['narrative'] for r in totals.values())==budget['new_narrative_target_cap'];checks+=2
out=dict(status='PASS',assertions=checks,actual_batches_checked=256,totals_single_arm=totals,scorer_false_positive_tests=True,common_lr_tie_break_checked=True,model_loaded=False,optimizer_updates=0)
(P/'cpu-verification.json').write_text(json.dumps(out,indent=2)+'\n');print(out)
