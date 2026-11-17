import json,subprocess,shlex,hashlib,datetime
from pathlib import Path
P=Path(__file__).resolve().parent
u=json.loads((P/'uploads.json').read_text())['inputs']
commands=['set -euo pipefail','sudo mkdir -p /opt/eager-inputs']
for i in u:
 dest='/opt/eager-inputs/'+i['uri'].split('/')[-1]
 commands+=['sudo gcloud storage cp '+shlex.quote(i['uri'])+' '+dest+' --quiet',"printf '%s  %s\\n' "+shlex.quote(i['sha256'])+' '+dest+' | sudo sha256sum -c -']
commands+=['sudo test -f /opt/english/normal-stop-ready','sudo test ! -e /opt/english/backup-failure.txt','sudo flock -n /opt/english/worker.lock true','sudo flock -n /tmp/ganesh-gpu-writer.lock true','sudo shutdown --show']
r=subprocess.run(['gcloud','compute','ssh','ganesh-a100-1117-203113','--project=executespecv1','--zone=us-central1-c','--tunnel-through-iap','--quiet','--command='+"\n".join(commands)],capture_output=True,text=True,timeout=240)
(P/'prelaunch.log').write_text(r.stdout+r.stderr)
assert r.returncode==0,r.stderr
(P/'readback.json').write_text(json.dumps({'checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'full_gcs_readback_verified':True,'inputs':u,'log_sha256':hashlib.sha256((P/'prelaunch.log').read_bytes()).hexdigest()},indent=2)+'\n')
print(r.stdout)
