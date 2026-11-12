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
mkdir -p constraint-repair-v1-launch
exec > >(tee -a constraint-repair-v1-launch/startup.log) 2>&1
exec 9>gpu.lock
flock -n 9
P=gs://forge-ownbase-a100-20261110/ownbase-v2/constraint-repair-v1
trap 'timeout 120 gcloud storage cp constraint-repair-v1-launch/startup.log "$P/startup.log" --quiet || true' EXIT
mkdir -p sft/constraint-repair-admitted-v1
for F in manifest.json admission.json train.jsonl validation.jsonl; do
 gcloud storage cp "gs://forge-ownbase-a100-20261110/ownbase-v2/sft/constraint-repair-admitted-v1/$F" "sft/constraint-repair-admitted-v1/$F" --quiet
done
gcloud storage cp "$P/heldout-suite.json" instruction-heldout-suite.json --quiet
gcloud storage cp "$P/run.py" constraint-repair-v1-launch/run_pilot.py --quiet
gcloud storage cp "$P/regression-suite.json" instruction-v3-regression-suite.json --quiet
gcloud storage cp "$P/regression-v2-suite.json" instruction-v2-regression-suite.json --quiet
gcloud storage cp "$P/nano_quality.py" cloud_training/nano_quality.py --quiet
echo "89c9bd4f2ad68d9d53c8e7fb508222e5d05f13dc01e17876d51041563c9fe07b  cloud_training/nano_quality.py" | sha256sum -c -
gcloud storage cp "$P/general-challenge.json" general-conversation-challenge.json --quiet
gcloud storage cp "$P/conversation-regression-suite.json" conversation-regression-suite.json --quiet
gcloud storage cp "$P/teacher-regression-suite.json" teacher-regression-suite.json --quiet
timeout 5400 /usr/bin/python3 -u constraint-repair-v1-launch/run_pilot.py
