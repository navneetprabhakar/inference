#!/bin/bash
# Single admitted lease only; provider DELETE deadline remains the outer guard.
set -Eeuo pipefail
export CLOUDSDK_CORE_DISABLE_PROMPTS=1 HF_HUB_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1
export NANOCHAT_DTYPE=bfloat16 OMP_NUM_THREADS=4 TORCHINDUCTOR_COMPILE_THREADS=2
mkdir -p /opt/ownbase-nano
cd /opt/ownbase-nano
exec 9>gpu.lock
flock -n 9
exec > >(tee -a server.log) 2>&1
DEST="gs://forge-ownbase-a100-20261110/ownbase-v2/budget50-v1/bootstrap"
TELEMETRY=''
finish() {
  rc=$?; trap - EXIT
  [ -z "$TELEMETRY" ] || kill "$TELEMETRY" 2>/dev/null || true
  printf '{"exit_code":%s,"finished_utc":"%s"}\n' "$rc" "$(date -u +%FT%TZ)" > server-status.json
  timeout 120 gcloud storage cp server.log server-status.json "$DEST/" --quiet || true
  if [ -d results ]; then timeout 180 gcloud storage rsync --recursive --exclude='.*payload[.]pt' results "$DEST/results" --quiet || true; fi
  shutdown -h now || true
  exit "$rc"
}
trap finish EXIT
# Conservative bootstrap guard covers metadata/config failures; verified config reschedules it. Provider deletes disk.
shutdown -h +20
metadata() { curl --fail --silent --connect-timeout 5 --max-time 15 -H 'Metadata-Flavor: Google' "http://metadata.google.internal/computeMetadata/v1/instance/attributes/$1"; }
timeout 120 gcloud storage cp "$(metadata config-uri)" launch-config.json --quiet
printf '%s  launch-config.json\n' "$(metadata config-sha256)" | sha256sum -c -
# Deadline starts at OS boot, not after data transfer/compiler setup.
read -r DEADLINE LOCAL_MIN DEST < <(python3 - <<'PY'
import json,time,re
c=json.load(open('launch-config.json')); seconds=c['max_runtime_seconds']
kind=c.get('launch_kind','production'); assert kind in ('pilot','production','retained')
assert type(seconds) is int and 1200<=seconds<=(10800 if kind=='pilot' else 115200 if kind=='retained' else 21600)
cadence=c.get('checkpoint_seconds',900); assert type(cadence) is int and cadence in (900,1800)
assert re.fullmatch(r'forge-ownbase-[a-z0-9-]{1,40}',c['run_id'])
uptime=float(open('/proc/uptime').read().split()[0]); remaining=seconds-uptime
assert remaining>900
assert c['budget']['compute_reservation_usd']+c['budget']['storage_transfer_and_uncertainty_reserve_usd']<=50
assert seconds==50400 and c['run_id']=='forge-ownbase-budget50-v1'
print(int(time.time()+remaining-1200),max(1,int((remaining-600)/60)), c['run_prefix']+'/bootstrap')
PY
)
shutdown -c || true
shutdown -h "+$LOCAL_MIN"
timeout 600 gcloud storage cp "$(metadata bundle-uri)" bundle.tar.gz --quiet
printf '%s  bundle.tar.gz\n' "$(metadata code-sha256)" | sha256sum -c -
# Bootstrap extraction rejects all links/devices and path traversal before writes.
python3 - <<'PY'
import tarfile,pathlib
with tarfile.open('bundle.tar.gz','r:gz') as t:
    names=set()
    for m in t.getmembers():
        p=pathlib.PurePosixPath(m.name)
        assert m.isfile() and not p.is_absolute() and '..' not in p.parts and m.name not in names
        assert m.name not in ('launch-config.json','server.log','gpu.lock','bundle.tar.gz')
        names.add(m.name)
    t.extractall('.',filter='data')
from cloud_training.nano_package import extract_verified
extract_verified('bundle.tar.gz','.')
PY
for deb in debs/*.deb; do dpkg-deb -x "$deb" /; done
PY=''
for candidate in /opt/conda/bin/python /opt/pytorch/bin/python /opt/venv/bin/python /usr/bin/python3 /usr/local/bin/python3; do
  if [ -x "$candidate" ] && "$candidate" -c 'import torch,numpy; assert torch.__version__.startswith("2.9.1"); assert torch.version.cuda=="12.9"' 2>/dev/null; then PY="$candidate"; break; fi
done
[ -n "$PY" ] || { echo 'Pinned PyTorch runtime missing'; exit 1; }
"$PY" - <<'PY'
import pathlib,zipfile
for wheel in pathlib.Path('wheels').glob('*.whl'): zipfile.ZipFile(wheel).extractall('vendor')
PY
export PYTHONPATH='/opt/ownbase-nano/vendor:/opt/ownbase-nano:/opt/ownbase-nano/nanochat-source'
"$PY" - <<'PY'
import sysconfig,pathlib,torch
assert pathlib.Path(sysconfig.get_path('include'),'Python.h').is_file()
from importlib.metadata import version
from nanochat.tokenizer import RustBPETokenizer
assert version('rustbpe') == '0.1.0' and version('tiktoken') == '0.11.0'
tokenizer = RustBPETokenizer.from_directory('tokenizer')
probe = 'Own base tokenizer: 12.5 metres, blue notebook.'
assert tokenizer.decode(tokenizer.encode(probe)) == probe
assert torch.cuda.device_count()==1 and 'A100' in torch.cuda.get_device_name()
x=torch.randn(128,128,device='cuda',requires_grad=True)
torch.compile(lambda a:(a@a).square().mean())(x).backward(); torch.cuda.synchronize()
PY
mkdir -p results
(
  while sleep 120; do
    timeout 30 gcloud storage cp server.log "$DEST/server.log" --quiet || true
    # Small nested progress/result/log evidence only; never sync weight payloads.
    while IFS= read -r -d '' f; do
      timeout 30 gcloud storage cp "$f" "$DEST/$f" --quiet || true
    done < <(find results -type f \( -name 'progress.json' -o -name 'result.json' -o -name 'controller.json' -o -name 'failure.json' \) -print0)
  done
) &
TELEMETRY=$!
gcloud storage cp "$(metadata runner-uri)" run-budget50.py --quiet
printf '%s  run-budget50.py\n' "$(metadata runner-sha256)" | sha256sum -c -
gcloud storage cp "$(metadata seed-journal-uri)" seed-journal.json --quiet
printf '%s  seed-journal.json\n' "$(metadata seed-journal-sha256)" | sha256sum -c -
"$PY" -u run-budget50.py
