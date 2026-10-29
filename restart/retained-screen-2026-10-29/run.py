"""Approved four-arm research screen. No automatic promotion or extra updates."""
import sys,json,time,gc,sqlite3,os
from pathlib import Path
P=Path(__file__).resolve().parent;PROJECT=P.parents[1];READY=P.parent/'runner-readiness-2026-10-29';CAL=P.parent/'lr-feasibility-2026-10-29';sys.path.insert(0,str(READY))
import runner as core
import evaluate as evaluation
from runner import Backend,Inputs,Runner,Meter,read,sha,atomic
from preservation import PreservationEvaluator
CAPS=dict(positions=50000000,updates=4612,assistant=1000000,narrative=10000000,seconds=9000)
ORIGINAL_RESOURCES=core.resources

def resources():
 ORIGINAL_RESOURCES()
 roots=[P,READY,P.parent/'disposable-calibration-2026-10-29',CAL]
 size=sum(f.stat().st_size for root in roots for f in root.rglob('*') if f.is_file())
 if size>6*1024**3:raise RuntimeError('TOTAL_STUDY_ARTIFACT_CAP')
core.resources=resources;evaluation.resources=resources

def verify():
 for base,name in [(READY,'freeze.json'),(READY,'preservation-freeze.json'),(READY,'gradient-freeze.json'),(READY,'launch-freeze.json'),(CAL,'freeze.json'),(CAL,'assessment-freeze.json'),(CAL,'receipt-freeze.json'),(P,'freeze.json')]:
  for f,h in read(base/name)['files'].items():
   if sha(PROJECT/f)!=h:raise RuntimeError('FROZEN_INPUT_CHANGED:'+f)
 return sha(P/'freeze.json')

def import_calibration(meter):
 source=CAL/'private/study.sqlite';db=sqlite3.connect(f'file:{source}?mode=ro',uri=True)
 values=db.execute('SELECT SUM(positions),SUM(updates),SUM(assistant),SUM(narrative) FROM events').fetchone();seconds,active=db.execute('SELECT seconds,active_start FROM timing').fetchone();db.close()
 assert active is None
 expected=read(CAL/'assessment.json');assert dict(zip(['positions','updates','assistant','narrative'],values))==expected['cumulative_charges'];assert abs(seconds-expected['cumulative_seconds'])<1e-6
 meter.reserve('import-all-calibration-12-plus600-and-timing',int(values[0]),updates=int(values[1]),assistant=int(values[2]),narrative=int(values[3]));meter.db.execute('UPDATE timing SET seconds=? WHERE id=1',(seconds,));meter.db.commit()
 atomic(P/'carry-forward.json',json.dumps({'source':str(source.relative_to(PROJECT)),'source_sha256':sha(source),'charges':meter.totals(),'seconds':seconds,'includes_earlier12_once':True,'old_ledger_unchanged':True},indent=2).encode())

class ProgressEvaluator(PreservationEvaluator):
 def checkpoint(self,kind,step):
  print(json.dumps({'event':'evaluation-start','arm':CURRENT_ARM,'step':step,'kind':kind}),flush=True)
  result=super().checkpoint(kind,step)
  print(json.dumps({'event':'evaluation-end','arm':CURRENT_ARM,'step':step,'matrix':result['matrix'],'native_nll':result['native_narrative']['nll'],'seconds':self.meter.seconds()}),flush=True)
  return result
CURRENT_ARM=-1

def main():
 global CURRENT_ARM
 identity=verify()
 if (P/'started.json').exists():raise RuntimeError('NO_IMPLICIT_SCREEN_RESTART')
 atomic(P/'started.json',json.dumps({'authority':'User approved four-arm retained research screen with150-minute total ceiling carrying all calibration usage','limits':CAPS,'learning_rate':.0005,'automatic_promotion':False}).encode())
 meter=Meter(P/'private/study.sqlite',CAPS,True);import_calibration(meter);inputs=Inputs();source_hash=inputs.config['source_checkpoint_sha256'];completed=[]
 try:
  for i,arm in enumerate(inputs.config['arms']):
   CURRENT_ARM=i;resources();meter.start()
   try:b=Backend(.0005)
   finally:meter.stop()
   if sha(PROJECT/inputs.config['source'])!=source_hash:raise RuntimeError('SOURCE_CHANGED')
   folder=P/'private'/f'arm-{i}';r=Runner(b,inputs,meter,arm['wording'],arm['replay_coefficient'],identity,folder);ev=ProgressEvaluator(b,meter,folder/'evaluation')
   initial=b.digest();print(json.dumps({'event':'arm-start','arm':i,**arm,'source_parameters':initial}),flush=True)
   if i==0:
    baseline=ProgressEvaluator(b,meter,P/'private/source-evaluation').checkpoint('source',0);atomic(P/'source-baseline.json',json.dumps(baseline,indent=2).encode())
   else:
    assert initial==completed[0]['source_parameters'],'FRESH_SOURCE_MISMATCH'
   log=(folder/'updates.jsonl').open('x')
   try:
    for _ in range(1000):
     stats=r.one();log.write(json.dumps({'step':r.cursor,**stats})+'\n');log.flush()
     if r.cursor in [250,500,1000]:ev.checkpoint('endpoint' if r.cursor==1000 else 'sentinel',r.cursor)
     # Checkpoint I/O is charged as active time; arithmetic/data schedule unchanged.
     if r.cursor%25==0:
      meter.start()
      try:r.save()
      finally:meter.stop()
     if r.cursor%100==0:print(json.dumps({'event':'training','arm':i,'step':r.cursor,**stats,'charges':meter.totals(),'seconds':meter.seconds()}),flush=True)
   finally:log.close()
   record={'arm':i,**arm,'updates':r.cursor,'source_parameters':initial,'endpoint_parameters':b.digest(),'checkpoint_sha256':sha(folder/'checkpoint.pkl')};completed.append(record);atomic(P/'completed-arms.json',json.dumps(completed,indent=2).encode())
   del ev,r,b;gc.collect()
  assert meter.totals()['updates']==4612;verify()
  atomic(P/'result.json',json.dumps({'status':'COMPLETED','arms':completed,'charges':meter.totals(),'seconds':meter.seconds(),'automatic_promotion':False,'final_test_used':False},indent=2).encode())
 except BaseException as ex:
  atomic(P/'stop.json',json.dumps({'reason':str(ex),'type':type(ex).__name__,'arm':CURRENT_ARM,'completed_arms':len(completed),'charges':meter.totals(),'seconds':meter.seconds(),'no_implicit_retry':True},indent=2).encode());raise
if __name__=='__main__':main()
