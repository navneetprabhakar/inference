#!/usr/bin/env bash
# Creator: Navneet Prabhakar
# Setup only on the one independently bounded VM; dependencies stay offline.
set -euo pipefail
task_archive="${1:?archive path}"
task_archive_sha="${2:?archive hash}"
task_launch="${3:?verified cloud launch JSON}"
task_output="${4:?new extraction directory}"
task_verifier="${5:?pinned archive verification script}"
python3 "$task_verifier" "$task_archive" "$task_archive_sha" "$task_output"
task_output="$(cd "$task_output" && pwd)"
mkdir "$task_output/dependencies"
python3 -m pip install --no-index --find-links "$task_output/wheels" --target "$task_output/dependencies" \
  safetensors==0.8.0 tokenizers==0.22.2 jsonschema==4.26.0 > "$task_output/offline-install.log" 2>&1
python3 -m venv --without-pip --system-site-packages "$task_output/venv"
python3 - "$task_output" "$task_launch" <<'PY'
import json,hashlib,shutil,sys
from pathlib import Path
from datetime import datetime,timezone
root=Path(sys.argv[1]); launch=Path(sys.argv[2]); info=json.loads(launch.read_text())
manifest=json.loads((root/'manifest.json').read_text()); project=root/'project'
experiment=Path(manifest['experiment_root'])
if experiment!=Path('data/english-balanced-experiment-v2'):raise ValueError('Reviewed experiment root required')
plan=project/experiment/'plan.json'
if (info.get('resource_contract_passed') is not True
    or info['plan_sha256']!=manifest['plan_sha256']
    or hashlib.sha256(plan.read_bytes()).hexdigest()!=info['plan_sha256']):
 raise ValueError('Actual resource-bound launch must match frozen package/experiment')
created=datetime.fromisoformat(info['creation_started_at_utc'])
# The trainer stops updates at creation+44h. Allow30minutes for its final
# checkpoint/assessment, then leave30minutes before independent VM deletion.
remaining=int(45*3600-1800-(datetime.now(timezone.utc)-created).total_seconds())
if not 3600<=remaining<=45*3600-1800:raise ValueError('Independent VM lifetime/cleanup reserve')
destination=project/experiment/'cloud-launch.json'
if destination.exists():raise FileExistsError('Retain previous cloud launch record')
shutil.copyfile(launch,destination)
(root/'job-seconds.txt').write_text(str(remaining))
site=list((root/'venv/lib').glob('python*/site-packages'))
if len(site)!=1:raise ValueError('One isolated image interpreter required')
(site[0]/'english-project.pth').write_text(str(project/'src')+'\n'+str(root/'dependencies')+'\n')
PY
"$task_output/venv/bin/python" - <<'PY'
import torch,safetensors,tokenizers,jsonschema
if not torch.cuda.is_available() or torch.cuda.device_count()!=1 or 'L4' not in torch.cuda.get_device_name(0):
 raise RuntimeError('The actual one-L4 CUDA host is required')
if torch.__version__!='2.9.1+cu129' or torch.version.cuda!='12.9':
 raise RuntimeError('Preserve the previously validated pinned image Torch/CUDA runtime')
if safetensors.__version__!='0.8.0' or tokenizers.__version__!='0.22.2':
 raise RuntimeError('Pinned portable checkpoint/tokenizer dependencies required')
PY
task_username="$(id -un)"
task_groupname="$(id -gn)"
task_job_seconds="$(cat "$task_output/job-seconds.txt")"
sudo systemd-run --unit=slm-english-recovery --uid="$task_username" --gid="$task_groupname" \
  --property=RuntimeMaxSec="${task_job_seconds}s" --property=KillMode=control-group \
  --property=TimeoutStopSec=15 --property=Restart=no \
  --property=WorkingDirectory="$task_output/project" \
  --property=StandardOutput="append:$task_output/project/data/english-balanced-experiment-v2/cloud-service.log" \
  --property=StandardError="append:$task_output/project/data/english-balanced-experiment-v2/cloud-service.log" \
  --setenv=PATH="$task_output/venv/bin:/usr/local/bin:/usr/bin:/bin" \
  /bin/bash "$task_output/project/scripts/english-cloud-worker-v2.sh" "$task_output/project"
