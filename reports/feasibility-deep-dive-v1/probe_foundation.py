"""Read-only matched foundation diagnostics, not release tests or training data."""
import json,hashlib,time,gc,datetime
from pathlib import Path
import torch
from cloud_training.nano_serve import load_own_bundle
from cloud_training.nano_probes import run_probes,FINAL_TOKENIZER_SHA256
P=Path('reports/feasibility-deep-dive-v1')
CASES=[
 ('updated_location','A parcel moved from Jaipur to Surat. Its current location is',' Surat',' Jaipur'),
 ('updated_owner','Initially Priya owned the mug. She gave it to Kabir. The mug now belongs to',' Kabir',' Priya'),
 ('colour','The folder is purple, and the chair is brown. The folder is',' purple',' brown'),
 ('age','Ravi is older than Meera. Of these two people, the younger one is',' Meera',' Ravi'),
 ('water','At standard atmospheric pressure, pure water freezes at',' 0',' 100'),
 ('planet','The planet on which humans live is',' Earth',' Jupiter'),
 ('biology','Plants use sunlight to make food through',' photosynthesis',' digestion'),
 ('circuit','A simple electric circuit must be closed for current to',' flow',' stop'),
 ('addition','23 + 16 =',' 39',' 37'),
 ('subtraction','85 - 27 =',' 58',' 62'),
 ('multiplication','6 * 7 =',' 42',' 48'),
 ('division','72 / 8 =',' 9',' 6'),
]
(P/'diagnostic-cases.json').write_text(json.dumps({'purpose':'exposed_foundation_diagnostic_not_release','cases':CASES,'limits':'Small investigator-authored cloze contrast set, not general accuracy. Candidate rankings are not free generation. Sum and mean token NLL both reported; tokenizer length effects remain.'},indent=2)+'\n')
models=[('base10b','runs/local-readiness-v1/base10b',True),('sft50','runs/quality-rca-v1/step-00000050',False),('sft194','runs/ownbase-budget50-v1/local-candidates/new-base-2k-8epochs',False)]
for name,path,base in models:
 start=time.monotonic();model,tok,meta=load_own_bundle('runs/nanochat-source',path,'runs/ownbase-v2-data/tokenizer',tokenizer_sha256=FINAL_TOKENIZER_SHA256,device='mps',allow_base=base)
 raw=run_probes(model,tok);pairs=[]
 for key,prompt,correct,wrong in CASES:
  results=[]
  prefix=tok.encode(prompt,prepend=tok.get_bos_token_id())
  for text in [correct,wrong]:
   suffix=tok.encode(text);ids=prefix+suffix
   labels=[-1]*(len(prefix)-1)+suffix
   with torch.inference_mode():nll=model(torch.tensor([ids[:-1]],device='mps'),torch.tensor([labels],device='mps'),loss_reduction='sum').item()
   results.append({'text':text,'tokens':len(suffix),'sum_nll':nll,'mean_nll':nll/len(suffix)})
  pairs.append({'id':key,'prompt':prompt,'candidates':results,'correct_preferred_sum':results[0]['sum_nll']<results[1]['sum_nll'],'correct_preferred_mean':results[0]['mean_nll']<results[1]['mean_nll']})
 output={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checkpoint':path,'manifest_sha256':hashlib.sha256((Path(path)/'manifest.json').read_bytes()).hexdigest(),'raw_completions':raw,'contrastive':pairs,'correct_preferred_sum':sum(r['correct_preferred_sum'] for r in pairs),'correct_preferred_mean':sum(r['correct_preferred_mean'] for r in pairs),'seconds':time.monotonic()-start,'device':'mps','trained':False,'release_exposure':False}
 (P/(name+'.json')).write_text(json.dumps(output,indent=2)+'\n');print(name,output['correct_preferred_sum'],output['correct_preferred_mean'],flush=True)
 del model;gc.collect();torch.mps.empty_cache()
