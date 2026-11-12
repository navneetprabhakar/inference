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
mkdir -p conversation-repair-v1-launch
exec > >(tee -a conversation-repair-v1-launch/startup.log) 2>&1
exec 9>gpu.lock
flock -n 9
P=gs://forge-ownbase-a100-20261110/ownbase-v2/conversation-repair-v1
trap 'timeout 120 gcloud storage cp conversation-repair-v1-launch/startup.log "$P/startup.log" --quiet || true' EXIT
mkdir -p sft/conversation-repair-admitted-v1
for F in manifest.json admission.json train.jsonl validation.jsonl; do
 gcloud storage cp "gs://forge-ownbase-a100-20261110/ownbase-v2/sft/conversation-repair-admitted-v1/$F" "sft/conversation-repair-admitted-v1/$F" --quiet
done
gcloud storage cp "$P/heldout-suite.json" instruction-heldout-suite.json --quiet
gcloud storage cp "$P/run.py" conversation-repair-v1-launch/run_pilot.py --quiet
gcloud storage cp "$P/regression-suite.json" instruction-v3-regression-suite.json --quiet
gcloud storage cp "$P/regression-v2-suite.json" instruction-v2-regression-suite.json --quiet
cp cloud_training/nano_sft.py conversation-repair-v1-launch/previous-nano-sft.py
gcloud storage cp "$P/nano_sft.py" cloud_training/nano_sft.py --quiet
echo "734caf5a013a39d9ca922cc118c1de31db30f24e7351ff426e011da8f8acf649  cloud_training/nano_sft.py" | sha256sum -c -
timeout 5400 /usr/bin/python3 -u conversation-repair-v1-launch/run_pilot.py
