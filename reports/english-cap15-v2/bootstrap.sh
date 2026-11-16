#!/bin/bash
set -euo pipefail
mkdir -p /opt/english
cd /opt/english
exec > >(tee -a /opt/english/bootstrap.log) 2>&1
exec 9>/opt/english/worker.lock
flock -n 9 || exit 2
metadata() { curl --fail --silent --show-error --max-time 10 -H 'Metadata-Flavor: Google' "http://metadata.google.internal/computeMetadata/v1/instance/attributes/$1"; }
# Fixed absolute expiry survives retries/reboots; provider STOP is independent.
DEADLINE=$(metadata own-deadline-utc)
MINUTES=$(python3 - "$DEADLINE" <<'PY'
import datetime,sys,time
remaining=datetime.datetime.fromisoformat(sys.argv[1].replace('Z','+00:00')).timestamp()-time.time()
assert remaining>1200
print(max(1,int((remaining-60)//60)))
PY
)
shutdown -h "+$MINUTES"
# Copy only private, hash-bound code/config; extraction rejects links/traversal.
timeout 600 gcloud storage cp "$(metadata bundle-uri)" runtime.tar.gz --quiet
printf '%s  runtime.tar.gz\n' "$(metadata bundle-sha256)" | sha256sum -c -
timeout 120 gcloud storage cp "$(metadata packet-uri)" packet.tar.gz --quiet
printf '%s  packet.tar.gz\n' "$(metadata packet-sha256)" | sha256sum -c -
python3 - <<'PY'
import tarfile,pathlib
for archive in ('runtime.tar.gz','packet.tar.gz'):
 with tarfile.open(archive) as t:
  names=set()
  for m in t.getmembers():
   p=pathlib.PurePosixPath(m.name)
   assert m.isfile() and not p.is_absolute() and '..' not in p.parts and m.name not in names
   assert not pathlib.Path(m.name).exists()
   names.add(m.name)
  t.extractall('.',filter='data')
from cloud_training.nano_package import extract_verified
extract_verified('runtime.tar.gz','.')
PY
for deb in debs/*.deb; do dpkg-deb -x "$deb" /; done
PYTHON=''
for candidate in /opt/conda/bin/python /opt/pytorch/bin/python /opt/venv/bin/python /usr/bin/python3 /usr/local/bin/python3; do
 if [ -x "$candidate" ] && "$candidate" -c 'import torch; assert torch.__version__.startswith("2.9.1"); assert torch.version.cuda=="12.9"' 2>/dev/null; then PYTHON="$candidate"; break; fi
done
[ -n "$PYTHON" ] || exit 3
"$PYTHON" - <<'PY'
import zipfile,pathlib
for w in pathlib.Path('wheels').glob('*.whl'):zipfile.ZipFile(w).extractall('vendor')
PY
export PYTHONPATH=/opt/english/vendor:/opt/english:/opt/english/nanochat-source
export HF_HUB_OFFLINE=1 WANDB_MODE=disabled
"$PYTHON" -u gpu_qualify.py
# No disk deletion. A failed normal-backup check leaves compute to its hard STOP
# deadline and retains disk for recovery; do not claim a clean closeout.
if [ -f /opt/english/normal-stop-ready ] && ! [ -f /opt/english/backup-failure.txt ]; then shutdown -h now; fi
