"""Read-only reconciliation; never creates, starts or stops compute."""
import json,subprocess,datetime
from pathlib import Path
P=Path(__file__).resolve().parent
config=json.loads((P/'config.json').read_text())
def call(a):
 r=subprocess.run(['gcloud',*a,'--project=executespecv1','--format=json'],capture_output=True,text=True,timeout=90)
 return {'returncode':r.returncode,'data':json.loads(r.stdout) if r.returncode==0 else None,'error':r.stderr if r.returncode else None}
result={'checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'instances':call(['compute','instances','list']),'disks':call(['compute','disks','list'])}
if (P/'operations.json').exists():
 result['operations']=[call(['compute','operations','describe',o['name'],'--zone=us-central1-a']) for o in json.loads((P/'operations.json').read_text())]
(P/'latest-status.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'checked_utc':result['checked_utc'],'instances':[(i['name'],i['status']) for i in result['instances']['data'] or []],'disk_count':len(result['disks']['data'] or []),'operations':[o['data'] for o in result.get('operations',[])],'errors':[v['error'] for v in (result['instances'],result['disks']) if v['error']]},indent=2))
