#!/bin/bash
set -Eeuo pipefail
export CLOUDSDK_CORE_DISABLE_PROMPTS=1 HF_HUB_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1
export NANOCHAT_DTYPE=bfloat16 OMP_NUM_THREADS=4 TORCHINDUCTOR_COMPILE_THREADS=2
export PYTHONPATH='/opt/ownbase-nano/vendor:/opt/ownbase-nano:/opt/ownbase-nano/nanochat-source'
cd /opt/ownbase-nano
exec 9>gpu.lock
flock -n 9
exec > >(tee -a recovery-server.log) 2>&1
DEST=gs://forge-ownbase-a100-20261110/production-logs/forge-ownbase-v2-retained-01
SOURCE=gs://forge-ownbase-a100-20261110/ownbase-v2/recovery-3b-v1
DEADLINE=1794476714
TELEMETRY=''
finish() {
 rc=$?; trap - EXIT
 [ -z "$TELEMETRY" ] || kill "$TELEMETRY" 2>/dev/null || true
 timeout 120 gcloud storage cp recovery-server.log "$DEST/recovery-server.log" --quiet || true
 timeout 180 gcloud storage rsync --recursive --exclude='.*payload[.]pt' results "$DEST/results" --quiet || true
 shutdown -h now || true
 exit "$rc"
}
trap finish EXIT
REMAINING=$((DEADLINE-$(date +%s)))
[ "$REMAINING" -gt 18000 ]
shutdown -h "+$((REMAINING/60))"
timeout 120 gcloud storage cp "$SOURCE/nano_campaign.py" cloud_training/nano_campaign.py.recovery --quiet
printf '%s  %s\n' '6ef7c7eb176492057eaa74f985b3e8714db96ab8c384c3dc96696ff80d4a8ec7' cloud_training/nano_campaign.py.recovery | sha256sum -c -
timeout 120 gcloud storage cp "$SOURCE/config.json" recovery-config.json --quiet
printf '%s  %s\n' 'e6f375cb7ebc758d414656c139f70ed405312056707eb1f818097a06349b0264' recovery-config.json | sha256sum -c -
/usr/bin/python3 - <<'PY'
import json,hashlib,pathlib,torch
assert torch.__version__.startswith('2.9.1') and torch.version.cuda=='12.9'
assert torch.cuda.device_count()==1 and 'A100' in torch.cuda.get_device_name()
m=json.load(open('results/stage-002/step-00005723/metadata.json'))
assert m['step']==5723
for name,expected in m['identity']['adapter_hashes'].items():
 assert hashlib.sha256((pathlib.Path('cloud_training')/name).read_bytes()).hexdigest()==expected,name
PY
cp cloud_training/nano_campaign.py cloud_training/nano_campaign.py.before-recovery
mv cloud_training/nano_campaign.py.recovery cloud_training/nano_campaign.py
(
 while sleep 60; do
  timeout 30 gcloud storage cp recovery-server.log "$DEST/recovery-server.log" --quiet || true
  for f in results/*.json results/stage-*/*.json results/stage-*/worker.log results/review-*/*.json results/review-*/worker.log results/review-*/sft/progress.json results/review-*/sft/result.json; do
   [ ! -f "$f" ] || timeout 30 gcloud storage cp "$f" "$DEST/$f" --quiet || true
  done
 done
) &
TELEMETRY=$!
timeout --signal=TERM --kill-after=60s "$REMAINING" /usr/bin/python3 -u - <<'PY'
import json
from cloud_training.nano_campaign import run_campaign
raise SystemExit(run_campaign(json.load(open('recovery-config.json')),'/opt/ownbase-nano',1794476714))
PY
