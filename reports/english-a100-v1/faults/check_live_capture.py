"""Tiny CPU fixture validates post-signal live-state capture, not CUDA recovery."""
import json,os,subprocess,sys,tempfile
from pathlib import Path
P=Path(__file__).parent.resolve()
with tempfile.TemporaryDirectory() as d:
 root=Path(d)
 fixture='''import torch,signal,runpy,sys,json
from pathlib import Path
from types import SimpleNamespace
from cloud_training.nano_checkpoint import save_bundle
from cloud_training.nano_restart_compare import compare_bundles
received=[]
signal.signal(signal.SIGTERM,lambda sig,frame:received.append(sig))
def stopping():return bool(received)
def backward_weighted(model):
 assert not stopping()
 model.weight.sum().backward()
 assert stopping()
def run():
 model=torch.nn.Linear(2,1);optimizer=torch.optim.SGD(model.parameters(),lr=.1)
 out=Path(OUTPUT);out.mkdir()
 packing=SimpleNamespace(state_dict=lambda:{'cursor':0})
 trained_targets=0;best_dev=2.;best_step=0;step=0;reason='lease_or_signal'
 guards={'aggregate':SimpleNamespace(state={'stopped':False})}
 metadata={'step':0,'identity':{'test':'live-capture'},'loop':{'trained_targets':trained_targets,'best_dev':best_dev,'best_step':best_step,'quality_guards':{'aggregate':{'stopped':False}}}}
 save_bundle(out/'step-00000000',model=model,optimizer=optimizer,metadata=metadata,data_state={'exact':True,'next_batch':0,'packing':packing.state_dict()})
 backward_weighted(model);model.zero_grad(set_to_none=True)
 return 0
'''
 code='import sys,os,runpy\nfrom pathlib import Path\n'
 code+='scope={"OUTPUT":'+repr(str(root/'out'))+'}\n'
 code+='exec(compile('+repr(fixture)+',"/test/cloud_training/nano_sft.py","exec"),scope)\n'
 code+='runpy.run_module=lambda *a,**k:scope["run"]()\n'
 code+='sys.argv=["inject"]\nexec(compile(Path('+repr(str(P/'signal_inject.py'))+').read_text(),"inject","exec"),globals())\n'
 code+='from cloud_training.nano_restart_compare import compare_bundles\nassert compare_bundles('+repr(str(root/'out/step-00000000'))+','+repr(str(root/'out/interrupted-live'))+')["status"]=="pass"\n'
 subprocess.run([sys.executable,'-c',code],env=dict(os.environ,FAULT_SIGNAL_MARKER=str(root/'marker.json')),check=True)
 assert json.loads((root/'marker.json').read_text())['live_post_rollback_saved']
(P/'live-capture-check.json').write_text(json.dumps({'tiny_cpu_live_state_capture':'pass','gpu_fault_qualified':False},indent=2)+'\n');print('Live capture fixture passed')
