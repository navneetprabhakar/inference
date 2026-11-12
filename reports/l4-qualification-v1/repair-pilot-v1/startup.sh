#!/bin/bash
set -Eeuo pipefail
export CLOUDSDK_CORE_DISABLE_PROMPTS=1 HF_HUB_OFFLINE=1 NANOCHAT_DTYPE=bfloat16
export PYTHONPATH=/opt/ownbase-nano/vendor:/opt/ownbase-nano:/opt/ownbase-nano/nanochat-source
cd /opt/ownbase-nano
DEADLINE=1794476714
NOW=$(date +%s)
[ "$NOW" -lt "$DEADLINE" ] || { shutdown -h now; exit 1; }
MINUTES=$(( (DEADLINE-NOW)/60 ))
shutdown -h +"$MINUTES"
mkdir -p repair-pilot-launch
exec > >(tee -a repair-pilot-launch/startup.log) 2>&1
exec 9>gpu.lock
flock -n 9
P=gs://forge-ownbase-a100-20261110/ownbase-v2/repair-pilot-v1
trap 'timeout 120 gcloud storage cp repair-pilot-launch/startup.log "$P/startup.log" --quiet || true' EXIT
mkdir -p sft/targeted-context-admitted-v3
for F in manifest.json admission.json train.jsonl validation.jsonl; do
 gcloud storage cp "gs://forge-ownbase-a100-20261110/ownbase-v2/sft/targeted-context-admitted-v3/$F" "sft/targeted-context-admitted-v3/$F" --quiet
done
gcloud storage cp "$P/heldout-suite.json" repair-heldout-suite.json --quiet
gcloud storage cp "$P/run.py" repair-pilot-launch/run_pilot.py --quiet
timeout 3600 /usr/bin/python3 -u repair-pilot-launch/run_pilot.py
