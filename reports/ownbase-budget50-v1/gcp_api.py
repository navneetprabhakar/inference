"""Bounded IPv4 GCP REST request; credentials stay in process memory/stdin."""
import argparse,json,subprocess
from pathlib import Path
from urllib.parse import urlparse

def request(url, *, method='GET', payload=None, timeout=60):
    assert urlparse(url).hostname in {'compute.googleapis.com','storage.googleapis.com','cloudbilling.googleapis.com','bigquery.googleapis.com','cloudresourcemanager.googleapis.com'}
    auth=subprocess.run(['gcloud','auth','print-access-token'],capture_output=True,text=True,timeout=30,check=True)
    config='header = "Authorization: Bearer '+auth.stdout.strip()+'"\n'
    argv=['curl','-4','--silent','--show-error','--fail-with-body','--connect-timeout','10','--max-time',str(timeout),'--config','-','-X',method,url]
    if payload is not None:argv+=['-H','Content-Type: application/json','--data-binary',json.dumps(payload)]
    result=subprocess.run(argv,input=config,capture_output=True,text=True,timeout=timeout+10)
    if result.returncode:raise RuntimeError(f'GCP request failed ({result.returncode}): {result.stdout[:1200]} {result.stderr[:300]}')
    if not result.stdout:return {}
    try:return json.loads(result.stdout)
    except json.JSONDecodeError:return result.stdout
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('url');p.add_argument('output');p.add_argument('--method',default='GET');p.add_argument('--payload');args=p.parse_args()
    result=request(args.url,method=args.method,payload=json.loads(Path(args.payload).read_text()) if args.payload else None)
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'output':args.output,'status':result.get('status'),'error':result.get('error')}))
