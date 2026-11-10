#!/bin/bash
set -Eeuo pipefail
export CLOUDSDK_CORE_DISABLE_PROMPTS=1
export HF_HUB_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 NANOCHAT_DTYPE=bfloat16
export OMP_NUM_THREADS=4 TORCHINDUCTOR_COMPILE_THREADS=2
BASE=gs://forge-ownbase-a100-20261110/l4-qualification-v1
mkdir -p /opt/ownbase-l4
cd /opt/ownbase-l4
exec 9>/opt/ownbase-l4/gpu.lock
flock -n 9
exec > >(tee -a /opt/ownbase-l4/server.log) 2>&1
metadata() { curl --fail --silent --connect-timeout 5 --max-time 15 -H 'Metadata-Flavor: Google' "http://metadata.google.internal/computeMetadata/v1/instance/attributes/$1"; }
DEST="$BASE/bootstrap-$(hostname)"
TELEMETRY=""
finish() {
  rc=$?
  trap - EXIT
  [ -z "$TELEMETRY" ] || kill "$TELEMETRY" 2>/dev/null || true
  printf '{"exit_code":%s,"finished_utc":"%s"}\n' "$rc" "$(date -u +%FT%TZ)" > server-status.json
  timeout 180 gcloud storage cp server.log server-status.json "$DEST/" --quiet || true
  if [ -d results ]; then timeout 300 gcloud storage rsync --recursive --exclude=".*payload[.]pt" results "$DEST/results" --quiet || true; fi
  shutdown -h now || true
  exit "$rc"
}
trap finish EXIT
# Provider runtime limit remains the outer guard if startup or cleanup fails.
shutdown -h +165
RUN_ID=$(metadata run-id)
DEST="$BASE/$RUN_ID"
timeout 300 gcloud storage cp "$(metadata bundle-uri)" bundle.tar.gz --quiet
printf '%s  bundle.tar.gz\n' "$(metadata code-sha256)" | sha256sum -c -
tar -xzf bundle.tar.gz
# Offline development headers are required by Triton’s generated C extension.
for deb in debs/*.deb; do dpkg-deb -x "$deb" /; done
PY=""
for candidate in /opt/conda/bin/python /opt/pytorch/bin/python /opt/venv/bin/python /usr/bin/python3 /usr/local/bin/python3; do
  if [ -x "$candidate" ] && "$candidate" -c 'import torch,numpy; assert torch.__version__.startswith("2.9.1"); assert torch.version.cuda == "12.9"' 2>/dev/null; then PY="$candidate"; break; fi
done
[ -n "$PY" ] || { echo 'Pinned CUDA PyTorch interpreter missing'; exit 1; }
"$PY" - <<'PY'
import pathlib,zipfile,hashlib,json
for wheel in pathlib.Path('wheels').glob('*.whl'):
    zipfile.ZipFile(wheel).extractall('vendor')
lock=json.load(open('kernel-lock.json'))
for name,meta in lock['files'].items():
    assert hashlib.sha256((pathlib.Path('kernel')/name).read_bytes()).hexdigest()==meta['sha256'],name
PY
export PYTHONPATH="/opt/ownbase-l4/vendor:/opt/ownbase-l4:/opt/ownbase-l4/nanochat-source"
"$PY" -m pip freeze > environment.txt
nvidia-smi > gpu.txt
"$PY" - <<'PY'
import pathlib,sysconfig,torch
assert pathlib.Path(sysconfig.get_path("include"),"Python.h").is_file(), "Missing Python development headers"
x=torch.randn(128,128,device="cuda",requires_grad=True)
f=torch.compile(lambda a: (a@a).square().mean())
f(x).backward()
torch.cuda.synchronize()
print("CUDA compiler forward/backward preflight passed",flush=True)
PY
gcloud storage cp environment.txt gpu.txt "$DEST/" --quiet
"$PY" verify_nano_checkpoint.py
mkdir -p results
# Low-cost telemetry; does not start another GPU process or write model weights.
(
  while sleep 120; do
    timeout 30 gcloud storage cp server.log "$DEST/server.log" --quiet || true
    for f in results/*.json; do [ ! -f "$f" ] || timeout 30 gcloud storage cp "$f" "$DEST/results/" --quiet || true; done
  done
) &
TELEMETRY=$!
timeout --signal=TERM --kill-after=45s 6000 "$PY" -u -m cloud_training.nano_benchmark --repo nanochat-source --output results --seconds 1800 --wall-seconds 5400 --packed-data benchmark-data/train --tokenizer-sha 2f5a044b597b6505675869ff2cc9a05a560eb798a3ceaac31739fb330bb965ea --kernel-path kernel --backup-prefix "$DEST/recovery"
kill "$TELEMETRY" || true
