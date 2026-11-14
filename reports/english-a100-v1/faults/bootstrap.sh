#!/bin/bash
set -euo pipefail
exec 9>/opt/english/worker.lock
flock -n 9 || exit 2
[ -f /opt/english-repair/normal-stop-ready ]
[ ! -f /opt/english-repair/backup-failure.txt ] || [ -f /opt/english-repair/reconciliation-stop-ready ]
[ ! -e /opt/english-faults ]
mkdir /opt/english-faults
cd /opt/english-faults
exec > >(tee -a bootstrap.log) 2>&1
metadata() { curl --fail --silent --show-error --max-time 10 -H 'Metadata-Flavor: Google' "http://metadata.google.internal/computeMetadata/v1/instance/attributes/$1"; }
DEADLINE=$(metadata own-deadline-utc)
MINUTES=$(python3 - "$DEADLINE" <<'PY'
import datetime,sys,time
remaining=datetime.datetime.fromisoformat(sys.argv[1].replace('Z','+00:00')).timestamp()-time.time()
assert remaining>1800
print(max(1,int((remaining-60)//60)))
PY
)
shutdown -h "+$MINUTES"
timeout 120 gcloud storage cp "$(metadata fault-packet-uri)" packet.tar.gz --quiet
printf '%s  packet.tar.gz\n' "$(metadata fault-packet-sha256)" | sha256sum -c -
python3 - <<'PY'
import tarfile,pathlib
with tarfile.open('packet.tar.gz') as t:
 names=set()
 for m in t:
  p=pathlib.PurePosixPath(m.name)
  assert m.isfile() and not p.is_absolute() and '..' not in p.parts and m.name not in names
  names.add(m.name)
 t.extractall('.',filter='data')
PY
export PYTHONPATH=/opt/english/vendor:/opt/english:/opt/english/nanochat-source
export HF_HUB_OFFLINE=1 WANDB_MODE=disabled
/usr/bin/python3 -u worker.py
if [ -f backup-ready ] && [ ! -f backup-failure.txt ]; then
 if /usr/bin/python3 -c 'import json; assert json.load(open("results/qualification.json"))["status"]=="signal_upload_pass_pending_provider_stop"'; then
  echo 'External provider STOP drill pending; original hard deadline remains.'
 else
  shutdown -h now
 fi
fi
