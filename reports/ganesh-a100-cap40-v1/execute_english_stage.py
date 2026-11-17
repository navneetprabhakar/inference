"""Execute exactly one approved controller command on the retained VM."""
import argparse,datetime,json,subprocess,shlex,hashlib
from pathlib import Path
P=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('task',choices=('fit_train','fit_probes','curriculum_train','curriculum_probes'));p.add_argument('--prepare',action='store_true');a=p.parse_args()
subprocess.run(['.venv/bin/python',str(P/'refresh_pilot_inventory.py')],check=True,timeout=240)
ssh=['gcloud','compute','ssh','ganesh-a100-1117-203113','--project=executespecv1','--zone=us-central1-c','--tunnel-through-iap','--quiet']
env='sudo env PYTHONPATH=/opt/english-eager/vendor:/opt/english-eager:/opt/english-eager/nanochat-source HF_HUB_OFFLINE=1 WANDB_MODE=disabled '
if a.prepare:
 assert a.task=='fit_train'
 sha=hashlib.sha256((P/'prepare_pilot_on_vm.py').read_bytes()).hexdigest()
 cmd="set -euo pipefail\ncd /opt/english-eager\nsudo test ! -e pilot-request.json\nsudo flock -n /opt/english-eager/worker.lock true\nsudo flock -n /tmp/ganesh-gpu-writer.lock true\nprintf '%s  %s\\n' "+shlex.quote(sha)+" /home/admin_executespec_ai/prepare_pilot_on_vm.py | sha256sum -c -\nsudo cp /home/admin_executespec_ai/prepare_pilot_on_vm.py /opt/english-eager/pilot-evidence/prepare_pilot_on_vm.py\n"+env+'/usr/bin/python3 /opt/english-eager/pilot-evidence/prepare_pilot_on_vm.py'
 r=subprocess.run(ssh+['--command='+cmd],capture_output=True,text=True,timeout=600);(P/'pilot-prepare.log').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stdout+r.stderr
# Read-only actual controller preflight; no training or durable intent yet.
code='''import json
from pathlib import Path
from cloud_training.nano_recovery_controller import Controller
from cloud_training.nano_recovery_gate import inspect
R=Path('/opt/english-eager');c=Controller(R,R/'pilot-request.json',R/'runs/ganesh-recovery-next/controller');s=c._state();assert not s['running'] and not s['failed']
t=next(t for t in c.tasks if t['id'] not in s['completed']);assert t['id']==TASK and t['kind']=='command'
c.request['evidence'].update(s.get('evidence',{}));g=inspect(R,c.request,t['stage']);assert g['allowed'],g
print(json.dumps({'task':TASK,'gate':g}))'''.replace('TASK',repr(a.task))
r=subprocess.run(ssh+['--command=cd /opt/english-eager && '+env+'/usr/bin/python3 -c '+shlex.quote(code)],capture_output=True,text=True,timeout=120);(P/(a.task+'-dispatch-gate.log')).write_text(r.stdout+r.stderr);assert r.returncode==0,r.stdout+r.stderr
now=datetime.datetime.now(datetime.timezone.utc)
with (P/(a.task+'-launch-intent.json')).open('x') as f:json.dump({'utc':now.isoformat(),'task':a.task,'cap_usd':40,'same_vm':True},f)
unit='ganesh-english-'+a.task.replace('_','-')
cmd='sudo systemd-run --unit='+unit+' --working-directory=/opt/english-eager --setenv=PYTHONPATH=/opt/english-eager/vendor:/opt/english-eager:/opt/english-eager/nanochat-source --setenv=HF_HUB_OFFLINE=1 --setenv=WANDB_MODE=disabled --property=KillMode=control-group --property=RuntimeMaxSec=7900 /usr/bin/python3 -u -m cloud_training.nano_recovery_controller --root /opt/english-eager --request /opt/english-eager/pilot-request.json --state /opt/english-eager/runs/ganesh-recovery-next/controller --execute-next'
r=subprocess.run(ssh+['--command='+cmd],capture_output=True,text=True,timeout=90);(P/(a.task+'-launch.log')).write_text(r.stdout+r.stderr);assert r.returncode==0,r.stderr;print(r.stdout+r.stderr)
