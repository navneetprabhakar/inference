"""Read-only raw English training/probe progress; never grades output from loss."""
import json,subprocess,shlex
from pathlib import Path
P=Path(__file__).resolve().parent
code='''import json,datetime
from pathlib import Path
R=Path('/opt/english-eager/runs/ganesh-recovery-next');o={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'training':{},'probes':{}}
s=R/'controller/state.json'
if s.exists():
 j=json.loads(s.read_text());o['controller']={k:j.get(k) for k in ('running','failed')};o['controller']['completed']=list(j['completed'])
for name in ('fit','curriculum'):
 p=R/name/'progress.json'
 if p.exists():
  j=json.loads(p.read_text());o['training'][name]={k:j.get(k) for k in ('step','status','train_loss','assistant_targets','update_seconds','development','quality_stop_families')}
 p=R/name/'result.json'
 if p.exists():
  j=json.loads(p.read_text());o['training'].setdefault(name,{}).update({k:j.get(k) for k in ('status','reason','step','best_development_step','best_development_loss','quality_accepted')})
for name in ('fit-probes','curriculum-probes'):
 for p in (R/name).glob('*.json'):
  j=json.loads(p.read_text());o['probes'][p.name]={'status':j.get('status'),'turns':len(j.get('records',[]))}
o['assessment_complete']=Path('/opt/english-eager/stopped-fit-assessment/complete.json').exists()
print(json.dumps(o,indent=2))'''
r=subprocess.run(['gcloud','compute','ssh','ganesh-a100-1117-203113','--project=executespecv1','--zone=us-central1-c','--tunnel-through-iap','--quiet','--command=sudo python3 -c '+shlex.quote(code)],capture_output=True,text=True,timeout=90)
(P/'english-monitor.log').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stderr;j=json.loads(r.stdout);(P/'english-latest.json').write_text(json.dumps(j,indent=2)+'\n');print(json.dumps(j,indent=2))
