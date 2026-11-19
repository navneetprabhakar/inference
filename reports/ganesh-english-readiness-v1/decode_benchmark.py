"""Full-context uncached decode timing; no quality-score claim or logit edits."""
import json,time
from pathlib import Path
import torch
from cloud_training.nano_serve import load_own_bundle
ROOT=Path('/opt/ganesh-conversation');cfg=json.loads((ROOT/'config-v3.json').read_text())
start=time.monotonic();model,tok,_=load_own_bundle(ROOT/'nanochat-source',ROOT/'parent',ROOT/'tokenizer',tokenizer_sha256=cfg['tokenizer_sha256'],device='cuda',allow_base=True);load=time.monotonic()-start
prompt=tok.encode('This is a short English conversation. ');trials=[]
for _ in range(3):
 ids=torch.tensor([(prompt*((1856//len(prompt))+1))[:1856]],device='cuda',dtype=torch.long)
 torch.cuda.synchronize();start=time.monotonic()
 with torch.inference_mode():
  for i in range(192):
   logits=model(ids)[:,-1,:]
   if not bool(torch.isfinite(logits).all()):raise ValueError('Nonfinite benchmark logits')
   sampled=int(torch.argmax(logits,dim=-1).item())
   ids=torch.cat((ids,torch.tensor([[prompt[0]]],device='cuda',dtype=torch.long)),dim=1)
 torch.cuda.synchronize();trials.append(time.monotonic()-start)
seconds=max(trials)/192;forecast=164640*seconds*1.5+7*load
result={'benchmark_only':True,'worst_seconds_per_token':seconds,'load_seconds':load,'trials_seconds':trials,'generation_seconds_upper':forecast,'generation_fits':forecast<=5400,'maximum_generated_tokens':164640}
(ROOT/'qualification-v3/decode-benchmark.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
raise SystemExit(0 if result['generation_fits'] else 2)
