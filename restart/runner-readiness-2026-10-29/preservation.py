"""Preservation evidence: held-out native NLL plus explicitly floor-aware behavior."""
from runner import *
from evaluate import Evaluator,preservation_delta
VALIDATION=PROJECT/'restart/foundation-stage3-v1/validation.npy'

def behavior_decision(baseline,candidate):
 delta=preservation_delta(baseline,candidate)
 if delta['floor_warning']:delta.update(passes_5pp=None,status='INCONCLUSIVE_SOURCE_FLOOR')
 else:delta['status']='PASS' if delta['passes_5pp'] else 'FAIL'
 return delta

def narrative(backend,meter):
 a=np.load(VALIDATION,mmap_mode='r');assert a.shape==(512,257)
 losses=[]
 for i in range(0,len(a),8):
  rows=np.asarray(a[i:i+8],np.int32);batch=(rows[:,:-1],rows[:,1:],np.ones((len(rows),256),np.float32))
  meter.reserve('heldout-native-nll',int(batch[0].size));meter.start()
  try:losses.append(backend.forward(batch))
  finally:meter.stop()
 return {'nll':float(np.mean(losses)),'targets':131072,'blocks':64,'batch_losses':losses,'role':'preservation proxy for native narrative distribution; not conversation quality; no automatic +5% stop'}

class PreservationEvaluator(Evaluator):
 def checkpoint(self,kind,step):
  result=super().checkpoint(kind,step);result['native_narrative']=narrative(self.backend,self.meter)
  atomic(self.out/f'{step}-summary.json',json.dumps(result,indent=2).encode());return result

def main():
 verify_manifest();meta=read(P/'preservation-inputs.json')
 if sha(VALIDATION)!=meta['validation_sha256']:raise RuntimeError('VALIDATION_CHANGED')
 if (P/'narrative-result.json').exists():raise RuntimeError('NO_IMPLICIT_RERUN')
 import mlx.optimizers as optim
 def forbidden(*a,**k):raise RuntimeError('OPTIMIZER_FORBIDDEN')
 optim.Optimizer.apply_gradients=forbidden
 meter=Meter(P/'private/forward-ledger.sqlite',dict(positions=500000,updates=0,assistant=0,narrative=0,seconds=300),False)
 meter.start()
 try:backend=Backend();before=backend.digest()
 finally:meter.stop()
 metric=narrative(backend,meter);assert backend.digest()==before
 source=read(P/'forward-result.json')['source_preservation'];decision=behavior_decision(source,source)
 atomic(P/'narrative-result.json',json.dumps({'status':'PASS','native_narrative':metric,'behavior_preservation_gate':decision,'cumulative_charges':meter.totals(),'cumulative_seconds':meter.seconds(),'optimizer_updates':0,'parameters_unchanged':True},indent=2).encode());print(metric['nll'],decision['status'])
if __name__=='__main__':main()
