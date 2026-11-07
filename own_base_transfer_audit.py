"""Frozen teacher-prefix/local-user-conditioning diagnostic. No training or broker dispatch."""
import argparse,copy,hashlib,json,os,re,sys,time,fcntl,subprocess
from pathlib import Path
import own_base_dev_run as runtime
ROOT=Path(__file__).resolve().parent
SEED='grounded-transfer-48-v1'
ROLE_PATHS={'chat':'grounded-chat-aligned-v1','primary_tool':'grounded-tool-aligned-v2','four_call_extension':'grounded-session-aligned-v2'}
REPORT=ROOT/'reports/grounded-transfer-audit-v1'
RUNTIME=tuple(sorted(set(runtime.RUNTIME+('own_base_transfer_audit.py','own_base_sft_rows.py','own_base_sft_train.py','verify_own_base_transfer_audit.py','reports/grounded-transfer-audit-v1/PROTOCOL.md'))))

def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def pin(p):return {'path':str(Path(p).resolve()),'sha256':runtime.checksum(p)}
def require(x,message):
 if not x:raise ValueError(message)

def select_ids(rows,role,split):
 ids={r['doc_id']for r in rows};require(len(ids)>=8,'eight distinct histories required')
 return sorted(ids,key=lambda d:(hashlib.sha256(f'{SEED}|{role}|{split}|{d}'.encode()).hexdigest(),d))[:8]

def decode_history(tok,inputs,labels):
 from tokenizer import EOT
 require(labels[-1]==EOT,'terminal EOT target missing')
 ids=list(inputs)+[EOT];history=[];start=0
 for end,token in enumerate(ids):
  if token!=EOT:continue
  text=tok.decode(ids[start:end]);header,body=text.split('\n',1);role=header[1:-1];payload=json.loads(body)
  require(header==f'[{role}]' and role in ('system','user','assistant','tool'),'invalid frame')
  if role=='tool':
   require(history and 'call' in history[-1],'unbound tool');history[-1]['call_id']=payload['call_id'];message={'role':role,'record':payload}
  else:message={'role':role,**payload}
  history.append(message);start=end+1
 require(start==len(ids),'unterminated frame')
 from own_base_sft_rows import last_turn_row
 rebuilt=last_turn_row(tok,history)
 require(rebuilt.inputs==list(inputs) and rebuilt.labels==list(labels),'packed row reconstruction mismatch')
 return history

def encode_case(tok,history,donor_text):
 from dialogue import assistant_prompt,_frames
 from own_base_sft_rows import last_turn_row
 user=max(i for i,m in enumerate(history)if m['role']=='user');first=user+1
 require(history[first]['role']=='assistant','first current assistant missing')
 changed=copy.deepcopy(history);changed[user]['text']=donor_text
 rows=[]
 for h in (history,changed):
  row=last_turn_row(tok,h);groups={};observed=False
  for i in range(first,len(h)):
   if h[i]['role']=='tool':observed=True
   if h[i]['role']!='assistant':continue
   p=assistant_prompt(tok,h[:i],reply_budget=256);end=len(_frames(tok,h[:i+1])[0]);category=('conditioned_call' if observed else 'first_call') if 'call' in h[i] else ('teacher_observed_readback' if observed else 'text_without_current_observation')
   groups.setdefault(category,[]).extend(range(len(p)-1,end-1))
  require(sorted(j for g in groups.values()for j in g)==[i for i,y in enumerate(row.labels)if y!=-100],'category masks differ')
  rows.append(dict(inputs=row.inputs,labels=row.labels,groups=groups))
 require([y for y in rows[0]['labels']if y!=-100]==[y for y in rows[1]['labels']if y!=-100],'swap changed targets')
 prefix=assistant_prompt(tok,history[:first],reply_budget=256)
 expected={k:v for k,v in history[first].items()if k not in ('role','call_id')}
 return dict(history=history,current_user_index=user,prefix=prefix,expected_first_frame=expected,correct=rows[0],swapped=rows[1],swap_equal=history[user]['text']==donor_text)

