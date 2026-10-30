"""Four authorized 5M-input-token arms; local-only; stop for review."""
import argparse,fcntl,hashlib,json,os,signal,subprocess,sys,time
from pathlib import Path
from train_local import atomic_json
from sft_common import ROOT
OUT=ROOT/'runs/sft-v2';REPORT=ROOT/'reports/sft-v2';ARMS=[('100m',1e-5),('100m',3e-5),('200m',1e-5),('200m',3e-5)]
CHILD=None
STOP=False
def stop(*_):
 global STOP
 STOP=True
 if CHILD is not None and CHILD.poll() is None:CHILD.terminate()
def latest(p):return p/json.loads((p/'latest.json').read_text())['directory']
def main(resume=False):
 global CHILD
 signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop);OUT.mkdir(exist_ok=True);REPORT.mkdir(exist_ok=True)
 lock=(OUT/'.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 cp=OUT/'campaign.json';old=json.loads(cp.read_text()) if cp.exists() else None
 if old and not resume:raise RuntimeError('Existing experiment; inspect and use --resume')
 names=['run_sft_experiment.py','train_sft.py','evaluate_sft.py','sft_common.py','benchmark_mlx.py','train_local.py','evaluate_pilot.py']
 pins={n:hashlib.sha256((ROOT/'scripts'/n).read_bytes()).hexdigest() for n in names};data_hash=hashlib.sha256((ROOT/'data/sft-v2/manifest.json').read_bytes()).hexdigest()
 if old:assert old['code_pins']==pins and old['data_sha256']==data_hash,'Do not change pinned experiment on resume'
 bases={'100m':latest(ROOT/'runs/local-campaign-v1/pilot'),'200m':latest(ROOT/'runs/continuation-v1/200m')};base_hashes={k:hashlib.sha256((v/'model.safetensors').read_bytes()).hexdigest() for k,v in bases.items()}
 for k,v in bases.items():assert json.loads((v/'state.json').read_text())['tokens']==int(k[:-1])*1000000
 state={'status':'preparing','pid':os.getpid(),'started_at':time.time(),'code_pins':pins,'data_sha256':data_hash,'base_hashes':base_hashes,'authorized_arms':4,'input_token_cap_per_arm':5000000,'aggregate_sft_input_token_ceiling':20000000,'completed_arms':[],'cloud_spend_usd':0,'paid_api_spend_usd':0,'power_policy':'continue_on_battery','stop_after':'four arms and evaluations; awaiting user review'}
 def write():state['updated_at']=time.time();atomic_json(cp,state)
 def invoke(args,log):
  global CHILD
  if STOP or (OUT/'STOP').exists():raise RuntimeError('Stopped by user')
  assert all(hashlib.sha256((ROOT/'scripts'/n).read_bytes()).hexdigest()==h for n,h in pins.items())
  log.parent.mkdir(parents=True,exist_ok=True)
  with log.open('a') as f:
   CHILD=subprocess.Popen([sys.executable,'-u',*map(str,args)],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT);state['child_pid']=CHILD.pid;write();rc=CHILD.wait()
  if rc:raise RuntimeError(f'Child failed or stopped ({rc}): {args[0]}')
 def evaluate(checkpoint,stage,mode,out,config=None):
  if (out/'completed.json').exists():
   saved=json.loads((out/'completed.json').read_text());assert saved['complete'] and saved['model_sha256']==hashlib.sha256((checkpoint/'model.safetensors').read_bytes()).hexdigest();return
  state.update(status='evaluating',stage=stage,evaluation_mode=mode);write();args=[ROOT/'scripts/evaluate_sft.py','--checkpoint',checkpoint,'--stage',stage,'--mode',mode,'--output',out]
  if config:args+=['--config',config]
  invoke(args,OUT/(stage+'-'+mode+'.log'))
 write()
 for name,base in bases.items():
  evaluate(base,'base-'+name,'sweep',REPORT/('base-'+name)/'decoding')
  evaluate(base,'base-'+name,'final',REPORT/('base-'+name)/'final',REPORT/('base-'+name)/'decoding/selected.json')
 for base,lr in ARMS:
  name=base+('-lr1e-5' if lr==1e-5 else '-lr3e-5');stage=OUT/name
  state.update(status='training',stage=name,evaluation_mode=None);write()
  if not (stage/'result.json').exists():
   args=[ROOT/'scripts/train_sft.py','--checkpoint',bases[base],'--lr',lr,'--output',stage]
   if (stage/'latest.json').exists():args+=['--resume']
   invoke(args,stage/'console.log')
  result=json.loads((stage/'result.json').read_text());assert result['status']=='completed' and result['tokens']==5000000
  for tokens in [1000000,3000000]:evaluate(stage/'milestones'/str(tokens),name+f'-{tokens//1000000}m','milestone',REPORT/name/f'{tokens//1000000}m')
  model=stage/'milestones/5000000';evaluate(model,name,'sweep',REPORT/name/'decoding');evaluate(model,name,'final',REPORT/name/'final',REPORT/name/'decoding/selected.json');state['completed_arms'].append(name);write()
 assert all(hashlib.sha256((v/'model.safetensors').read_bytes()).hexdigest()==base_hashes[k] for k,v in bases.items()),'Frozen base changed'
 summary={};lines=['# Bounded four-arm SFT comparison','','All training has stopped. Each arm consumed exactly 5M processed input slots, including padding; no model was extended beyond its SFT budget. No cloud or paid APIs.','','Raw local fixture metrics are not broad tool capability scores. Chat quality needs human review. Primary comparisons use common greedy decoding with penalty 1.2. Development sweeps are exploratory only.','']
 for name in ['base-100m','base-200m']+state['completed_arms']:
  report=json.loads((REPORT/name/'final/metrics.json').read_text());summary[name]=report;lines += [f'## {name}','','```json',json.dumps({'config':report['config'],'metrics':report['metrics']},indent=2),'```','',f'[All actual outputs]({name}/final/REPORT.md)','']
  rows=json.loads((REPORT/name/'final/generations.json').read_text());chosen=[]
  for kind in ['chat','grounded','single','clarify','none','chain','error']:chosen.extend([x for x in rows if x['kind']==kind][:2])
  for row in chosen:
   lines += [f"### {row['id']}",'','```text',row['prompt'],'```']
   for g in row['generations']:lines+=['```text',g['output'],'```']
 atomic_json(REPORT/'comparison.json',summary);(REPORT/'REPORT.md').write_text('\n'.join(lines)+'\n');state.update(status='awaiting_user_review',finished_at=time.time(),trained_sft_input_tokens=20000000,final_report=str(REPORT/'REPORT.md'),base_checkpoints_unchanged=True);write()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--resume',action='store_true');args=p.parse_args()
 try:main(args.resume)
 except Exception as e:
  atomic_json(OUT/'error.json',{'error':repr(e),'time':time.time()});p=OUT/'campaign.json'
  if p.exists():s=json.loads(p.read_text());s.update(status='stopped',error=repr(e));atomic_json(p,s)
  raise
