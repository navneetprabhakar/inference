"""Read-only cloud inventory; refresh only the request's mutable inventory receipt."""
import datetime,json,subprocess,shlex
from pathlib import Path
P=Path(__file__).resolve().parent;D=P/'pilot-inputs-eager'
r=subprocess.run(['gcloud','compute','instances','list','--project=executespecv1','--format=json'],capture_output=True,text=True,check=True,timeout=60);j=json.loads(r.stdout)
assert len(j)==1;v=j[0];assert v['name']=='ganesh-a100-1117-203113' and v['status']=='RUNNING'
assert v['scheduling']['terminationTime']=='2026-11-18T03:05:59Z' and v['scheduling']['instanceTerminationAction']=='STOP' and not v['scheduling']['automaticRestart'];assert all(not d['autoDelete'] for d in v['disks'])
p=D/'inventory.json';p.write_text(json.dumps({'checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'instances':j},indent=2)+'\n')
subprocess.run(['gcloud','compute','scp',str(p),v['name']+':~/eager-inventory.json','--project=executespecv1','--zone=us-central1-c','--tunnel-through-iap','--quiet'],check=True,timeout=90)
code='''import json,hashlib,os
from pathlib import Path
R=Path('/opt/english-eager');p=R/'pilot-evidence/inventory.json';src=Path('/home/admin_executespec_ai/eager-inventory.json');temp=p.with_suffix('.pending');temp.write_bytes(src.read_bytes());os.replace(temp,p)
request=R/'pilot-request.json'
if request.exists():
 r=json.loads(request.read_text());body={'status':'pass','check':'fresh_inventory','spec_sha256':r['authorization']['spec_sha256'],'checked_utc':json.loads(p.read_text())['checked_utc'],'raw_receipt':'pilot-evidence/inventory.json','raw_sha256':hashlib.sha256(p.read_bytes()).hexdigest()};receipt=R/'pilot-evidence/fresh_inventory-receipt.json';receipt.write_text(json.dumps(body,indent=2)+'\\n');r['evidence']['fresh_inventory']={'path':'pilot-evidence/fresh_inventory-receipt.json','sha256':hashlib.sha256(receipt.read_bytes()).hexdigest()};pending=request.with_suffix('.pending');pending.write_text(json.dumps(r,indent=2)+'\\n');os.replace(pending,request)
print('Fresh actual inventory; immutable specification unchanged')'''
subprocess.run(['gcloud','compute','ssh',v['name'],'--project=executespecv1','--zone=us-central1-c','--tunnel-through-iap','--quiet','--command=sudo /usr/bin/python3 -c '+shlex.quote(code)],check=True,timeout=90)
