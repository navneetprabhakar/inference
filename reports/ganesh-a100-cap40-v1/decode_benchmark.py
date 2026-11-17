"""Conservative fixed-length uncached forward benchmark; not a quality evaluation.
Never edits model logits, actual serving answers or frozen evaluation budgets.
"""
import json,time,hashlib,sys
from pathlib import Path
import torch
from cloud_training.nano_serve import load_own_bundle
ROOT=Path('/opt/english');OUT=ROOT/'results';cfg=json.loads((ROOT/'config.json').read_text())
t0=time.monotonic();model,tok,meta=load_own_bundle(ROOT/'nanochat-source',ROOT/'base',ROOT/'tokenizer',tokenizer_sha256=cfg['tokenizer_sha256'],device='cuda',allow_base=True);load_seconds=time.monotonic()-t0
# Match uncached serving's forward, finite-logit check, greedy scalar read and concatenation.
# A constant token continues the workload to its full budget, avoiding early-EOS timing bias.
prompt=[int(x) for x in tok.encode('This is a short English conversation. ')]
measurements=[]
for length in (512,1856):
 times=[]
 for trial in range(3):
  ids=torch.tensor([ (prompt*((length//len(prompt))+1))[:length] ],device='cuda',dtype=torch.long)
  torch.cuda.synchronize();started=time.monotonic()
  with torch.inference_mode():
   for _ in range(192):
    logits=model(ids)[:,-1,:]
    if not bool(torch.isfinite(logits).all()):raise ValueError('Nonfinite benchmark logits')
    sampled=int(torch.argmax(logits,dim=-1).item())
    ids=torch.cat((ids,torch.tensor([[prompt[0]]],device='cuda',dtype=torch.long)),dim=1)
  torch.cuda.synchronize();times.append(time.monotonic()-started)
 measurements.append({'prefix_tokens':length,'output_steps':192,'seconds':times})
worst=max(s for m in measurements for s in m['seconds']);per_token=worst/192
# Use worst full-context throughput for all tokens, plus repeated model-load costs and 25% margin.
fit=1.25*(228096*per_token+9*load_seconds);curriculum=1.25*(90432*per_token+6*load_seconds)
single_probe=1.25*(27648*per_token+load_seconds)
result={'largest_single_probe_forecast_seconds':single_probe,'load_seconds':load_seconds,'measurements':measurements,'worst_seconds_per_token':per_token,'fit_probe_forecast_seconds':fit,'curriculum_probe_forecast_seconds':curriculum,'fits_predeclared_probe_timeouts':fit<=5400 and curriculum<=5400 and single_probe<=1350,'benchmark_only_not_model_quality':True,'serving_source_sha256':hashlib.sha256((ROOT/'cloud_training/nano_serve.py').read_bytes()).hexdigest()}
(OUT/'decode-benchmark.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
