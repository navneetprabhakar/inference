"""Prepare explicit CPU-only activation metadata; never launch a worker."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent

def pin(p):
 p=Path(p).resolve();return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())

def main():
 old=json.loads((ROOT/'reports/own-base-sft-preflight/activation-v1.json').read_text())
 allocation=json.loads((OUT/'allocation.json').read_text())
 old['state']='pending_root_review_for_hardware_preflight'
 old['run']=str(ROOT/'runs/own-base-grounded-sft-preflight-01')
 old['datasets']=[{k:v for k,v in s.items()if k in ('name','receipt','admission','verification','development_split')} for s in allocation['datasets']]
 old['extension_qualification']=pin(ROOT/'data/grounded-session-aligned-v2/four-call-qualification.json')
 for name,sha in old['runtime_sha256'].items():
  if pin(ROOT/name)['sha256']!=sha:raise ValueError('frozen trainer runtime changed: '+name)
 old['preflight_code_sha256']={name:pin(ROOT/name)['sha256']for name in ('own_base_grounded_preflight.py','verify_own_base_grounded_preflight.py','reports/grounded-sft-preflight-v1/PROTOCOL.md')}
 old['stop_paths']=list(dict.fromkeys(old['stop_paths']+[str(ROOT/'runs/own-base-grounded-sft-preflight-01/STOP'),str(ROOT/'runs/own-base-grounded-sft-diagnostic-01/STOP')]))
 (OUT/'activation-draft.json').write_text(json.dumps(old,indent=2)+'\n')
 print('Prepared non-runnable root-review draft',pin(OUT/'activation-draft.json'))
if __name__=='__main__':main()
