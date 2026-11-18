"""Start only the single reconciled qualification repair; original provider lease."""
import datetime as dt,json,shlex,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent
assert (P/'repair-stage.log').exists() and 'no training launched' in (P/'repair-stage.log').read_text()
cfg=json.loads((P/'config-v2.json').read_text());stop=dt.datetime.fromisoformat(cfg['provider_stop_utc'].replace('Z','+00:00'))
assert (stop-dt.datetime.now(dt.timezone.utc)).total_seconds()>160*60,'Insufficient fixed remaining lease'
intent=P/'qualification-v2-launch.json';assert not intent.exists()
script='''set -euo pipefail
cd /opt/ganesh-conversation
test -f config-v2.json
test ! -e qualification-v2-started
test ! -d qualification-v2
for candidate in /opt/conda/bin/python /opt/pytorch/bin/python /opt/venv/bin/python /usr/bin/python3 /usr/local/bin/python3; do
 if [ -x "$candidate" ] && "$candidate" -c 'import torch; assert torch.__version__.startswith("2.9.1"); assert torch.version.cuda=="12.9"' 2>/dev/null; then
  systemd-run --unit=ganesh-conversation-qual-v2 --property=WorkingDirectory=/opt/ganesh-conversation --property=RuntimeMaxSec=960 --setenv=PYTHONPATH=/opt/ganesh-conversation/vendor:/opt/ganesh-conversation:/opt/ganesh-conversation/nanochat-source --setenv=HF_HUB_OFFLINE=1 --setenv=WANDB_MODE=disabled "$candidate" -u /opt/ganesh-conversation/reports/ganesh-conversation-execution-v1/gpu_qualify.py
  exit 0
 fi
done
exit 3
'''
cmd=['gcloud','compute','ssh',cfg['instance'],'--project=executespecv1','--zone=us-central1-f','--tunnel-through-iap','--quiet','--command=sudo bash -c '+shlex.quote(script)]
intent.write_text(json.dumps({'utc':dt.datetime.now(dt.timezone.utc).isoformat(),'provider_stop_utc':cfg['provider_stop_utc'],'runtime_sha256':cfg['runtime_sha256'],'purpose':'qualification_only','pilot_started':False,'argv':cmd},indent=2)+'\n')
r=subprocess.run(cmd,capture_output=True,text=True,timeout=120)
(P/'qualification-v2-launch-result.json').write_text(json.dumps({'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr},indent=2)+'\n');print(r.stdout);print(r.stderr);r.check_returncode()
