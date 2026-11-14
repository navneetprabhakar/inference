"""Read current operation, VM and serial state; never mutates cloud resources."""
import json,subprocess
from pathlib import Path
p=Path(__file__).parent;r=json.loads((p/'launch-request.json').read_text());zone=next(a.split('=',1)[1] for a in r['create_argv'] if a.startswith('--zone='))
def read(args,path):
 c=subprocess.run(['gcloud',*args],text=True,capture_output=True,timeout=60)
 (p/path).write_text(c.stdout if c.returncode==0 else c.stderr)
 return c
if (p/'launch-response.json').exists():
 response=json.loads((p/'launch-response.json').read_text())
 if response.get('stdout'):
  op=json.loads(response['stdout'])[0]['name'];c=read(['compute','operations','describe',op,'--project=executespecv1','--zone='+zone,'--format=json'],'operation-'+zone[-1]+'.json')
  if c.returncode==0:
   o=json.loads(c.stdout);print('operation',o['status'],o.get('error',{}))
c=read(['compute','instances','describe',r['run_id'],'--zone='+zone,'--project=executespecv1','--format=json'],'instance-latest.json')
if c.returncode==0:
 i=json.loads(c.stdout);print('VM',i['status'],'deadline',i.get('scheduling',{}).get('terminationTime'));c=read(['compute','instances','get-serial-port-output',r['run_id'],'--zone='+zone,'--project=executespecv1','--port=1'],'serial-latest.log');print(c.stdout[-5000:])
else:print(c.stderr.strip())
