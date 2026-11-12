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
mkdir -p deep-diagnostic-v1
exec > >(tee -a deep-diagnostic-v1/startup.log) 2>&1
exec 9>gpu.lock
flock -n 9
DEST=gs://forge-ownbase-a100-20261110/ownbase-v2/diagnostics/6b-deep-v1
finish() {
 rc=$?; trap - EXIT
 echo "diagnostic_exit=$rc utc=$(date -u +%FT%TZ)" > deep-diagnostic-v1/COMPLETE
 timeout 120 gcloud storage rsync --recursive deep-diagnostic-v1 "$DEST" --quiet || true
 echo "Diagnosis done; VM retained for follow-up within original budget cutoff."
}
trap finish EXIT
 timeout 120 gcloud storage cp "$DEST/nano_protocol_diagnostics.py" cloud_training/nano_protocol_diagnostics.py --quiet
 timeout 1500 /usr/bin/python3 -u -m cloud_training.nano_protocol_diagnostics \
 --repo nanochat-source --checkpoint results/review-004/sft/step-00000155 \
 --tokenizer tokenizer --tokenizer-sha ad777bb448ea8fcf115835548596f9303f3ee5e85a014b0bb315567091080cc5 \
 --manifest sft/diagnostic-admitted-v1/manifest.json --device cuda --kernel-path kernel \
 --suite cloud_training/evaluation/conversation-tools-dev.json \
 --output deep-diagnostic-v1/token-diagnostics-v3.json
