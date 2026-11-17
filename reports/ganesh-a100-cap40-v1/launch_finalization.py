import json,hashlib,datetime,subprocess,shlex
from pathlib import Path
from cloud_training.nano_recovery_gate import inspect,digest
P=Path(__file__).resolve().parent;R=Path.cwd();code=P/'finalize_qualification_on_vm.py';sha=digest(code)
request=json.loads((P/'completion-request.json').read_text());request['files'][str(code.relative_to(R))]=sha;request['completion_scope']='No optimizer updates: direct upload rejection error evidence and still-unstarted original decode benchmark'
spec=hashlib.sha256(json.dumps({k:v for k,v in request.items() if k not in ('authorization','evidence')},sort_keys=True,separators=(',',':')).encode()).hexdigest();request['authorization']['spec_sha256']=spec
for name,entry in list(request['evidence'].items()):
 b=json.loads((R/entry['path']).read_text());b['spec_sha256']=spec;p=P/('finalization-'+name+'-receipt.json');p.write_text(json.dumps(b,indent=2)+'\n');request['evidence'][name]={'path':str(p.relative_to(R)),'sha256':digest(p)}
gate=inspect(R,request,'qualification');assert gate['allowed'],gate
(P/'finalization-request.json').write_text(json.dumps(request,indent=2)+'\n');(P/'finalization-gate.json').write_text(json.dumps(gate,indent=2)+'\n')
now=datetime.datetime.now(datetime.timezone.utc);end=datetime.datetime(2026,11,17,22,31,13,tzinfo=datetime.timezone.utc);assert (end-now).total_seconds()>600
with (P/'finalization-launch-intent.json').open('x') as f:json.dump({'utc':now.isoformat(),'spec_sha256':spec,'no_optimizer_updates':True},f)
cmd="set -euo pipefail\nsudo test -f /opt/english-eager/completion-normal-stop-ready\nsudo flock -n /opt/english-eager/worker.lock true\nprintf '%s  %s\\n' "+shlex.quote(sha)+" /home/admin_executespec_ai/finalize_qualification_on_vm.py | sha256sum -c -\n"
cmd+='sudo systemd-run --unit=ganesh-qualification-finalization --working-directory=/opt/english-eager --setenv=PYTHONPATH=/opt/english-eager/vendor:/opt/english-eager:/opt/english-eager/nanochat-source --setenv=HF_HUB_OFFLINE=1 --setenv=WANDB_MODE=disabled --property=KillMode=control-group --property=RuntimeMaxSec='+str(min(600,int((end-now).total_seconds())-30))+' /usr/bin/python3 -u /home/admin_executespec_ai/finalize_qualification_on_vm.py'
r=subprocess.run(['gcloud','compute','ssh','ganesh-a100-1117-203113','--project=executespecv1','--zone=us-central1-c','--tunnel-through-iap','--quiet','--command='+cmd],capture_output=True,text=True,timeout=90);(P/'finalization-launch.log').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stderr;print(r.stdout+r.stderr)
