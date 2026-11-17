"""Fetch only immutable completed probe outputs and terminal training evidence."""
import base64,hashlib,json,subprocess,shlex
from pathlib import Path
P=Path(__file__).resolve().parent;D=P/'assessment';D.mkdir(exist_ok=True)
code='''import base64,hashlib,json
from pathlib import Path
R=Path('/opt/english-eager');B=R/'runs/ganesh-recovery-next';files={}
def add(p,key):
 b=p.read_bytes();files[key]={'sha256':hashlib.sha256(b).hexdigest(),'base64':base64.b64encode(b).decode()}
for n in ('result.json','updates.jsonl','quality-preflight.json','retention-journal.json'):
 p=B/'fit'/n
 if p.exists():add(p,'training/'+n)
add(B/'controller/state.json','original-controller-state.json')
index=B/'fit_probes-receipt.json'
if index.exists():
 j=json.loads(index.read_text());add(index,'fit_probes-receipt.json')
 for item in j['candidates']:
  p=R/item['path'];assert p.resolve().is_relative_to(B/'fit-probes');assert hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256'];add(p,'raw/'+p.name)
for name in ('pilot-request.json','pilot-control-backup.json','qualification-finalization/qualification.json','qualification-finalization/backup.json','pilot-evidence/measured-schedule-review.json'):
 p=R/name
 if p.exists():add(p,'controls/'+p.name)
print(json.dumps(files))'''
r=subprocess.run(['gcloud','compute','ssh','ganesh-a100-1117-203113','--project=executespecv1','--zone=us-central1-c','--tunnel-through-iap','--quiet','--command=sudo python3 -c '+shlex.quote(code)],capture_output=True,text=True,timeout=120);assert r.returncode==0,r.stderr
files=json.loads(r.stdout)
for name,entry in files.items():
 p=D/name;p.parent.mkdir(parents=True,exist_ok=True);b=base64.b64decode(entry['base64']);assert hashlib.sha256(b).hexdigest()==entry['sha256']
 if name.startswith('raw/') and p.exists():assert p.read_bytes()==b,'Completed raw output changed'
 p.write_bytes(b)
(D/'fetch-hashes.json').write_text(json.dumps({n:e['sha256'] for n,e in files.items()},indent=2)+'\n')
print(json.dumps({'raw_files':[n for n in files if n.startswith('raw/')],'training_reason':json.loads((D/'training/result.json').read_text())['reason']}))
