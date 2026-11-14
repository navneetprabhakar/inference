"""Read-only 537M/4096 forward smoke; no training, chat server, or release queries."""
import os,sys,json,time,hashlib
from pathlib import Path
os.environ['NANOCHAT_DTYPE']='float32';os.environ['HF_HUB_OFFLINE']='1'
sys.path.insert(0,str(Path('runs/nanochat-source').resolve()))
import torch
from nanochat.gpt import GPT,GPTConfig
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_checkpoint import validate_bundle
from cloud_training.nano_context import transition_config
from cloud_training.nano_sft import JsonlConversations
P=Path('runs/ownbase-budget50-v1/local-candidates/new-base-2k-8epochs');validate_bundle(P)
meta=json.loads((P/'metadata.json').read_text());cfg,transition=transition_config(meta['identity']['config'],4096,allow_extension=True)
assert torch.backends.mps.is_available();torch.set_num_threads(4)
with torch.device('meta'):model=GPT(GPTConfig(**cfg))
model.to_empty(device='mps');model.init_weights()
payload=torch.load(P/'payload.pt',map_location='cpu',weights_only=True);model.load_state_dict(payload['model'],strict=True);del payload
model.eval();tok=RustBPETokenizer.from_directory('runs/ownbase-v2-data/tokenizer');path=Path('reports/corrective-corpus-v1/candidate-4k/validation.jsonl')
d=JsonlConversations(path,tok,hashlib.sha256(path.read_bytes()).hexdigest(),4096)
i=max(range(len(d)),key=lambda n:d.lengths[n]);ids,mask=d.get(i);x=ids+[tok.get_bos_token_id()]*(4097-len(ids));y=[t if m else -1 for t,m in zip(ids[1:],mask[1:])]+[-1]*(4097-len(ids))
assert len(x[:-1])==len(y)==4096
start=time.monotonic()
with torch.inference_mode():loss=model(torch.tensor([x[:-1]],device='mps'),torch.tensor([y],device='mps'))
torch.mps.synchronize();assert torch.isfinite(loss)
result={'status':'full_size_4k_forward_pass','device':'mps','parameters':sum(p.numel() for p in model.parameters()),'sequence_length':4096,'real_development_tokens':len(ids),'loss':loss.item(),'seconds':time.monotonic()-start,'allocated_bytes':torch.mps.current_allocated_memory(),'driver_allocated_bytes':torch.mps.driver_allocated_memory(),'context_transition':transition,'checkpoint_unchanged':True,'trained':False,'release_exposures':0,'limitations':'In-memory context extension only; finite forward is not conversation quality, optimizer qualification, or an accepted 4K checkpoint.'}
Path('reports/local-readiness-v1/mps-4k-smoke.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
