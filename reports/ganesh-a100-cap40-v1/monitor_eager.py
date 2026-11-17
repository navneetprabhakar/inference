"""Read-only compact active-worker evidence via IAP."""
import json,subprocess,shlex
from pathlib import Path
P=Path(__file__).resolve().parent;state=json.loads((P/'zone-sweep.json').read_text());a=next(a for a in state['attempts'] if a['status']=='allocated_monitor_qualification');A=P/'eager-qualification'
code='''import json,datetime
from pathlib import Path
r=Path('/opt/english-eager/results');out={'checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'branches':{}}
for p in r.glob('*/progress.json'):
 j=json.loads(p.read_text());out['branches'][p.parent.name]={k:j.get(k) for k in ('status','step','reason','train_loss','dev_loss','assistant_targets')};out['branches'][p.parent.name]['checkpoint_dirs']=[x.name for x in p.parent.glob('step-*')]
for p in r.glob('*/result.json'):
 j=json.loads(p.read_text());out['branches'].setdefault(p.parent.name,{}).update({k:j.get(k) for k in ('status','step','reason')});out['branches'][p.parent.name]['result_written']=True
for name in ('qualification.json','normal-comparison.json','normal-comparison-supplemental.json','capture-comparison.json','replay-comparison.json','signal-comparison.json','decode-benchmark.json'):
 p=r/name
 if p.exists():out[name]=json.loads(p.read_text())
for name in ('normal-stop-ready','backup-failure.txt'):
 p=Path('/opt/english-eager')/name
 if p.exists():out[name]=p.read_text()
print(json.dumps(out,indent=2))'''
cmd='sudo python3 -c '+shlex.quote(code)
r=subprocess.run(['gcloud','compute','ssh',a['name'],'--zone='+a['zone'],'--project=executespecv1','--tunnel-through-iap','--quiet','--command='+cmd],capture_output=True,text=True,timeout=90)
(A/'monitor-latest.txt').write_text(r.stdout+r.stderr)
if r.returncode:print(r.stderr[-1500:]);raise SystemExit(r.returncode)
j=json.loads(r.stdout);(A/'worker-latest.json').write_text(json.dumps(j,indent=2)+'\n');print(json.dumps(j,indent=2))
