"""Independent FP32/MPS loss check of the saved, updated checkpoint. No updates."""
import json,sys,time
from pathlib import Path
import numpy as np
import torch
from engine_support import ROOT,PROJECT,UPSTREAM,Meter,save,sha,CHECKPOINT
sys.path.insert(0,str(UPSTREAM))
from model import ModelArgs,Transformer

def main():
    if (ROOT/'serialized-reference.json').exists():raise RuntimeError('One reference check only')
    assert json.loads((ROOT/'train-supervisor.json').read_text())['worker_reaped']
    state=torch.load(ROOT/'stage2-checkpoint.pt',map_location='cpu',weights_only=False)
    assert state['optimizer_step']==1745 and state['completed_targets']==228720640
    receipt=json.loads((ROOT/'stage2-checkpoint.json').read_text());assert sha(ROOT/'stage2-checkpoint.pt')==receipt['sha256']
    torch.set_num_threads(4);model=Transformer(ModelArgs(**state['model_args'])).to('mps');model.load_state_dict(state['model'],strict=True);model.eval()
    a=np.load(ROOT/'validation.npy');losses=[];start=time.monotonic();meter=Meter();deadline=json.loads((ROOT/'clock.json').read_text())['stage2_deadline_epoch']-20
    with torch.inference_mode():
      for i in range(0,len(a),16):
        assert time.time()<deadline and not (ROOT/'global-stop.json').exists()
        part=a[i:i+16];meter.reserve(len(part)*256,'serialized-FP32-reference')
        model(torch.from_numpy(part[:,:-1].astype(np.int64)).to('mps'),torch.from_numpy(part[:,1:].astype(np.int64)).to('mps'));losses.append(float(model.last_loss))
    reference=float(np.mean(losses));native=json.loads((ROOT/'stage2-evaluation/summary.json').read_text())['validation_nll'];difference=abs(reference-native)
    save(ROOT/'serialized-reference.json',dict(status='PASS' if difference<=.02 else 'FAIL',checkpoint_sha256=sha(ROOT/'stage2-checkpoint.pt'),FP32_reference_nll=reference,BF16_native_nll=native,absolute_difference=difference,tolerance=.02,targets=131072,seconds=time.monotonic()-start,training_updates=0,checkpoint_unchanged=sha(ROOT/'stage2-checkpoint.pt')==receipt['sha256']))
    assert difference<=.02,'Updated serialized checkpoint parity failure; no tolerance relaxation'
if __name__=='__main__':main()
