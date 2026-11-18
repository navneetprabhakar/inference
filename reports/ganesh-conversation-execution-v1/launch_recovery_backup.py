import datetime as dt,json,shlex,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent;cfg=json.loads((P/'config-v2.json').read_text());assert json.loads((P/'stage-recovery-v2.json').read_text())['returncode']==0
intent=P/'recovery-backup-launch.json';assert not intent.exists()
script='''set -euo pipefail
cd /opt/ganesh-conversation
test ! -f recovery-backups.json
for candidate in /opt/conda/bin/python /opt/pytorch/bin/python /opt/venv/bin/python /usr/bin/python3 /usr/local/bin/python3; do
 if [ -x "$candidate" ] && "$candidate" -c 'import torch; assert torch.__version__.startswith("2.9.1")' 2>/dev/null; then
  systemd-run --unit=ganesh-conversation-recovery-backup --property=WorkingDirectory=/opt/ganesh-conversation --property=RuntimeMaxSec=3000 --setenv=PYTHONPATH=/opt/ganesh-conversation/vendor:/opt/ganesh-conversation:/opt/ganesh-conversation/nanochat-source --setenv=HF_HUB_OFFLINE=1 --setenv=WANDB_MODE=disabled "$candidate" -u /opt/ganesh-conversation/reports/ganesh-conversation-execution-v1/recover_and_backup_on_vm.py
  exit 0
 fi
done
exit 3
'''
cmd=['gcloud','compute','ssh',cfg['instance'],'--project=executespecv1','--zone=us-central1-f','--tunnel-through-iap','--quiet','--command=sudo bash -c '+shlex.quote(script)]
intent.write_text(json.dumps({'utc':dt.datetime.now(dt.timezone.utc).isoformat(),'purpose':'backup_only_no_training','provider_stop_utc':cfg['provider_stop_utc'],'argv':cmd},indent=2)+'\n')
r=subprocess.run(cmd,capture_output=True,text=True,timeout=120);(P/'recovery-backup-launch-result.json').write_text(json.dumps({'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr},indent=2)+'\n');r.check_returncode();print(r.stdout,r.stderr)
