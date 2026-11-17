import hashlib,json,datetime,subprocess,shlex
from pathlib import Path
P=Path(__file__).resolve().parent
subprocess.run(['.venv/bin/python',str(P/'refresh_pilot_inventory.py')],check=True,timeout=240)
source=P/'assess_stopped_fit_on_vm.py';sha=hashlib.sha256(source.read_bytes()).hexdigest()
with (P/'stopped-fit-assessment-launch-intent.json').open('x') as f:json.dump({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_sha256':sha,'scope':'Full read-only assessment of quality-stopped fit; no training restart or curriculum dispatch'},f)
cmd="set -euo pipefail\nsudo flock -n /tmp/ganesh-gpu-writer.lock true\nprintf '%s  %s\\n' "+shlex.quote(sha)+" /home/admin_executespec_ai/assess_stopped_fit_on_vm.py | sha256sum -c -\n"
cmd+='sudo systemd-run --unit=ganesh-stopped-fit-assessment --working-directory=/opt/english-eager --setenv=PYTHONPATH=/opt/english-eager/vendor:/opt/english-eager:/opt/english-eager/nanochat-source --setenv=HF_HUB_OFFLINE=1 --setenv=WANDB_MODE=disabled --property=KillMode=control-group --property=TimeoutStopSec=600 --property=RuntimeMaxSec=7200 /usr/bin/python3 -u /home/admin_executespec_ai/assess_stopped_fit_on_vm.py'
r=subprocess.run(['gcloud','compute','ssh','ganesh-a100-1117-203113','--project=executespecv1','--zone=us-central1-c','--tunnel-through-iap','--quiet','--command='+cmd],capture_output=True,text=True,timeout=90);(P/'stopped-fit-assessment-launch.log').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stderr;print(r.stdout+r.stderr)
