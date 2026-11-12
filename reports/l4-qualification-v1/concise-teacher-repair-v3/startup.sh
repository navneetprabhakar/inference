#!/bin/bash
set -Eeuo pipefail
export CLOUDSDK_CORE_DISABLE_PROMPTS=1 HF_HUB_OFFLINE=1 NANOCHAT_DTYPE=bfloat16
export PYTHONPATH=/opt/ownbase-nano/vendor:/opt/ownbase-nano:/opt/ownbase-nano/nanochat-source
cd /opt/ownbase-nano
DEADLINE=1794519914
NOW=$(date +%s)
[ "$NOW" -lt "$DEADLINE" ] || { shutdown -h now; exit 1; }
MINUTES=$(( (DEADLINE-NOW)/60 ))
shutdown -c || true
shutdown -h +"$MINUTES"
mkdir -p /run/ownbase-recovery
exec > >(tee -a /run/ownbase-recovery/startup.log) 2>&1
exec 8>gpu.lock
flock -n 8
gcloud storage cp gs://forge-ownbase-a100-20261110/ownbase-v2/conversation-recovery-150-v1/cleanup.py /run/ownbase-recovery/cleanup.py --quiet
/usr/bin/python3 /run/ownbase-recovery/cleanup.py
flock -u 8
mkdir -p concise-teacher-repair-v3-launch
exec > >(tee -a concise-teacher-repair-v3-launch/startup.log) 2>&1
exec 9>gpu.lock
flock -n 9
P=gs://forge-ownbase-a100-20261110/ownbase-v2/concise-teacher-repair-v3
trap 'timeout 120 gcloud storage cp concise-teacher-repair-v3-launch/startup.log "$P/startup.log" --quiet || true' EXIT
mkdir -p sft/concise-teacher-repair-admitted-v1
for F in manifest.json admission.json train.jsonl validation.jsonl; do
 gcloud storage cp "gs://forge-ownbase-a100-20261110/ownbase-v2/sft/concise-teacher-repair-admitted-v1/$F" "sft/concise-teacher-repair-admitted-v1/$F" --quiet
done
gcloud storage cp "$P/heldout-suite.json" instruction-heldout-suite.json --quiet
gcloud storage cp "$P/run.py" concise-teacher-repair-v3-launch/run_pilot.py --quiet
gcloud storage cp "$P/regression-suite.json" instruction-v3-regression-suite.json --quiet
gcloud storage cp "$P/regression-v2-suite.json" instruction-v2-regression-suite.json --quiet
gcloud storage cp "$P/nano_quality.py" cloud_training/nano_quality.py --quiet
echo "89c9bd4f2ad68d9d53c8e7fb508222e5d05f13dc01e17876d51041563c9fe07b  cloud_training/nano_quality.py" | sha256sum -c -
gcloud storage cp "$P/general-challenge.json" general-conversation-challenge.json --quiet
gcloud storage cp "$P/conversation-regression-suite.json" conversation-regression-suite.json --quiet
gcloud storage cp "$P/teacher-regression-suite.json" teacher-regression-suite.json --quiet
gcloud storage cp "$P/constraint-regression-suite.json" constraint-regression-suite.json --quiet
cp cloud_training/nano_sft.py concise-teacher-repair-v3-launch/previous-nano-sft.py
gcloud storage cp "$P/nano_sft.py" cloud_training/nano_sft.py --quiet
echo "9e4a1020774cd568634100c381e8cd2603dfbbd613a191105c3c77d4a120ba4f  cloud_training/nano_sft.py" | sha256sum -c -
timeout 5400 /usr/bin/python3 -u concise-teacher-repair-v3-launch/run_pilot.py
