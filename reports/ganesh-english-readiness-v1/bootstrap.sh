#!/bin/bash
set -euo pipefail
mkdir -p /opt/ganesh-conversation
cd /opt/ganesh-conversation
exec > >(tee -a bootstrap.log) 2>&1
exec 9>bootstrap.lock
flock -n 9 || exit 2
metadata() { curl --fail --silent --show-error --max-time 10 -H 'Metadata-Flavor: Google' "http://metadata.google.internal/computeMetadata/v1/instance/attributes/$1"; }
# The provider STOP is primary. Independent guest fallback is at STOP+60 seconds.
DEADLINE=$(metadata own-deadline-utc)
FALLBACK=$(python3 - "$DEADLINE" <<'PY'
import datetime,sys,time
stop=datetime.datetime.fromisoformat(sys.argv[1].replace('Z','+00:00'))
assert stop.timestamp()-time.time()>1800
print((stop+datetime.timedelta(seconds=60)).strftime('%Y-%m-%d %H:%M:%S UTC'))
PY
)
systemd-run --unit=ganesh-budget-stop --on-calendar="$FALLBACK" /sbin/shutdown -h now
[ ! -e bootstrap-started ] || exit 0
touch bootstrap-started
timeout 600 gcloud storage cp "$(metadata bundle-uri)" runtime.tar.gz --quiet
printf '%s  runtime.tar.gz\n' "$(metadata bundle-sha256)" | sha256sum -c -
timeout 120 gcloud storage cp "$(metadata packet-uri)" packet.tar.gz --quiet
printf '%s  packet.tar.gz\n' "$(metadata packet-sha256)" | sha256sum -c -
timeout 120 gcloud storage cp "$(metadata config-uri)" config-v3.json --quiet
printf '%s  config-v3.json\n' "$(metadata config-sha256)" | sha256sum -c -
for item in fresh-authorization provider-v3 runtime-readiness-v3; do
 timeout 120 gcloud storage cp "$(metadata "$item-uri")" "$item.json" --quiet
 printf '%s  %s.json\n' "$(metadata "$item-sha256")" "$item" | sha256sum -c -
done
python3 - <<'PY'
import pathlib,tarfile
for archive in ('runtime.tar.gz','packet.tar.gz'):
 with tarfile.open(archive) as t:
  seen=set()
  for m in t.getmembers():
   p=pathlib.PurePosixPath(m.name)
   assert m.isfile() and not p.is_absolute() and '..' not in p.parts and m.name not in seen
   assert not pathlib.Path(m.name).exists()
   seen.add(m.name)
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
export PYTHONPATH=/opt/ganesh-conversation/vendor:/opt/ganesh-conversation:/opt/ganesh-conversation/nanochat-source
export HF_HUB_OFFLINE=1 WANDB_MODE=disabled
"$PYTHON" - <<'PY'
import json,subprocess
from pathlib import Path
from cloud_training.nano_checkpoint import validate_bundle
from cloud_training.nano_data import sha256_file
cfg=json.loads(Path('config-v3.json').read_text())
ready=json.loads(Path('runtime-readiness-v3.json').read_text())
assert ready['status']=='pass' and ready['archive_tests_passed'] is True
assert ready['runtime_sha256']==cfg['runtime_sha256']==sha256_file('runtime.tar.gz')
assert ready['packet_sha256']==sha256_file('packet.tar.gz')
assert sha256_file('tokenizer/tokenizer.pkl')==cfg['tokenizer_sha256']
for name in ('parent','ancestor'):
 d=Path(name);d.mkdir()
 for file in ('payload.pt','metadata.json','manifest.json','COMMITTED'):
  subprocess.run(['gcloud','storage','cp',cfg[name+'_uri']+'/'+file,str(d/file),'--quiet'],check=True,timeout=600)
 validate_bundle(d)
 assert sha256_file(d/'manifest.json')==cfg[name+'_manifest_sha256']
Path('verified-inputs-v3.json').write_text(json.dumps(dict(verified=True,instance=cfg['instance'],runtime_sha256=cfg['runtime_sha256'])))
PY
"$PYTHON" - <<'PY'
import subprocess,json,sys
command=json.loads(subprocess.check_output([sys.executable,'reports/ganesh-english-readiness-v1/qualification_service.py']))
subprocess.run(command,check=True)
PY
