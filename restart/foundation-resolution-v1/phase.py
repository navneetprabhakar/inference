"""Activate exactly one conditionally approved phase; never reset an existing clock."""
import sys,time
from common import *
from supervise import supervise

def activate(phase):
 assert phase in ['R1','R2'];check(phase if read(ROOT/'clock.json')['phase']==phase else read(ROOT/'clock.json')['phase'],reserve=False)
 assert not (ROOT/f'{phase}-activation.json').exists(),'PHASE_ALREADY_ACTIVATED'
 assert not (ROOT/'STOP.json').exists()
 prerequisite='R0' if phase=='R1' else 'R1';result=read(ROOT/f'{prerequisite}-result.json');assert result['status']=='PASS'
 receipt=read(ROOT/'approval-receipt.json');assert sha(ROOT/'plan.json')==receipt['plan_sha256']
 now=time.time();clock=dict(schema_version=1,phase=phase,started_epoch=now,deadline_epoch=now+10800,shutdown_reserve_seconds=300,wall_seconds_cap=10800)
 save(ROOT/f'{prerequisite}-clock.json',read(ROOT/'clock.json'))
 save(ROOT/'clock.json',clock)
 save(ROOT/f'{phase}-activation.json',dict(epoch=now,clock=clock,approval_receipt_sha256=sha(ROOT/'approval-receipt.json'),prerequisite_result_sha256=sha(ROOT/f'{prerequisite}-result.json'),authority='User approval for execution of gated resolution plan; prior phase passed',conversation_training_authorized=False))
 # All immutable production dependencies and prospective inputs, never outputs
 # which the phase itself is about to produce.
 files=[*ROOT.glob('*.py'),ROOT/'probes.json',ROOT/'anchors-private.json',ROOT/'rubric.json',ROOT/'plan.json',ROOT/'approval-receipt.json',ROOT/'clock.json',ROOT/f'{phase}-activation.json',ROOT/'packet-reference.json',OLD/'packet.json',OLD/'validation.npy',OLD/'engine.py',OLD/'engine_support.py',OLD/'finalize.py',UPSTREAM/'model.py',UPSTREAM/'tokenizer.py',UPSTREAM/'tokenizer.model',ROOT/f'{prerequisite}-result.json']
 corpus=read(PROJECT/'restart/mac15m-feasibility-v1/data-receipt.json')
 for r in corpus['shards']:
  f=UPSTREAM/'data/TinyStories_all_data'/r['shard'].replace('.json','.bin');assert sha(f)==r['token_sha256'],'TRAINING_DATA_MUTATED';files.append(f)
 if phase=='R1':files.append(PROJECT/'restart/foundation-stage3-v1/stage3-checkpoint.pt')
 else:files.append(ROOT/result['selected_arm']/'checkpoint.pt')
 save(ROOT/f'{phase}-freeze.json',dict(phase=phase,epoch=time.time(),files={str(p.relative_to(PROJECT)):sha(p) for p in files}))
 check(phase)

def main():
 phase=sys.argv[1];activate(phase)
 marker=ROOT/f'{phase}-attempt.json';assert not marker.exists();save(marker,dict(epoch=time.time(),phase=phase,one_attempt=True))
 commands=[]
 if phase=='R1':
  for arm in ['A','B']:
   commands.append([str(PYTHON),str(ROOT/'train.py'),phase,arm]);commands.append([str(PYTHON),str(ROOT/'evaluate.py'),phase,'fp32',str((ROOT/arm/'checkpoint.pt').relative_to(PROJECT)),arm])
 else:
  commands=[[str(PYTHON),str(ROOT/'train.py'),phase,'selected'],[str(PYTHON),str(ROOT/'evaluate.py'),phase,'fp32',str((ROOT/'R2/checkpoint.pt').relative_to(PROJECT)),'R2']]
 supervise(phase,commands,phase+'-execution')
 arms=['A','B'] if phase=='R1' else ['R2']
 for arm in arms:
  assert read(ROOT/arm/'training-complete.json')['status']=='PASS'
  assert abs(read(ROOT/arm/'summary.json')['validation_nll']-read(ROOT/arm/'fp32.json')['validation_nll'])<=.02,'FP32_PARITY_FAILED'
 if phase=='R1':assert read(ROOT/'A/batch-hashes.json')['hashes']==read(ROOT/'B/batch-hashes.json')['hashes'],'ARM_DATA_MISMATCH'
 save(ROOT/f'{phase}-computation-pass.json',dict(status='PASS',phase=phase,epoch=time.time(),positions=Meter(phase).total(),teacher_review_pending=True))
if __name__=='__main__':
 try:main()
 except BaseException as e:
  save(ROOT/'STOP.json',dict(phase=sys.argv[1],reason=type(e).__name__+': '+str(e),epoch=time.time(),training_authorized=False));raise
