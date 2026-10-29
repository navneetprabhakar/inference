import tempfile,json,sys,copy
from pathlib import Path
import numpy as np
from runner import *
from evaluate import preservation_score,preservation_delta,summarize

def main():
 count=0
 def check(v):
  nonlocal count
  assert v;count+=1
 limits=dict(positions=100000000,updates=2000,assistant=10000000,narrative=10000000,seconds=60)
 inputs=Inputs()
 for w in ['canonical','diverse']:
  for i in range(1000):
   b,r=inputs.batch(w,i,.5);check(b[0].shape==b[1].shape==b[2].shape and b[0].shape[0]==8);check(r.shape==(8,257))
   _,zero=inputs.batch(w,i,0);check(zero is None)
   for j,index in enumerate(inputs.schedule[i]):
    row=inputs.rows[w][index];n=len(row['ids'])-1;check(np.array_equal(b[0][j,:n],row['ids'][:-1]));check(np.array_equal(b[1][j,:n],row['ids'][1:]));check(np.array_equal(b[2][j,:n],row['mask'][1:]));check(not b[2][j,n:].any())
 # Per-task normalization differs from pooling targets when target counts differ.
 ce=np.array([[2.,2.],[10.,0.]]);mask=np.array([[1.,1.],[1.,0.]])
 check(np.mean((ce*mask).sum(1)/mask.sum(1))==6);check((ce*mask).sum()/mask.sum()!=6)
 class Fake:
  def __init__(self):self.steps=0;self.trace=[]
  def apply(self,b,r,c):self.steps+=1;self.trace.append((int(b[0].sum()),None if r is None else int(r.sum()),c));return {}
  def state(self):return dict(steps=self.steps,trace=self.trace.copy())
  def restore(self,d):self.steps=d['steps'];self.trace=d['trace'].copy()
 with tempfile.TemporaryDirectory() as tmp:
  path=Path(tmp);meter=Meter(path/'deny.sqlite',limits)
  try:meter.reserve('bad',1,updates=1)
  except RuntimeError:check(meter.totals()['updates']==0)
  else:raise AssertionError('Optimizer allowed')
  m=Meter(path/'run.sqlite',limits,True);f=Fake();run=Runner(f,inputs,m,'diverse',.5,'abc',path/'state')
  run.one();run.save();run.one();expected=f.state();check(m.totals()['updates']==2)
  try:run.restore()
  except RuntimeError:check(True)
  else:raise AssertionError('Ledger rewind allowed')
  run.save();g=Fake();resumed=Runner(g,inputs,m,'diverse',.5,'abc',path/'state');resumed.restore();check(g.state()==expected and resumed.cursor==2);run.one();resumed.one();check(f.trace[2]==g.trace[2])
  # Synthetic execution proves callback schedule without invoking any model/optimizer.
  m2=Meter(path/'schedule.sqlite',limits,True);r2=Runner(Fake(),inputs,m2,'canonical',0,'abc',path/'s2');seen=[];r2.run(lambda k,i:seen.append((k,i)));check(seen==[('source',0),('sentinel',250),('sentinel',500),('endpoint',1000)]);check(m2.totals()['narrative']==0)
  m3=Meter(path/'cap.sqlite',{**limits,'positions':1},True);m3.reserve('one',1)
  try:m3.reserve('two',1)
  except RuntimeError:check(m3.totals()['positions']==1)
  else:raise AssertionError('Cap exceeded')
  m3.db.close();m3=Meter(path/'cap.sqlite',{**limits,'positions':1},True);check(m3.totals()['positions']==1)
 cases=read(P/'private/preservation.json')
 for case in cases:
  for t in range(len(case['messages'])//2):
   answer=case['messages'][t*2+1]['content'];check(preservation_score(case,t,answer,True,False,False)['complete']);check(not preservation_score(case,t,'not '+answer,True,False,False)['complete']);check(not preservation_score(case,t,answer,False,False,False)['complete']);check(not preservation_score(case,t,answer,True,False,True)['complete'])
 check(preservation_delta({'total':80,'correct':60,'families':{}},{'total':80,'correct':56,'families':{}})['passes_5pp']);check(not preservation_delta({'total':80,'correct':60,'families':{}},{'total':80,'correct':55,'families':{}})['passes_5pp'])
 result={'status':'PASS','assertions':count,'optimizer_calls':0,'scope':'CPU arrays, fake backend lifecycle, accounting, serialization, preservation scorer; not actual optimizer/resume equivalence'};atomic(P/'tests.json',json.dumps(result,indent=2).encode());print(result)
if __name__=='__main__':main()
