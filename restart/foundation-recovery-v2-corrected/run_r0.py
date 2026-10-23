"""Single serialized model-executing R0 attempt under independent watchdog."""
import sys,time
from common import *
from supervise import supervise

def main():
 phase='R0';check(phase);freeze_check(phase);assert read(ROOT/phase/'cpu-preflight.json')['status']=='PASS'
 marker=ROOT/phase/'attempt.json';assert not marker.exists(),'NO_RETRY'
 save(marker,dict(phase=phase,started_epoch=time.time(),one_model_executing_attempt=True,training_updates=0))
 commands=[]
 for c in read(ROOT/'plan.json')['source_candidates']:
  for backend in ['mlx','fp32']:commands.append([str(PYTHON),str(ROOT/'evaluate.py'),phase,backend,c['id']])
 supervise(phase,commands,'evaluation')
 parity=[]
 for c in read(ROOT/'plan.json')['source_candidates']:
  out=ROOT/phase/c['id'];a=read(out/'summary.json')['validation_nll'];b=read(out/'fp32.json')['validation_nll'];assert abs(a-b)<=.02,'FP32_PARITY'
  parity.append(dict(id=c['id'],BF16_NLL=a,FP32_NLL=b,absolute_difference=abs(a-b)))
 save(ROOT/phase/'computation.json',dict(status='PASS',training_updates=0,positions=Meter(phase).total(),parity=parity,epoch=time.time()))
 print(__import__('json').dumps(dict(event='R0_computation_complete',positions=Meter(phase).total(),parity=parity)),flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:
  if not (ROOT/'STOP.json').exists():save(ROOT/'STOP.json',dict(phase='R0',reason=type(e).__name__+': '+str(e),epoch=time.time(),training_updates=0))
  raise
