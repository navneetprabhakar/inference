from runner import *
from preservation import behavior_decision
import tempfile

def main():
 passed=[]
 limits=dict(positions=20,updates=0,assistant=0,narrative=0,seconds=60)
 with tempfile.TemporaryDirectory() as t:
  path=Path(t)/'ledger.sqlite';m=Meter(path,limits)
  for values in [(-1,0),(1,1)]:
   try:m.reserve('invalid',values[0],updates=values[1])
   except (RuntimeError,ValueError):passed.append('invalid/unauthorized reservation rejected')
   else:raise AssertionError('Invalid reservation accepted')
  m.start()
  try:m.start()
  except RuntimeError:passed.append('nested timer rejected')
  else:raise AssertionError('Timer reset accepted')
  m.stop();m.db.close()
  try:Meter(path,{**limits,'positions':21})
  except RuntimeError:passed.append('ledger limit change rejected')
  else:raise AssertionError('Budget reset accepted')
  m=Meter(path,limits);m.db.execute('UPDATE timing SET seconds=61,active_start=NULL');m.db.commit()
  try:m.reserve('late',1)
  except RuntimeError:passed.append('time cap enforced before work')
  else:raise AssertionError('Time cap ignored')
  m.db.close()
  crash=Meter(Path(t)/'crash.sqlite',limits);crash.reserve('precrash',5);crash.db.execute('UPDATE timing SET active_start=?',(time.time()-2,));crash.db.commit();crash.db.close()
  reopened=Meter(Path(t)/'crash.sqlite',limits);assert reopened.seconds()>=2 and reopened.totals()['positions']==5;passed.append('crash reservation and elapsed time retained')
 baseline={'total':80,'correct':0,'families':{}};assert behavior_decision(baseline,baseline)['status']=='INCONCLUSIVE_SOURCE_FLOOR';passed.append('floor baseline cannot pass preservation')
 result={'status':'PASS','checks':passed,'real_optimizer_calls':0};atomic(P/'lifecycle-tests.json',json.dumps(result,indent=2).encode());print(result)
if __name__=='__main__':main()