def prepare():
 from tokenizer import load
 from own_base_sft_train import Streams
 tok=load();cases=[];pins={};selection=[]
 for role,name in ROLE_PATHS.items():
  directory=ROOT/'data'/name;receipt=pin(directory/'receipt.json');data=Streams(receipt,development_split='exposed-development')
  for file in directory.iterdir():
   if file.is_file():pins[str(file.relative_to(ROOT))]=runtime.checksum(file)
  for split in ('train','validation'):
   rows=data.rows[split];chosen=select_ids(rows,role,split);groups={d:[]for d in chosen}
   for i,r in enumerate(rows):
    if r['doc_id'] in groups:
     x,y=data.row(split,i);groups[r['doc_id']].append((r,decode_history(tok,x.tolist(),y.tolist())))
   selection.append(dict(role=role,split=split,doc_ids=chosen))
   for rank,d in enumerate(chosen):
    donor=chosen[(rank+1)%8];donor_rows=groups[donor]
    for r,h in groups[d]:
     # Fixed donor first current-user text; no fit-dependent replacement.
     dh=donor_rows[0][1];du=max(i for i,m in enumerate(dh)if m['role']=='user')
     case=encode_case(tok,h,dh[du]['text']);case.update(role=role,split=split,doc_id=d,turn=r['turn'],family=r['family'],donor_doc_id=donor,donor_turn=donor_rows[0][0]['turn'],packed_index=r)
     cases.append(case)
 require(len(cases)<=144,'fixed row cap; refuse rather than replace')
 payload=dict(schema=1,seed=SEED,selection=selection,cases=cases,input_sha256=pins,scope='teacher-prefix single-next-frame and local current-user swap; not autonomous rollout or acceptance')
 REPORT.mkdir(exist_ok=True);path=REPORT/'selection.json';require(not path.exists(),'selection immutable');path.write_text(json.dumps(payload,indent=2)+'\n')
 old=json.loads((ROOT/'reports/grounded-dev-evaluation-v1/activation.json').read_text());caps=copy.deepcopy(old['budgets']);caps.update(wall_seconds=1200,heartbeat_seconds=90,termination_grace_seconds=10,max_frames=len(cases),max_reserved_generation_tokens=len(cases)*256,max_reserved_input_positions=len(cases)*sum(768+i for i in range(256)),max_reserved_attention_cells=len(cases)*sum((768+i)**2 for i in range(256)),max_actual_generated_tokens=len(cases)*256,max_output_bytes=128*1024**2)
 ce=dict(forwards=2*len(cases),input_positions=sum(len(c[v]['inputs'])for c in cases for v in ('correct','swapped')),attention_cells=sum(len(c[v]['inputs'])**2 for c in cases for v in ('correct','swapped')))
 spec=dict(schema=1,state='pending_root_review',selection=pin(path),candidate=old['candidate'],runtime_sha256={n:runtime.checksum(ROOT/n)for n in RUNTIME},budgets=caps,ce_limits=ce,output=str(ROOT/'runs/grounded-transfer-audit-01'),stop_paths=list(dict.fromkeys(old['stop_paths']+[str(ROOT/'runs/grounded-transfer-audit-01/STOP')])) )
 (REPORT/'activation-draft.json').write_text(json.dumps(spec,indent=2)+'\n');print(dict(histories=48,rows=len(cases),ce=ce,selection=pin(path)))

def validate(spec,*,reviewed=True):
 require(spec['schema']==1 and spec['state']==('reviewed_for_transfer_audit' if reviewed else 'pending_root_review'),'review state')
 out=Path(spec['output']);require(out==ROOT/'runs/grounded-transfer-audit-01' and not out.is_symlink(),'fixed audit output')
 b=spec['budgets'];require(b['wall_seconds']==1200 and b['termination_grace_seconds']==10 and 0<b['heartbeat_seconds']<=90,'hard time limits')
 require(0<b['max_frames']<=144 and b['max_reserved_generation_tokens']==256*b['max_frames'] and b['max_actual_generated_tokens']==256*b['max_frames'],'generation limits')
 require(b['max_reserved_input_positions']<=144*sum(768+i for i in range(256)) and b['max_reserved_attention_cells']<=144*sum((768+i)**2 for i in range(256)),'input compute caps')
 require(b['max_rss_bytes']<=18*1024**3 and b['max_swap_growth_bytes']<=1024**3 and b['min_free_disk_bytes']>=20*1024**3 and runtime.RESERVED_BYTES*2<=b['max_output_bytes']<=128*1024**2 and b['max_thermal_state']<=1,'resource caps')
 require(str(ROOT/'runs/STOP')in spec['stop_paths'] and str(out/'STOP')in spec['stop_paths'],'STOP inheritance')
 require(spec['candidate']==json.loads((ROOT/'reports/grounded-dev-evaluation-v1/activation.json').read_text())['candidate'],'existing grounded candidate only')
 require(set(spec['runtime_sha256'])==set(RUNTIME),'runtime pins required')
 for n,h in spec['runtime_sha256'].items():require(runtime.checksum(ROOT/n)==h,'runtime changed: '+n)
 require(Path(spec['selection']['path'])==REPORT/'selection.json' and runtime.checksum(spec['selection']['path'])==spec['selection']['sha256'],'selection changed')
 data=json.loads(Path(spec['selection']['path']).read_text());validate_selection(data,spec)
 return spec

