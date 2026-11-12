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
mkdir -p conversation-prefix-launch
exec > >(tee -a conversation-prefix-launch/startup.log) 2>&1
exec 9>gpu.lock
flock -n 9
P=gs://forge-ownbase-a100-20261110/ownbase-v2/conversation-prefix-diagnostic-v1
trap 'timeout 120 gcloud storage cp conversation-prefix-launch/startup.log "$P/startup.log" --quiet || true' EXIT
gcloud storage cp "$P/run.py" conversation-prefix-launch/run.py --quiet
gcloud storage cp "$P/probe.py" conversation-prefix-launch/probe.py --quiet
gcloud storage cp "$P/general-challenge.json" general-conversation-challenge.json --quiet
timeout 2100 /usr/bin/python3 -u conversation-prefix-launch/run.py
