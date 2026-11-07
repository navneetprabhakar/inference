"""Explicit external milestone evaluator; immutable original web/context/raw series.

Launch only through this CLI's owned watchdog. Never writes root decisions.
Whole worst-case attempts/time reserved before child spawn; no implicit retries.
"""
import subprocess
import argparse,fcntl,hashlib,json,math,os,resource,shutil,sys,time
from pathlib import Path
import own_base_dev_run as rt
ROOT=Path(__file__).resolve().parent
SERIES=['original-web-256','context-pairs-32','raw-continuations-32']
FOUNDATION_SHA='658702f471c49b4362c29f46795f5fc6b3135f7e7c7bd540e50d34c2c547fb7d'
def need(x,s):
 if not x:raise ValueError(s)
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def canon(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def readpin(pin):
 p=Path(pin['path']);need(p.is_file() and not p.is_symlink() and sha(p)==pin['sha256'],'pin '+str(p));return json.loads(p.read_text())
def signed(path,value):rt.atomic(path,dict(value,sha256=hashlib.sha256(canon(value)).hexdigest()))
def unsigned(path):
 d=json.loads(path.read_text());s=d.pop('sha256');need(hashlib.sha256(canon(d)).hexdigest()==s,'ledger checksum');return d

def ac_power_text(text):
 return bool(__import__('re').search(r"Now drawing from ['\"]AC Power['\"]",text))

def require_ac_power():
 need(ac_power_text(subprocess.check_output(['pmset','-g','batt'],text=True,timeout=2)),'mandatory AC power')

def runtime_versions():
 import torch,numpy
 return dict(torch=str(torch.__version__),numpy=numpy.__version__,python=sys.version)

def validate(request_pin):
 request=readpin(request_pin);run=Path(request_pin['path']).resolve().parent;t=request['trained_tokens'];need(type(t)is int and t>=0,'milestone integer');need(run.parent==ROOT/'runs' and Path(request_pin['path']).name==f'milestone-{t}-request.json','canonical request path')
 protocol=readpin(request['protocol']);need(protocol['state']=='reviewed_external_language_milestone' and protocol['series']==SERIES,'reviewed immutable series')
 need(protocol['python']==str(Path(sys.executable).absolute()),'interpreter identity')
 need(protocol['runtime_versions']==runtime_versions(),'numeric runtime versions')
 need(protocol['mandatory_ac_power'] is True,'mandatory AC policy')
 need(type(protocol['rss_limit_bytes'])is int and 0<protocol['rss_limit_bytes']<=18*1024**3,'RSS ceiling')
 need(isinstance(protocol['stop_paths'],list) and str(ROOT/'runs/STOP') in protocol['stop_paths'],'STOP inheritance')
 for n,h in protocol['code_sha256'].items():need(sha(ROOT/n)==h,'code '+n)
 required={'own_base_language_milestone.py','own_base_dev_run.py','base_train.py','gpt2.py','tokenizer.py','checkpoint.py','guards.py','optimizer_ablation_train.py','base_run_control.py','pretrained_base.py','pretrain.py','train.py'};need(required<=protocol['code_sha256'].keys(),'runtime pins')
 for k in ('attempted_targets','input_positions','attention_elements','active_seconds','calendar_seconds'):need(type(protocol['budgets'][k])in(int,float) and math.isfinite(protocol['budgets'][k]) and protocol['budgets'][k]>0,'finite '+k)
 need(20<protocol['per_milestone_seconds']<=protocol['budgets']['active_seconds'],'finite milestone lease')
 need(sha(ROOT/'reports/base-foundation-100m/budget.json')==FOUNDATION_SHA,'frozen foundation budget');foundation=json.loads((ROOT/'reports/base-foundation-100m/budget.json').read_text())
 need(protocol['foundation_budget_sha256']==FOUNDATION_SHA,'foundation pin');need(sha(Path(foundation['diagnostics']))==foundation['diagnostics_sha256'],'diagnostics unchanged')
 need(set(protocol['worst_case'])=={'attempted_targets','input_positions','attention_elements','forwards'},'exact reservation shape')
 need(protocol['length']==512 and protocol['generation_max']==48 and protocol['precision']=='fp32','frozen evaluation layout')
 return request,protocol,run,foundation

def cost_plan(diagnostics,tok,blocks):
 need(len(blocks)==256 and len(diagnostics['pairs'])==32 and len(diagnostics['prefixes'])==32,'original256/32/32 inventory')
 costs=[]
 for b in blocks:costs.append((512,512,512*512))
 for pair in diagnostics['pairs']:
  need(len(pair['members'])==2 and len(pair['choices'])==2,'frozen binary context pair')
  for member in pair['members']:
   prefix=tok.encode(member['prefix']).ids
   for answer in pair['choices']:
    ending=tok.encode(answer).ids;n=len(prefix)+len(ending)-1;need(prefix and ending and n<1024,'pair bounds');costs.append((len(ending),n,n*n))
 for prefix in diagnostics['prefixes']:
  text=prefix['text'] if isinstance(prefix,dict) else prefix;n=len(tok.encode(text).ids);need(n>0 and n+47<=1024,'raw prefix bounds')
  costs.extend((1,n+i,(n+i)**2) for i in range(48))
 return dict(attempted_targets=sum(x[0] for x in costs),input_positions=sum(x[1] for x in costs),attention_elements=sum(x[2] for x in costs),forwards=len(costs))

def forward_cost(batch,length,*,predicted=None,generation=False):
 need(type(batch)is int and type(length)is int and batch>0 and 0<length<=1024,'forward shape')
 targets=predicted if predicted is not None else (batch if generation else batch*length)
 need(type(targets)is int and 0<targets<=batch*length,'predicted positions')
 return dict(attempted_targets=targets,input_positions=batch*length,attention_elements=batch*length*length,forwards=1)

def reserve_forward(totals,cost,ceiling):
 need(set(totals)==set(cost)==set(ceiling),'accounting fields')
 candidate={k:totals[k]+cost[k] for k in totals}
 for key,value in candidate.items():need(type(value)is int and value>=0 and value<=ceiling[key],'forward budget '+key)
 totals.update(candidate)

def launch(pin):
 request,p,run,_=validate(pin);base=run.parent/(run.name+'-external-evaluation');base.mkdir(exist_ok=True);lock=(base/'lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 try:
  bpath=base/'budget.json';b=unsigned(bpath) if bpath.exists() else dict(protocol_sha256=request['protocol']['sha256'],started=time.time(),reserved={k:0 for k in ('attempted_targets','input_positions','attention_elements','active_seconds')},milestones=[])
  need(b['protocol_sha256']==request['protocol']['sha256'],'campaign protocol immutable');t=request['trained_tokens'];need(t not in b['milestones'],'milestone already attempted; explicit new reviewed protocol required for retry')
  seconds=p['per_milestone_seconds'];need(time.time()+seconds-b['started']<=p['budgets']['calendar_seconds'],'calendar cap')
  for key in b['reserved']:
   amount=seconds if key=='active_seconds' else p['worst_case'][key];need(b['reserved'][key]+amount<=p['budgets'][key],'campaign budget '+key);b['reserved'][key]+=amount
  b['milestones'].append(t);signed(bpath,b) # Charge remains on crash/early EOT; no silent retries.
  out=base/f'milestone-{t}';out.mkdir(exist_ok=False);rt.atomic(out/'request-pin.json',pin);ticket=rt.make_ticket(seconds,pin['sha256']);ticket['heartbeat']=str(out/'heartbeat');rt.atomic(out/'launch.json',dict(request_sha256=pin['sha256'],protocol_sha256=request['protocol']['sha256'],worst_case=p['worst_case'],reserved_seconds=seconds))
  def check(pid,left):need(not any(Path(x).exists() for x in p['stop_paths']+[str(run/'STOP'),str(ROOT/'runs/STOP')]),'STOP')
  def command(fd):return [p['python'],str(Path(__file__).resolve()),pin['path'],'--request-sha256',pin['sha256'],'--worker','--ticket-fd',str(fd)]
  result=rt.supervise(command,out,ticket=ticket,heartbeat_seconds=120,grace_seconds=10,max_rss_bytes=p['rss_limit_bytes'],check=check);rt.atomic(out/'watchdog.json',result);return result
 finally:lock.close()

def worker(pin,fd):
 import torch
 import checkpoint
 from gpt2 import Config,GPT2
 from base_train import Corpus,document_losses,language_diagnostics
 from tokenizer import load
 from guards import thermal,swap_mib
 from optimizer_ablation_train import parent_lock
 from dataclasses import asdict
 ticket=rt.consume_ticket(fd);need(ticket['spec_sha256']==pin['sha256'],'ticket request');request,p,run,foundation=validate(pin);out=run.parent/(run.name+'-external-evaluation')/f"milestone-{request['trained_tokens']}";torch.set_num_threads(1);lock=(ROOT/'runs/mps.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);events=(out/'events.jsonl').open('x');totals=dict(attempted_targets=0,input_positions=0,attention_elements=0,forwards=0);last=0;swap=swap_mib();failure=None;result={}
 def check():
  nonlocal last
  need(rt.remaining(ticket)>10,'watchdog deadline margin');Path(ticket['heartbeat']).write_text(str(time.time()));need(not any(Path(x).exists() for x in p['stop_paths']+[str(run/'STOP'),str(ROOT/'runs/STOP')]),'STOP');need(shutil.disk_usage(ROOT).free>=20*1024**3,'disk floor')
  if time.monotonic()-last>5:
   require_ac_power();need(thermal()<=1,'thermal ceiling');need(swap_mib()-swap<=1024,'swap growth');last=time.monotonic()
 def event(value):events.write(json.dumps(value)+'\n');events.flush();os.fsync(events.fileno())
 try:
  check();require_ac_power();need(torch.backends.mps.is_available(),'MPS required');entry=request['checkpoint'];need(set(entry)=={'file','sha256','bytes'} and checkpoint.FILE_NAME.fullmatch(entry['file']),'checkpoint entry')
  with parent_lock(run):
   ledger=unsigned(run/'campaign.json');identity=json.loads((run/'campaign-spec.json').read_text());need(ledger['spec']==identity and ledger['state']=='paused-milestone' and ledger['trained_tokens']==request['trained_tokens'],'accepted paused milestone')
   need(entry in ledger['checkpoints'] and entry in json.loads((run/'latest.json').read_text()),'committed checkpoint inventory');file=run/entry['file'];need(not file.is_symlink() and file.stat().st_size==entry['bytes'] and sha(file)==entry['sha256'],'checkpoint bytes')
   payload=torch.load(file,map_location='cpu',weights_only=True,mmap=True);need(payload['identity']==identity['identity'] and payload['campaign_id']==ledger['campaign_id'] and payload['trained_tokens']==request['trained_tokens'] and payload['step']==ledger['step'],'checkpoint identity/cursor');need(payload['spec_sha256']==hashlib.sha256(canon(identity)).hexdigest(),'checkpoint immutable spec')
   need(identity['identity']['protocol']['external_milestone_gate']['protocol']==request['protocol'] and request['trained_tokens'] in identity['identity']['protocol']['external_milestone_gate']['milestones'],'checkpoint milestone protocol')
   need(identity['identity']['model']==asdict(Config()) and identity['identity']['initialization']['mode']=='own_pretraining','own-base architecture/lineage');model=GPT2(Config());model.load_state_dict(payload['model'],strict=True);del payload;model=model.to('mps').float().eval()
  corpus=Corpus(foundation['corpus'],foundation['manifest_sha256'],foundation['validation_blocks_sha256'],512,1,device='mps');tok=load();diagnostics=json.loads(Path(foundation['diagnostics']).read_text());need(cost_plan(diagnostics,tok,corpus.blocks)==p['worst_case'],'exact planned accounting');phase='web'
  class Counted(torch.nn.Module):
   def __init__(self,m):super().__init__();self.inner=m;self.positions=m.positions
   def forward(self,x,**kwargs):
    check();mask=kwargs.get('prediction_mask');cost=forward_cost(int(x.shape[0]),int(x.shape[1]),predicted=int(mask.sum().item()) if mask is not None else None,generation=phase=='diagnostics')
    reserve_forward(totals,cost,p['worst_case'])
    event(dict(kind='reserved_forward',phase=phase,cost=cost,cumulative=dict(totals)));y=self.inner(x,**kwargs);event(dict(kind='forward_returned_async',number=totals['forwards']));return y
  counted=Counted(model);losses=document_losses(counted,corpus,check);phase='diagnostics';diag=language_diagnostics(counted,tok,diagnostics,check,completions=True);need(len(losses)==256 and len(diag['pairs'])==32 and len(diag['completions'])==32,'full result inventory');torch.mps.synchronize();check()
  need(sha(file)==entry['sha256'] and sha(Path(pin['path']))==pin['sha256'],'unchanged checkpoint/request');validate(pin)
  result=dict(state='completed_external_language_milestone_not_acceptance',trained_tokens=request['trained_tokens'],request_sha256=pin['sha256'],protocol_sha256=request['protocol']['sha256'],checkpoint=entry,runtime_versions=runtime_versions(),mandatory_ac_power=True,web_document_losses=losses,web_mean_ce=sum(losses)/256,diagnostics=diag,attempted=totals,reserved_worst_case=p['worst_case'],complete=True,training_admitted=False)
 except BaseException as e:failure=dict(type=type(e).__name__,reason=str(e));result=dict(state='incomplete_external_language_milestone',complete=False,failure=failure,attempted=totals,request_sha256=pin['sha256'],protocol_sha256=request['protocol']['sha256'])
 finally:
  events.close();rt.atomic(out/'result.json',result);lock.close()
 if failure:raise RuntimeError(failure)

if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('request');a.add_argument('--request-sha256',required=True);a.add_argument('--worker',action='store_true');a.add_argument('--ticket-fd',type=int);v=a.parse_args();pin=dict(path=str(Path(v.request).resolve()),sha256=v.request_sha256)
 if v.worker:worker(pin,v.ticket_fd)
 else:print(json.dumps(launch(pin)))
