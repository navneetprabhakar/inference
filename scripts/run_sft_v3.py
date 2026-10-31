"""Two capped local repair arms, dev-only selection, one test release, then stop."""
import fcntl,hashlib,html,json,os,signal,subprocess,sys,time
from pathlib import Path
from sft_common import ROOT
from train_local import atomic_json
from select_sft_v3 import rank,POLICY
OUT=ROOT/'runs/sft-v3';REPORT=ROOT/'reports/sft-v3/experiment';CHILD=None;STOP=False
NAMES=['run_sft_v3.py','train_sft_v3.py','evaluate_sft_v3.py','select_sft_v3.py','sft_v3.py','sft_common.py','train_local.py','benchmark_mlx.py','evaluate_pilot.py','blind_sft_review.py']
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def stop(*_):
 global STOP
 STOP=True
 if CHILD is not None and CHILD.poll() is None:CHILD.terminate()
def main():
 global CHILD
 signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop);OUT.mkdir(exist_ok=True);REPORT.mkdir(parents=True,exist_ok=True)
 lock=(OUT/'.campaign.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 cfgpath=ROOT/'configs/sft_v3_prepared.json';cfg=json.loads(cfgpath.read_text());assert cfg['training_authorized_tokens']==4000000
 pins={n:digest(ROOT/'scripts'/n) for n in NAMES};config_hash=digest(cfgpath);data_hash=digest(ROOT/'data/sft-v3/manifest.json');cp=OUT/'campaign.json'
 bases={'reference-lr1':ROOT/'runs/sft-v2/100m-lr1e-5/milestones/5000000','reference-lr3':ROOT/'runs/sft-v2/100m-lr3e-5/milestones/5000000'};base=bases['reference-lr3'];base_hashes={k:digest(v/'model.safetensors') for k,v in bases.items()}
 state=json.loads(cp.read_text()) if cp.exists() else {'started_at':time.time(),'code_pins':pins,'config_sha256':config_hash,'data_sha256':data_hash,'base_hashes':base_hashes,'completed_training_arms':[],'training_limit_per_arm':2000000,'aggregate_training_limit':4000000,'cloud_spend_usd':0,'paid_api_spend_usd':0}
 assert state['code_pins']==pins and state['config_sha256']==config_hash and state['data_sha256']==data_hash and state['base_hashes']==base_hashes
 state.update(pid=os.getpid(),error=None)
 def save():state['updated_at']=time.time();atomic_json(cp,state)
 def invoke(args,log):
  global CHILD
  if STOP or (OUT/'STOP').exists():raise RuntimeError('Stopped; no further jobs launched')
  assert all(digest(ROOT/'scripts'/n)==v for n,v in pins.items()) and digest(cfgpath)==config_hash
  log.parent.mkdir(parents=True,exist_ok=True)
  with log.open('a') as f:
   CHILD=subprocess.Popen([sys.executable,'-u',*map(str,args)],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT);state['child_pid']=CHILD.pid;save();rc=CHILD.wait()
  if rc:raise RuntimeError(f'Child exited {rc}: {args[0]}')
 def evaluate(name,checkpoint,split):
  out=REPORT/name/split;p=out/'metrics.json'
  if p.exists():
   d=json.loads(p.read_text());assert d['model_sha256']==digest(checkpoint/'model.safetensors') and d['data_sha256']==data_hash;return d
  state.update(status='evaluating',stage=name,split=split);save();args=[ROOT/'scripts/evaluate_sft_v3.py','--checkpoint',checkpoint,'--output',out,'--split',split]
  if split=='test':args+=['--unlock-test']
  invoke(args,OUT/(name+'-'+split+'.log'));return json.loads(p.read_text())
 try:
  candidates={}
  for name,lr in [('repair-lr1',1e-5),('repair-lr3',3e-5)]:
   arm=OUT/name
   if not (arm/'result.json').exists():
    state.update(status='training',stage=name,split=None);save();args=[ROOT/'scripts/train_sft_v3.py','--checkpoint',base,'--output',arm,'--lr',lr]
    if (arm/'latest.json').exists():args+=['--resume']
    invoke(args,arm/'console.log')
   result=json.loads((arm/'result.json').read_text());assert result['status']=='completed' and result['tokens']==2000000 and result['base_model_sha256']==base_hashes['reference-lr3']
   if name not in state['completed_training_arms']:state['completed_training_arms'].append(name)
   for tokens in [1000000,2000000]:
    key=name+f'-{tokens//1000000}m';model=arm/'milestones'/str(tokens);d=evaluate(key,model,'dev');candidates[key]={'checkpoint':model,'report':d,'tokens':tokens,'lr':lr}
  baseline_reports={n:evaluate(n,p,'dev') for n,p in bases.items()}
  ranking=[]
  for name,item in candidates.items():ranking.append({'name':name,'checkpoint':str(item['checkpoint']),'tokens':item['tokens'],'lr':item['lr'],**rank(item['report'],baseline_reports['reference-lr3'])})
  ranking.sort(key=lambda x:(x['eligible'],x['score'],-x['chat_repetition'],-x['tokens'],-x['lr']),reverse=True);selected=ranking[0]
  release={'selected':selected,'ranking':ranking,'policy':POLICY,'reference_hashes':base_hashes,'data_sha256':data_hash,'selection_used_test':False}
  release_path=REPORT/'selection.json'
  if release_path.exists():assert json.loads(release_path.read_text())==release,'Frozen release changed'
  else:atomic_json(release_path,release)
  state.update(status='test_release',selected=selected);save()
  test_reports={'selected':evaluate(selected['name'],Path(selected['checkpoint']),'test')}
  for name,path in bases.items():test_reports[name]=evaluate(name,path,'test')
  all_names=[selected['name'],*bases]
  invoke([ROOT/'scripts/blind_sft_review.py',*[REPORT/n/'test/generations.json' for n in all_names],'--output',REPORT/'blind-review'],OUT/'blind-review.log')
  assert all(digest(path/'model.safetensors')==base_hashes[name] for name,path in bases.items())
  summary={'selection':release,'fresh_test':test_reports,'trained_input_slots':4000000,'stop':'awaiting_user_review','human_quality_review':'pending','note':'Fresh test is one fixed release for the dev-selected candidate and two frozen references. No automatic extension or promotion.'};atomic_json(REPORT/'comparison.json',summary)
  body='<meta charset="utf-8"><title>Bounded SFT repair comparison</title><style>body{font:16px/1.5 system-ui;max-width:1050px;margin:40px auto}pre{white-space:pre-wrap;background:#eee;padding:15px}</style><h1>Repair experiment complete — stopped for review</h1><p>4M additional input slots total. No cloud or paid APIs. Selection used development data only. Chat quality awaits blind review.</p><pre>'+html.escape(json.dumps(release,indent=2))+'</pre>'
  for label,d in test_reports.items():
   name=selected['name'] if label=='selected' else label;body+='<h2>'+label+'</h2><pre>'+html.escape(json.dumps({'metrics':d['metrics'],'retention':d['language_retention']},indent=2))+'</pre>'
   rows=json.loads((REPORT/name/'test/generations.json').read_text())
   for kind in ['chat','single','chain','clarify','result','grounded','error','none']:
    for r in [r for r in rows if r['kind']==kind][:2]:body+='<pre>'+html.escape(json.dumps({'id':r['id'],'prompt':r['prompt'],'reference':r['reference'],'outputs':[g['output'] for g in r['generations']]},indent=2))+'</pre>'
  (REPORT/'REPORT.html').write_text(body);state.update(status='awaiting_user_review',finished_at=time.time(),trained_input_slots=4000000,final_report=str(REPORT/'REPORT.html'));save();(OUT/'STOP').write_text('Bounded experiment complete. Review required before further training.\n')
 except Exception as e:state.update(status='stopped',error=repr(e));save();raise
if __name__=='__main__':main()