def validate_selection(data,spec):
 require(data['seed']==SEED and len(data['selection'])==6,'fixed selection identity')
 require({(x['role'],x['split'])for x in data['selection']}=={(r,s)for r in ROLE_PATHS for s in ('train','validation')},'six strata')
 require(all(len(x['doc_ids'])==8 and len(set(x['doc_ids']))==8 for x in data['selection']),'48 distinct stratum histories')
 expected={(x['role'],x['split'],d)for x in data['selection']for d in x['doc_ids']}
 require({(c['role'],c['split'],c['doc_id'])for c in data['cases']}==expected,'case selection coverage')
 require(len({(c['role'],c['split'],c['doc_id'],c['turn'])for c in data['cases']})==len(data['cases'])==spec['budgets']['max_frames'],'unique row count')
 limits=dict(forwards=2*len(data['cases']),input_positions=0,attention_cells=0)
 for c in data['cases']:
  require(0<len(c['prefix'])<=768,'full reply reserve')
  for variant in ('correct','swapped'):
   row=c[variant];n=len(row['inputs']);require(0<n<=1024 and n==len(row['labels']),'row bounds');require(all(type(x)==int and 0<=x<=50256 for x in row['inputs']),'input IDs');require(all(type(x)==int and (x==-100 or 0<=x<=50256)for x in row['labels']),'label IDs')
   require(sorted(i for v in row['groups'].values()for i in v)==[i for i,y in enumerate(row['labels'])if y!=-100],'exact CE masks')
   limits['input_positions']+=n;limits['attention_cells']+=n*n
 require(limits==spec['ce_limits'],'exact CE caps')

def ce(model,row,device):
 import torch
 import torch.nn.functional as F
 x=torch.tensor([row['inputs']],device=device);y=torch.tensor(row['labels'],device=device);mask=y!=-100
 with torch.inference_mode():
  values=F.cross_entropy(model(x,prediction_mask=mask[None]),y[mask],reduction='none').float()
 require(bool(torch.isfinite(values).all()),'nonfinite CE')
 order=[i for i,t in enumerate(row['labels'])if t!=-100];lookup={p:i for i,p in enumerate(order)}
 return {name:dict(targets=len(indices),loss_sum=float(values[[lookup[i]for i in indices]].sum().item()))for name,indices in row['groups'].items()}

def worker(path,expected,ticket):
 require(runtime.checksum(path)==expected,'spec changed');spec=validate(json.loads(Path(path).read_text()));out=Path(spec['output']);meta=json.loads((out/'launch.json').read_text())
 require(meta['parent_pid']==os.getppid() and meta['nonce']==ticket['nonce'] and ticket['spec_sha256']==expected and ticket['deadline']-ticket['wall_started']==1200,'watchdog ownership')
 journal=runtime.Journal(out/'events.jsonl',spec['budgets']['max_output_bytes']-runtime.RESERVED_BYTES);budget=runtime.Budget(spec['budgets'],journal);lock=(ROOT/'runs/mps.lock').open('a+');counts=dict(forwards=0,input_positions=0,attention_cells=0);completed=0
 try:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);guard=runtime.RunGuard(spec,out,meta['started'],journal);guard.check(force=True)
  data=json.loads(Path(spec['selection']['path']).read_text())
  for n,h in data['input_sha256'].items():require(runtime.checksum(ROOT/n,guard.check)==h,'source changed')
  from own_base_sft_export import load_candidate
  state,manifest=load_candidate(spec['candidate']['manifest'],spec['candidate']['manifest_sha256'],check=guard.check)
  require(str(Path(manifest['source']['run'])/'STOP')in spec['stop_paths'],'candidate source STOP required')
  import torch
  from gpt2 import GPT2,Config
  from tokenizer import load
  from dialogue import parse_assistant
  require(torch.backends.mps.is_available(),'MPS unavailable; no fallback');torch.set_num_threads(1)
  model=GPT2(Config(**manifest['model_config']));model.load_state_dict(state,strict=True);del state
  model=model.to(device='mps',dtype=torch.float32).eval();tok=load()
  for case in data['cases']:
   identity={k:case[k]for k in ('role','split','doc_id','turn','family','donor_doc_id','donor_turn')};journal.emit('case_started',identity=identity)
   results={}
   for variant in ('correct','swapped'):
    guard.check();row=case[variant];n=len(row['inputs']);proposed={k:counts[k]+v for k,v in dict(forwards=1,input_positions=n,attention_cells=n*n).items()}
    require(all(proposed[k]<=spec['ce_limits'][k]for k in counts),'CE budget exhausted');journal.emit('ce_reserved',identity=identity,variant=variant,counters=proposed);counts=proposed
    results[variant]=ce(model,row,'mps');torch.mps.synchronize();journal.emit('ce_observed',identity=identity,variant=variant,result=results[variant])
   ids=runtime.bounded_greedy(model,case['prefix'],256,guard,budget)
   try:parsed=parse_assistant(tok,ids);failure=None
   except (ValueError,TypeError,UnicodeError)as error:parsed=None;failure=str(error)
   journal.emit('case_completed',identity=identity,ce=results,raw=tok.decode(ids),generated_ids=ids,parsed=parsed,protocol_failure=failure,exact_teacher_frame_match=parsed==case['expected_first_frame'],swap_equal=case['swap_equal'],interpretation='teacher-prefix frame; no tool dispatched; not acceptance')
   completed+=1
  runtime.write_terminal(out,'worker-terminal.json',dict(state='completed_transfer_audit_not_acceptance',completed_rows=completed,planned_histories=48,planned_rows=len(data['cases']),ce_reserved=counts,generation=budget.counts),spec['budgets']['max_output_bytes']);return 0
 except BaseException as error:
  runtime.incomplete_terminal(out,error,dict(generation=budget.counts,ce_reserved=counts,completed_rows=completed),budget.pending,spec['budgets']['max_output_bytes']);return 2
 finally:lock.close();journal.close()

