"""Latency only on native training-token prefixes; no development scoring."""
import sys,json,time
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parent;sys.path.insert(0,str(P));from calibrate import CalibrationMeter,CAPS,verify
from runner import Backend,Inputs,atomic,read

def main():
 verify()
 if not (P/'result.json').exists() or (P/'timing.json').exists():raise RuntimeError('CALIBRATION_MUST_FINISH; NO_RERUN')
 import mlx.optimizers as optim
 def forbidden(*a,**k):raise RuntimeError('OPTIMIZER_FORBIDDEN_DURING_TIMING')
 optim.Optimizer.apply_gradients=forbidden
 meter=CalibrationMeter(P/'private/study.sqlite',CAPS,True);meter.start()
 try:b=Backend();model=b.common.bind(b.e);before=b.digest()
 finally:meter.stop()
 inputs=Inputs();tokens=np.asarray(inputs.replay[0,0],np.int32);samples=[]
 for prefix in [32,128,224]:
  for repeat in range(2):
   ids=list(map(int,tokens[:prefix]));elapsed=0;positions=0
   for i in range(32):
    meter.reserve('training-prefix-latency',len(ids));meter.start();start=time.monotonic()
    try:
     v=model(b.mx.array([ids],b.mx.int32))[0,-1,:];b.mx.eval(v);n=int(b.mx.argmax(v));b.e.memory()
    finally:meter.stop()
    elapsed+=time.monotonic()-start;positions+=len(ids);ids.append(n)
   samples.append({'prefix':prefix,'repeat':repeat,'forwards':32,'positions':positions,'seconds':elapsed,'seconds_per_forward':elapsed/32})
 # Actual heldout-shaped validation latency using replay training rows, not validation labels.
 narrative=[]
 for i in range(4):
  a=np.asarray(inputs.replay[i],np.int32);batch=(a[:,:-1],a[:,1:],np.ones((8,256),np.float32));meter.reserve('training-nll-latency',2048);meter.start();start=time.monotonic()
  try:b.forward(batch)
  finally:meter.stop()
  narrative.append(time.monotonic()-start)
 assert before==b.digest()
 atomic(P/'timing.json',json.dumps({'samples':samples,'narrative_batch_seconds':narrative,'parameters_unchanged':True,'extra_updates':0,'cumulative_charges':meter.totals(),'cumulative_seconds':meter.seconds(),'limits':'Training-prefix synthetic latency sample; includes no development scores, not an exact runtime guarantee.'},indent=2).encode())
if __name__=='__main__':main()
