"""Separate-process exact comparisons; outputs survive a failed numerical gate."""
import sys,json,hashlib
from pathlib import Path
import torch
from cloud_training.nano_optimizer_capture import load_capture,exact
if sys.argv[1]=='--replays':
 root=Path(sys.argv[2]);result={}
 for mode in ([sys.argv[3]] if len(sys.argv)>3 else ('eager','compiled')):
  assert mode in ('eager','compiled')
  a,b=[root/f'replay-{mode}-{i}' for i in (1,2)]
  ra,rb=[json.loads((x/'result.json').read_text()) for x in (a,b)]
  av,bv=[torch.load(x/'first-output.pt',map_location='cpu',weights_only=True) for x in (a,b)]
  result[mode]={'fresh_process_equal':exact(av,bv),'first':ra,'second':rb}
 dest=root/'replay-comparison.json'
else:
 a,b=[Path(x) for x in sys.argv[1:3]];ma,ba,aa=load_capture(a);mb,bb,ab=load_capture(b)
 result={'input_values_layout_equal':exact(ba,bb),'output_values_layout_equal':exact(aa,ab),'context_equal':ma==mb,'reference_manifest_sha256':hashlib.sha256((a/'manifest.json').read_bytes()).hexdigest(),'resumed_manifest_sha256':hashlib.sha256((b/'manifest.json').read_bytes()).hexdigest()}
 dest=Path(sys.argv[3])
with dest.open('x') as f:json.dump(result,f,indent=2)
print(json.dumps(result))
