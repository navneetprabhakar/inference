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
mkdir -p instruction-repair-v2-launch
exec > >(tee -a instruction-repair-v2-launch/startup.log) 2>&1
exec 9>gpu.lock
flock -n 9
P=gs://forge-ownbase-a100-20261110/ownbase-v2/instruction-repair-v2
trap 'timeout 120 gcloud storage cp instruction-repair-v2-launch/startup.log "$P/startup.log" --quiet || true' EXIT
mkdir -p sft/instruction-repair-admitted-v2
for F in manifest.json admission.json train.jsonl validation.jsonl; do
 gcloud storage cp "gs://forge-ownbase-a100-20261110/ownbase-v2/sft/instruction-repair-admitted-v2/$F" "sft/instruction-repair-admitted-v2/$F" --quiet
done
gcloud storage cp "$P/heldout-suite.json" instruction-heldout-suite.json --quiet
gcloud storage cp "$P/run.py" instruction-repair-v2-launch/run_pilot.py --quiet
gcloud storage cp "$P/regression-suite.json" instruction-v1-regression-suite.json --quiet
timeout 4200 /usr/bin/python3 -u instruction-repair-v2-launch/run_pilot.py
