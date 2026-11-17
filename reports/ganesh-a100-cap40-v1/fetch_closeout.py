import base64,hashlib,json,shlex,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent;D=P/'assessment/closeout';D.mkdir(exist_ok=True)
code='''import base64,json,hashlib
from pathlib import Path
R=Path('/opt/english-eager');files={}
for d in ['fit-closeout','termination-diagnosis','packing-diagnosis']:
 for p in (R/d).glob('*.json'):
  if p.name=='progress.json':continue
  if p.name.startswith('tools-') and json.loads(p.read_text()).get('status')!='development_checks_complete':continue
  b=p.read_bytes();files[d+'/'+p.name]={'sha256':hashlib.sha256(b).hexdigest(),'data':base64.b64encode(b).decode()}
print(json.dumps(files))'''
r=subprocess.run(['gcloud','compute','ssh','ganesh-a100-1117-203113','--project=executespecv1','--zone=us-central1-c','--tunnel-through-iap','--quiet','--command=sudo python3 -c '+shlex.quote(code)],capture_output=True,text=True,timeout=90);assert r.returncode==0,r.stderr
files=json.loads(r.stdout)
for name,e in files.items():
 p=D/name;p.parent.mkdir(parents=True,exist_ok=True);b=base64.b64decode(e['data']);assert hashlib.sha256(b).hexdigest()==e['sha256'];p.write_bytes(b)
print(list(files))
