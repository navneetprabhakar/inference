#!/bin/bash
set -euo pipefail
# Same allocated VM. Preserve the complete previous workspace and its captures.
exec 8>/opt/english/worker.lock
flock -n 8
[ -f /opt/english/normal-stop-ready ]
[ ! -e /opt/english/backup-failure.txt ]
[ ! -e /opt/english-eager ]
# Probe the machine-wide lock; each SFT child acquires it for its entire lifetime.
flock -n /tmp/ganesh-gpu-writer.lock true
mkdir /opt/english-eager
cd /opt/english-eager
exec > >(tee -a bootstrap.log) 2>&1
exec 9>worker.lock
flock -n 9
printf '%s\n' 'Original provider/guest deadline retained; no VM stop/restart.'
timeout 180 gcloud storage cp "$1" runtime.tar.gz --quiet
printf '%s  runtime.tar.gz\n' "$2" | sha256sum -c -
timeout 120 gcloud storage cp "$3" packet.tar.gz --quiet
printf '%s  packet.tar.gz\n' "$4" | sha256sum -c -
/usr/bin/python3 - <<'PY'
import tarfile,pathlib,os,zipfile,json,hashlib
for name in ('runtime.tar.gz','packet.tar.gz'):
 with tarfile.open(name) as t:
  names=set()
  for m in t.getmembers():
   p=pathlib.PurePosixPath(m.name)
   assert m.isfile() and not p.is_absolute() and '..' not in p.parts and m.name not in names
   assert not pathlib.Path(m.name).exists();names.add(m.name)
  t.extractall('.',filter='data')
from cloud_training.nano_package import extract_verified
extract_verified('runtime.tar.gz','.')
pathlib.Path('base').mkdir()
for name in ('payload.pt','metadata.json','manifest.json','COMMITTED'):os.link('/opt/english/base/'+name,'base/'+name)
for wheel in pathlib.Path('wheels').glob('*.whl'):zipfile.ZipFile(wheel).extractall('vendor')
with pathlib.Path('runtime.tar.gz').open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
pathlib.Path('runtime-readback.json').write_text(json.dumps({'sha256':sha,'gcs_full_download_hash_verified':True,'original_workspace_preserved':True},indent=2)+'\n')
PY
export PYTHONPATH=/opt/english-eager/vendor:/opt/english-eager:/opt/english-eager/nanochat-source
export HF_HUB_OFFLINE=1 WANDB_MODE=disabled
/usr/bin/python3 -u gpu_qualify.py
# Keep this VM for approved remaining work. No automatic fit, retry, or shutdown.
