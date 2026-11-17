"""Read-only test of packing context and assistant-end head saturation."""
import fcntl,json,os,time,hashlib,subprocess,tarfile
from pathlib import Path
import torch
from cloud_training.nano_serve import load_own_bundle
from cloud_training.nano_chat_format import token_contract
from cloud_training.nano_sft import JsonlConversations,FiniteEpochDataset,BestFitConversations
R=Path('/opt/english-eager');os.chdir(R);assert (R/'fit-closeout/backup.json').exists()
lock=open('/tmp/ganesh-gpu-writer.lock','a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
D=R/'packing-diagnosis';D.mkdir(exist_ok=False);r=json.loads((R/'pilot-request.json').read_text());c=r['training_inputs'];rows=[];start=time.monotonic()
for step in (0,20,30):
 ck=R/f'runs/ganesh-recovery-next/fit/step-{step:08d}';model,tok,_=load_own_bundle(R/c['repo'],ck,R/c['tokenizer'],tokenizer_sha256=c['tokenizer_sha256'],device='cuda',allow_base=True)
 end=token_contract(tok)['<|assistant_end|>'];path='reports/english-first-v1/fit-train.jsonl';ds=JsonlConversations(R/path,tok,r['files'][path],context=2048)
 raw=[]
 hook=model.lm_head.register_forward_hook(lambda module,inputs,out:raw.append(out[0,:,end].detach().float().cpu()))
 pack=BestFitConversations(FiniteEpochDataset(ds,1,seed=103),buffer_size=1)
 while True:
  try:xs,ys=pack.next_row()
  except StopIteration:break
  assert time.monotonic()-start<900
  x=torch.tensor([xs],device='cuda');y=torch.tensor(ys,device='cuda');mask=y!=-1;ending=y==end;content=mask&~ending
  with torch.inference_mode():
   logits=model(x)[0];loss=torch.nn.functional.cross_entropy(logits,y,ignore_index=-1,reduction='none');rank=(logits[ending]>logits[ending,end,None]).sum(-1)+1
   head=raw.pop()[ending.cpu()];derivative=1-torch.tanh(head/15)**2
   rows.append({'step':step,'packed_row':pack.rows,'targets':int(mask.sum()),'content_targets':int(content.sum()),'content_loss_sum':float(loss[content].sum()),'endpoints':int(ending.sum()),'end_loss_sum':float(loss[ending].sum()),'end_top1':int((rank==1).sum()),'raw_end_logits':head.tolist(),'softcap_derivative':derivative.tolist()})
 hook.remove();del model;torch.cuda.empty_cache()
p=D/'result.json';p.write_text(json.dumps({'scope':'First-epoch seed103 packed teacher-forced diagnostic; no optimizer updates, no acceptance','records':rows},indent=2)+'\n')
a=R/'packing-diagnosis.tar.gz'
with tarfile.open(a,'w:gz') as t:t.add(p,arcname='result.json');t.add(Path(__file__),arcname='diagnose_packing.py')
uri=json.loads((R/'config.json').read_text())['backup_prefix']+'/english/packing-diagnosis/evidence.tar.gz'
for source,dest in [(str(a),uri),(uri,str(R/'packing-diagnosis-readback.tar.gz'))]:subprocess.run(['gcloud','storage','cp',source,dest,'--quiet'],check=True,timeout=180)
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert sha(a)==sha(R/'packing-diagnosis-readback.tar.gz')
(D/'backup.json').write_text(json.dumps({'uri':uri,'sha256':sha(a),'full_readback_verified':True},indent=2)+'\n')
