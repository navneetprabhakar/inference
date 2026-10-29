"""Bounded forward-only check. Optimizer calls are prohibited, including disposable ones."""
import json,time,sys,pickle
from runner import *
from evaluate import Evaluator

def main():
 identity=verify_manifest();path=P/'private/forward-ledger.sqlite'
 if path.exists():raise RuntimeError('NO_IMPLICIT_VERIFICATION_RERUN')
 limits=dict(positions=500000,updates=0,assistant=0,narrative=0,seconds=300)
 meter=Meter(path,limits,False);atomic(P/'forward-started.json',json.dumps({'manifest':identity,'limits':limits}).encode())
 import mlx.optimizers as optim
 def forbidden(*a,**k):raise RuntimeError('OPTIMIZER_CALL_FORBIDDEN')
 optim.Optimizer.apply_gradients=forbidden
 meter.start()
 try:backend=Backend();before=backend.digest()
 finally:meter.stop()
 inputs=Inputs();losses={}
 try:
  for w in ['canonical','diverse']:
   batch,replay=inputs.batch(w,0,.5)
   for name,b in [(w,batch),(w+'-replay',(replay[:,:-1],replay[:,1:],np.ones((8,256),np.float32)))]:
    meter.reserve('forward-loss',int(b[0].size));meter.start()
    try:losses[name]=backend.forward(b)
    finally:meter.stop()
  # Cold optimizer state and RNG round-trip, no optimizer update or gradient evaluation.
  before_state=backend.state();atomic(P/'private/cold-state.pkl',pickle.dumps(before_state,protocol=5));backend.restore(pickle.loads((P/'private/cold-state.pkl').read_bytes()))
  assert backend.digest()==before and backend.steps==0
  batch,_=inputs.batch('canonical',0,0);meter.reserve('roundtrip-forward',int(batch[0].size));meter.start()
  try:repeat=backend.forward(batch)
  finally:meter.stop()
  assert repeat==losses['canonical'],'COLD_STATE_FORWARD_MISMATCH'
  result=Evaluator(backend,meter,P/'private/baseline').packet(read(P/'private/preservation.json'),'source-preservation')
  assert backend.digest()==before
  atomic(P/'forward-result.json',json.dumps({'status':'PASS','losses':losses,'cold_state_forward_exact':True,'parameters_before':before,'parameters_after':backend.digest(),'source_preservation':result,'charges':meter.totals(),'seconds':meter.seconds(),'optimizer_calls':0,'gradients_evaluated':0,'limitations':['No post-update optimizer equivalence, gradient parity, backward timing or trained resume checked.','Source preservation is a baseline, not student conversation acceptance.']},indent=2).encode())
 except BaseException as ex:
  atomic(P/'forward-stop.json',json.dumps({'reason':str(ex),'charges':meter.totals(),'seconds':meter.seconds()}).encode());raise
 print(json.dumps(read(P/'forward-result.json'),indent=2))
if __name__=='__main__':main()
