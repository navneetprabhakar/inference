import sys,json,pickle
from pathlib import Path
P=Path(__file__).resolve().parent;PROJECT=P.parents[1];READY=P.parent/'runner-readiness-2026-10-29';sys.path.insert(0,str(READY))
from runner import Backend,Meter,read,sha,atomic,verify_manifest
from evaluate import Evaluator

def main():
 verify_manifest();spec=read(P/'spec.json');freeze=read(P/'freeze.json')
 for f,h in freeze['files'].items():assert sha(PROJECT/f)==h,f
 if (P/'started.json').exists():raise RuntimeError('NO_IMPLICIT_RERUN')
 atomic(P/'started.json',json.dumps({'updates_allowed':0,'spec':spec}).encode());meter=Meter(P/'private/inference.sqlite',spec['limits'],False)
 import mlx.optimizers as optim
 def forbidden(*a,**k):raise RuntimeError('OPTIMIZER_FORBIDDEN')
 optim.Optimizer.apply_gradients=forbidden
 meter.start()
 try:
  b=Backend();checkpoint=pickle.loads((PROJECT/spec['checkpoint']).read_bytes());b.restore(checkpoint['state']);before=b.digest()
 finally:meter.stop()
 assert before==read(P.parent/'retained-screen-2026-10-29/result.json')['arms'][1]['endpoint_parameters']
 ev=Evaluator(b,meter,P/'private');rows=read(P/'private/probes.json');completed=0
 try:
  with (P/'private/responses.jsonl').open('x') as handle:
   for row in rows:
    text,eos,bos,overflow=ev.generate(row['messages'],32);correct=text.strip().casefold()==row['expected'].strip().casefold() and eos and not bos and not overflow
    out={k:v for k,v in row.items() if k not in ['scenario','messages']};out.update(response=text,eos=eos,bos=bos,overflow=overflow,correct=correct);handle.write(json.dumps(out)+'\n');handle.flush();completed+=1
    if completed%128==0:print(json.dumps({'completed':completed,'positions':meter.totals()['positions'],'seconds':meter.seconds()}),flush=True)
  assert b.digest()==before
  for f,h in freeze['files'].items():assert sha(PROJECT/f)==h,f
  atomic(P/'result.json',json.dumps({'status':'COMPLETED','responses':completed,'charges':meter.totals(),'seconds':meter.seconds(),'parameter_hash_before':before,'parameter_hash_after':b.digest(),'final_test_used':False},indent=2).encode())
 except BaseException as e:atomic(P/'stop.json',json.dumps({'reason':str(e),'completed':completed,'charges':meter.totals(),'seconds':meter.seconds()}).encode());raise
if __name__=='__main__':main()
