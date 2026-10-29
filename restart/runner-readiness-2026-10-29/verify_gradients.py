"""Two backward evaluations, zero optimizer applications or parameter changes."""
from runner import *
def main():
 verify_manifest()
 if (P/'gradient-result.json').exists():raise RuntimeError('NO_IMPLICIT_RERUN')
 import mlx.optimizers as optim
 def forbidden(*a,**k):raise RuntimeError('OPTIMIZER_FORBIDDEN')
 optim.Optimizer.apply_gradients=forbidden
 meter=Meter(P/'private/forward-ledger.sqlite',dict(positions=500000,updates=0,assistant=0,narrative=0,seconds=300),False)
 meter.start()
 try:b=Backend();before=b.digest()
 finally:meter.stop()
 batch,_=Inputs().batch('diverse',0,0);values=[];times=[];digests=[];norms=[]
 for _ in range(2):
  meter.reserve('backward-only-no-application',int(batch[0].size));meter.start();start=time.monotonic()
  try:
   value,g=b.grad(b.e.params,*[b.mx.array(a) for a in batch]);b.mx.eval(value,g);b.e.memory()
   if not math.isfinite(float(value)) or not all(bool(b.mx.all(b.mx.isfinite(v))) for v in g.values()):raise RuntimeError('NONFINITE_GRADIENT')
   h=hashlib.sha256()
   for k,v in sorted(g.items()):h.update(k.encode());h.update(np.array(v).tobytes())
   digests.append(h.hexdigest());values.append(float(value));norms.append(float(b.mx.sqrt(sum(b.mx.sum(v*v) for v in g.values()))));times.append(time.monotonic()-start)
  finally:meter.stop()
 assert digests[0]==digests[1] and values[0]==values[1]
 assert b.digest()==before and b.steps==0
 atomic(P/'gradient-result.json',json.dumps({'status':'PASS','gradient_hashes':digests,'losses':values,'norms':norms,'seconds_per_backward':times,'gradient_supervision_positions':2*int(batch[2].sum()),'gradient_evaluations':2,'optimizer_applications':0,'parameters_unchanged':True,'cumulative_positions':meter.totals()['positions'],'cumulative_seconds':meter.seconds(),'limit':'Deterministic finite gradients only. No independent gradient parity or post-update resume equivalence. A single batch is not a full-run throughput benchmark.'},indent=2).encode());print(read(P/'gradient-result.json'))
if __name__=='__main__':main()
