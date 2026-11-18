"""Read-only local state audit; no forward/backward, optimizer step, or cloud use."""
import hashlib,json,sys
from pathlib import Path
import torch
sys.path.insert(0,str(Path('runs/nanochat-source').resolve()))
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_chat_format import token_contract
from cloud_training.nano_checkpoint import validate_bundle
T=RustBPETokenizer.from_directory('runs/ownbase-v2-data/tokenizer');controls=token_contract(T);result=[]
for name,path in [('base10b','runs/local-readiness-v1/base10b'),('fit20','runs/ganesh-a100-cap40-v1/local-fit/step-00000020'),('fit30','runs/ganesh-a100-cap40-v1/local-fit/step-00000030')]:
 p=Path(path);validate_bundle(p);data=torch.load(p/'payload.pt',map_location='cpu',weights_only=True,mmap=True)
 group=data['optimizer']['param_groups'][0];assert group['kind']=='adamw' and len(group['params'])==1
 state=data['optimizer']['state'][group['params'][0]];w=data['model']['lm_head.weight'];assert state['exp_avg'].shape==w.shape
 stats=[]
 for token,i in controls.items():
  a=state['exp_avg'][i].float();v=state['exp_avg_sq'][i].float()
  stats.append({'token':token,'id':i,'weight_rms':float(w[i].float().square().mean().sqrt()),'first_moment_rms':float(a.square().mean().sqrt()),'second_moment_mean':float(v.mean()),'normalized_moment_rms':float((a/(v.sqrt()+group['eps'])).square().mean().sqrt())})
 result.append({'checkpoint':name,'manifest_sha256':hashlib.sha256((p/'manifest.json').read_bytes()).hexdigest(),'model_shape':list(w.shape),'optimizer_step':state['step'],'head_group':{k:v for k,v in group.items() if k!='params'},'controls':stats})
 del data
out={'purpose':'Saved output-head optimizer states, not evidence of causal repair','mapping_evidence':'Pinned GPT.setup_optimizer puts lm_head alone in group0; saved moment shape matches saved lm_head weight.','checkpoints':result}
Path(__file__).with_name('optimizer-state.json').write_text(json.dumps(out,indent=2)+'\n')
for r in result:
 e=next(x for x in r['controls'] if x['token']=='<|assistant_end|>');print(r['checkpoint'],r['optimizer_step'],r['head_group'],e,flush=True)
