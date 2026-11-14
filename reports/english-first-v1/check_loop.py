"""Run the actual nano_sft while-body in a fresh CPU process with fake compute/I/O.
Tests orchestration only; does NOT qualify CUDA, real checkpoints or GCS recovery.
"""
import ast,json,sys,tempfile,time
from pathlib import Path
from types import SimpleNamespace as NS
from cloud_training.nano_quality_gate import ValidationGuard
from cloud_training.nano_qualification_schedule import restart_branches,validate_restart_branches
branches=restart_branches();validate_restart_branches(branches)
a=json.loads(sys.argv[1]);state=a.get('state');step=0 if state is None else state['step']
guard=ValidationGuard({'relative_tolerance':.05,'patience':2},None if state is None else state['guard'])
if state is None:guard.observe(0,a['losses'][0])
class Packing:
 consumed=step
 rows=step
 def state_dict(self):return {'consumed':self.consumed}
 def load_state_dict(self,s):self.consumed=s['consumed'];self.rows=self.consumed
packing=Packing()
def collect_update(*args):packing.consumed+=1;packing.rows+=1;return [1],1
observed=[]
def observe_quality(ev):
 observed.append(step)
 return ['aggregate'] if guard.observe(step,ev['cross_entropy_nats']) else []
def evaluate_fixed(*args,**kwargs):return {'cross_entropy_nats':a['losses'][step]}
class Model:
 def parameters(self):return iter([NS(grad=None,device='cpu')])
 def zero_grad(self,**kwargs):pass
model=Model();optimizer=NS(param_groups=[],step=lambda:None)
torch=NS(cuda=NS(synchronize=lambda:None),nn=NS(utils=NS(get_total_norm=lambda *args,**kwargs:None)))
dev=None
args=NS(eval_rows=10,microbatch=1,eval_every_updates=a.get('cadence',1),checkpoint_seconds=100000)
recipe={'rows_per_update':1};guards={'aggregate':guard};status={};compiled=None;train=list(range(100))
trained_targets=step;best_dev=guard.state['best_ce'];best_step=guard.state['best_step'];max_step=step+a['updates'];reason='pilot_update_limit';last_save=time.monotonic()
stopping=lambda: a.get('signal_at') is not None and step>=a['signal_at']
capture_rng=lambda:None;restore_rng_state=lambda x:None
backward_weighted=lambda *args,**kwargs:1.;sft_schedule=lambda *args:(1.,0.)
checkpoint=lambda *args,**kwargs:None;atomic_json=lambda *args:None
module=ast.parse(Path('cloud_training/nano_sft.py').read_text())
run=next(n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='run')
loop=next(n for n in run.body if isinstance(n,ast.While))
with tempfile.TemporaryDirectory() as directory:
 out=Path(directory)
 exec(compile(ast.Module(body=[loop],type_ignores=[]),'actual_nano_sft_loop','exec'),globals())
print(json.dumps({'step':step,'guard':guard.state,'best_dev':best_dev,'best_step':best_step,'observed':observed,'reason':reason}))
