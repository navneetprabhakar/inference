"""Test-only real SIGTERM after the first completed accumulation microbatch."""
import json,os,runpy,signal,sys
from pathlib import Path
seen=0
marker=Path(os.environ['FAULT_SIGNAL_MARKER'])
def profile(frame,event,arg):
 global seen
 if event=='call' and frame.f_code.co_name=='stopping' and frame.f_back and frame.f_back.f_code.co_name=='backward_weighted':
  seen+=1
  if seen==2:
   model=frame.f_back.f_locals['model']
   partial=any(p.grad is not None for p in model.parameters())
   if not partial:raise RuntimeError('Signal injection did not reach partial accumulation')
   marker.write_text(json.dumps({'real_signal':'SIGTERM','accumulation_stop_check':seen,'partial_gradients_present':partial,'pid':os.getpid()})+'\n')
   os.kill(os.getpid(),signal.SIGTERM)
 if event=='return' and frame.f_code.co_name=='run' and frame.f_code.co_filename.endswith('/cloud_training/nano_sft.py') and marker.exists():
  sys.setprofile(None)
  from cloud_training.nano_checkpoint import save_bundle
  state=frame.f_locals
  if state['step']!=0 or state['reason']!='lease_or_signal':raise RuntimeError('Unexpected live rollback boundary')
  initial=json.loads((state['out']/'step-00000000/metadata.json').read_text())
  initial['loop']={'trained_targets':state['trained_targets'],'best_dev':state['best_dev'],'best_step':state['best_step'],'quality_guards':{name:dict(g.state) for name,g in state['guards'].items()}}
  save_bundle(state['out']/'interrupted-live',model=state['model'],optimizer=state['optimizer'],metadata=initial,data_state={'exact':True,'next_batch':state['step'],'packing':state['packing'].state_dict()})
  record=json.loads(marker.read_text());record['live_post_rollback_saved']=True;marker.write_text(json.dumps(record)+'\n')
sys.argv=['cloud_training.nano_sft',*sys.argv[1:]]
sys.setprofile(profile)
runpy.run_module('cloud_training.nano_sft',run_name='__main__')

sys.setprofile(None)
