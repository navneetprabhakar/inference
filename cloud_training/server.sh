#!/bin/bash
set -Eeuo pipefail
export CLOUDSDK_CORE_DISABLE_PROMPTS=1
BASE=gs://forge-ownbase-a100-20261110
export RESULTS=results-v3
mkdir -p /opt/ownbase
cd /opt/ownbase
exec 9>/opt/ownbase/gpu.lock
flock -n 9
exec > >(tee -a /opt/ownbase/server.log) 2>&1
finish() {
  rc=$?
  printf '{"exit_code":%s,"finished_utc":"%s"}\n' "$rc" "$(date -u +%FT%TZ)" > /opt/ownbase/server-status.json
  gcloud storage cp /opt/ownbase/server.log /opt/ownbase/server-status.json "$BASE/server/" --quiet || true
  shutdown -h now || true
}
trap finish EXIT
# Provider maximum VM runtime is the independent outer limit; this timer
# remains effective if the worker or startup process becomes unresponsive.
shutdown -h +165
metadata() { curl --fail --silent -H 'Metadata-Flavor: Google' "http://metadata.google.internal/computeMetadata/v1/instance/attributes/$1"; }
gcloud storage cp "$BASE/source/code.tar.gz" code.tar.gz --quiet
printf '%s  code.tar.gz\n' "$(metadata code-sha256)" | sha256sum -c -
tar -xzf code.tar.gz
mkdir -p inputs
gcloud storage cp --recursive "$BASE/input/*" inputs/ --quiet
PY=""
for candidate in /opt/conda/bin/python /opt/pytorch/bin/python /opt/venv/bin/python /usr/bin/python3 /usr/local/bin/python3; do
  if [ -x "$candidate" ] && "$candidate" -c 'import torch,numpy; assert torch.version.cuda' 2>/dev/null; then PY="$candidate"; break; fi
done
if [ -z "$PY" ]; then echo 'No preinstalled CUDA PyTorch interpreter found'; find /opt -maxdepth 4 -name 'python*' -print; exit 1; fi
# Install our single verified offline wheel into task-local vendor, without
# altering the image's externally managed Python installation.
"$PY" -c 'import zipfile; zipfile.ZipFile("wheels/tokenizers-0.22.2-cp39-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl").extractall("vendor")'
export PYTHONPATH="/opt/ownbase/vendor:/opt/ownbase"
"$PY" -m pip freeze > environment.txt
nvidia-smi > gpu.txt
gcloud storage cp environment.txt gpu.txt "$BASE/server/" --quiet
"$PY" verify_cloud_training.py
# Every stage is bounded; no long-training command exists in this launcher.
run_stage() {
  stage=$1;shift
  timeout --signal=TERM --kill-after=30s 1800 "$PY" -m cloud_training.diagnostics "$@" --inputs inputs --output "$RESULTS/$stage" --backup "$BASE/$RESULTS/$stage" --seconds 1650
}
run_stage preflight preflight
run_stage benchmark benchmark
MICRO=$("$PY" -c 'import json,os;v=json.load(open(os.environ["RESULTS"]+"/benchmark/result.json"));print(max([x for x in v["results"] if "tokens_per_second" in x],key=lambda x:x["tokens_per_second"])["microbatch"])')
run_stage memorize memorize --microbatch "$MICRO"
run_stage lr-low lr --lr 0.00006 --microbatch "$MICRO"
run_stage lr-medium lr --lr 0.00012 --microbatch "$MICRO"
run_stage lr-high lr --lr 0.00024 --microbatch "$MICRO"
printf '{"state":"all_diagnostics_complete_no_long_training"}\n' > complete.json
gcloud storage cp complete.json "$BASE/$RESULTS/complete.json" --quiet
