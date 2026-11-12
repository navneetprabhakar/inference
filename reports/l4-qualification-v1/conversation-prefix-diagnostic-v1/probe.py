import json,sys,hashlib
from pathlib import Path
import torch
from cloud_training.nano_serve import load_own_bundle
from cloud_training.nano_chat_format import encode_conversation
from cloud_training.nano_sft import JsonlConversations,evaluate_fixed
ROOT=Path('/opt/ownbase-nano');OUT=ROOT/'results/conversation-prefix-diagnostic-v1';OUT.mkdir(parents=True,exist_ok=True)
ckpt=ROOT/'results/conversation-repair-v1/sft/step-00000090';toksha='ad777bb448ea8fcf115835548596f9303f3ee5e85a014b0bb315567091080cc5'
model,tok,meta=load_own_bundle(ROOT/'nanochat-source',ckpt,ROOT/'tokenizer',tokenizer_sha256=toksha,device='cuda')
import nanochat.flash_attention as attention
path=ROOT/'sft/conversation-repair-admitted-v1/validation.jsonl';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();data=JsonlConversations(path,tok,sha(path));raw=[json.loads(x) for x in path.read_text().splitlines()]
report={'checkpoint_manifest_sha256':sha(ckpt/'manifest.json'),'attention_default':'fa3' if attention.USE_FA3 else 'sdpa','records':[],'usable_model_claim':False}
with torch.inference_mode():
 report['packed_default']=evaluate_fixed(model,data,rows=64,microbatch=8,device='cuda')
 samples=[r for r in raw if r['family']=='grounded_plan'][:6]
 for row in samples:
  encoded=encode_conversation(tok,row['messages'],policies=row.get('policies'));ids=encoded['ids'];mask=encoded['mask'];x=torch.tensor([ids[:-1]],device='cuda');logits=model(x)[0]
  targets=torch.tensor(ids[1:],device='cuda');supervised=torch.tensor(mask[1:],device='cuda',dtype=torch.bool)
  ce=torch.nn.functional.cross_entropy(logits,targets,reduction='none');rec={'user':row['messages'][0]['content'],'isolated_ce':float(ce[supervised].mean()),'targets':int(supervised.sum()),'prefix_checks':[]}
  spans=[s for s in encoded['spans'] if s['kind']=='assistant_text']
  for span in spans[:2]:
   # Only ground-truth prior context; compare full teacher-forced vs causal prefix logits.
   for offset in (0,1,6,10):
    t=span['start']+offset
    if t>=span['end']:continue
    prefix=model(torch.tensor([ids[:t]],device='cuda'))[0,-1];full=logits[t-1]
    target=ids[t];top=int(prefix.argmax());expected=tok.decode([target]);actual=tok.decode([top])
    rec['prefix_checks'].append({'position':t,'assistant_offset':offset,'target':expected,'top1':actual,'target_probability':float(prefix.softmax(-1)[target]),'full_prefix_top1_same':int(full.argmax())==top,'full_prefix_max_abs_diff':float((prefix-full).abs().max())})
  report['records'].append(rec)
  (OUT/'probe.json').write_text(json.dumps(report,indent=2)+'\n')
 # Reproduce training kernel for packed loss, separate from default serving backend.
 from kernels import get_local_kernel
 attention._fa3=get_local_kernel(ROOT/'kernel','flash_attn3').flash_attn_interface;attention.USE_FA3=True
 report['packed_training_kernel']=evaluate_fixed(model,data,rows=64,microbatch=8,device='cuda')
report['status']='complete';(OUT/'probe.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='records'}),flush=True)