def launch(path,expected):
 wall=time.time();mono=time.monotonic();require(runtime.checksum(path)==expected,'mandatory spec hash');spec=validate(json.loads(Path(path).read_text()));out=Path(spec['output']);ticket=runtime.make_ticket(1200,expected);ticket.update(wall_started=wall,monotonic_started=mono,deadline=wall+1200)
 out.mkdir(exist_ok=False);runtime.atomic(out/'launch.json',dict(started=wall,parent_pid=os.getpid(),nonce=ticket['nonce']));runtime.atomic(out/'spec.json',spec)
 def swap(timeout):
  text=subprocess.check_output(['sysctl','-n','vm.swapusage'],text=True,timeout=timeout);m=re.search(r'used = ([\d.]+)([KMG])',text);require(m,'swap telemetry');return float(m[1])*{'K':1024,'M':1024**2,'G':1024**3}[m[2]]
 try:
  baseline=swap(.5);last=-float('inf')
  def check(pid,available):
   nonlocal last
   require(not any(Path(p).exists()for p in spec['stop_paths']),'STOP');runtime.check_storage(spec)
   if time.monotonic()-last>=1:
    last=time.monotonic();thermal=runtime.apple_thermal();require(thermal in range(4) and thermal<=spec['budgets']['max_thermal_state'],'thermal');require(swap(min(.5,max(.01,available)))-baseline<=spec['budgets']['max_swap_growth_bytes'],'swap growth')
  result=runtime.supervise(lambda fd:[sys.executable,str(Path(__file__).resolve()),'_worker',str(Path(path).resolve()),'--expected-spec-sha256',expected,'--worker-fd',str(fd)],out,ticket=ticket,heartbeat_seconds=spec['budgets']['heartbeat_seconds'],grace_seconds=10,max_rss_bytes=spec['budgets']['max_rss_bytes'],check=check)
  p=out/'worker-terminal.json';terminal=json.loads(p.read_text())if p.exists()else None
  complete=result['exit_code']==0 and not result['watchdog_reason'] and result['within_deadline'] and terminal and terminal['state']=='completed_transfer_audit_not_acceptance' and terminal['completed_rows']==spec['budgets']['max_frames'] and runtime.remaining(ticket)>0
  runtime.write_terminal(out,'terminal.json',dict(state='completed_transfer_audit_not_acceptance'if complete else'incomplete',watchdog=result,worker_terminal=terminal,hardkill_ram_unknown=True),spec['budgets']['max_output_bytes']);return 0 if complete else 2
 except BaseException as error:
  runtime.write_terminal(out,'terminal.json',dict(state='incomplete',error_type=type(error).__name__,error=str(error)[:4096]),spec['budgets']['max_output_bytes']);return 2

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('prepare','run','_worker'));p.add_argument('spec',nargs='?');p.add_argument('--expected-spec-sha256');p.add_argument('--worker-fd',type=int);a=p.parse_args()
 if a.mode=='prepare':prepare()
 else:
  require(a.spec and a.expected_spec_sha256,'explicit spec and hash required')
  sys.exit(worker(a.spec,a.expected_spec_sha256,runtime.consume_ticket(a.worker_fd))if a.mode=='_worker'else launch(a.spec,a.expected_spec_sha256))
