"""Read-only target-level termination diagnosis; no optimizer or answer repair."""
import fcntl,hashlib,json,os,time
from pathlib import Path
import torch
from cloud_training.nano_serve import load_own_bundle
from cloud_training.nano_chat_format import token_contract
from cloud_training.nano_sft import JsonlConversations
R=Path('/opt/english-eager'); os.chdir(R)
assert (R/'stopped-fit-assessment/complete.json').exists()
lock=open('/tmp/ganesh-gpu-writer.lock','a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
P=R/'termination-diagnosis';P.mkdir(exist_ok=False)
req=json.loads((R/'pilot-request.json').read_text()); cfg=req['training_inputs']
start=time.monotonic(); records=[]
for step in (0,20,30):
 ck=R/f'runs/ganesh-recovery-next/fit/step-{step:08d}'
 model,tok,meta=load_own_bundle(R/cfg['repo'],ck,R/cfg['tokenizer'],tokenizer_sha256=cfg['tokenizer_sha256'],device='cuda',allow_base=True)
 end=token_contract(tok)['<|assistant_end|>']
 for split,path in [('fit','reports/english-first-v1/fit-train.jsonl'),('dev','reports/english-first-v1/development-reference.jsonl')]:
  ds=JsonlConversations(R/path,tok,req['files'][path],context=2048)
  names=[json.loads(l)['id'] for l in (R/path).read_text().splitlines()]
  for i in range(len(ds)):
   assert time.monotonic()-start<1500
   ids,mask=ds.get(i);x=torch.tensor([ids[:-1]],device='cuda'); y=torch.tensor(ids[1:],device='cuda'); m=torch.tensor(mask[1:],device='cuda',dtype=torch.bool)
   with torch.inference_mode():
    logits=model(x)[0];loss=torch.nn.functional.cross_entropy(logits,y,reduction='none'); ending=m&(y==end);content=m&~ending
    ends=[]
    for p in torch.where(ending)[0].tolist():
     z=logits[p]; top=int(z.argmax());ends.append({'position':p,'probability':float(z.softmax(-1)[end]),'rank':int((z>z[end]).sum())+1,'top_token':top,'top_text':tok.decode([top]),'end_loss':float(loss[p])})
   records.append({'step':step,'split':split,'session':names[i],'targets':int(m.sum()),'content_loss':float(loss[content].mean()),'end_loss':float(loss[ending].mean()),'endpoints':ends})
   (P/'progress.json').write_text(json.dumps({'records':records,'complete':False}))
 del model;torch.cuda.empty_cache()
(P/'result.json').write_text(json.dumps({'purpose':'teacher_forced_diagnostic_not_conversation_acceptance','complete':True,'records':records},indent=2)+'\n')
