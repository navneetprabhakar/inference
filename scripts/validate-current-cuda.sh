#!/usr/bin/env bash
# Creator: Navneet Prabhakar
# Host provisioning, offline dependencies and fixture transfer are separate.
set -uo pipefail
cd "${1:?pass extracted project directory}"
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=4
# Fixture children intentionally do not inherit PYTHONPATH. Fail before costly
# checks unless their interpreter has the project and SDK installed/registered.
if ! python3 - <<'PY'
import subprocess,sys
from mcp.client.stdio import get_default_environment
subprocess.run([sys.executable,'-c','import slm.mcp.fixture_server, slm.mcp.http_fixture'],
    env=get_default_environment(),check=True,timeout=10)
PY
then
    echo 'Fixture child interpreter cannot import the registered project/SDK' >&2
    exit 2
fi
mkdir current-results || exit 3
nvidia-smi > current-results/nvidia-smi.txt
python3 -m pip freeze > current-results/requirements-cuda.lock
export SLM_CUDA_STRESS_REPORT="$PWD/current-results/cuda-100-updates.json"
python3 -m pytest -q --junitxml=current-results/tests.xml > current-results/tests.log 2>&1
echo "$?" > current-results/tests.exit
python3 -m slm.eval.curriculum_transfer continue --fixture checkpoints/curriculum-full-origin-v1 --checkpoint checkpoints/curriculum-full-origin-v1/initial --output current-results/full-cuda --backend torch --device cuda > current-results/transfer.log 2>&1
echo "$?" > current-results/transfer.exit
python3 scripts/audit-curriculum.py --config configs/target-81m.json --output current-results/full-dense-own-resume.json --backend torch --device cuda --embedding dense-onehot-v1 > current-results/dense.log 2>&1
echo "$?" > current-results/dense.exit
python3 scripts/audit-curriculum.py --config configs/target-81m.json --output current-results/full-native-own-resume.json --backend torch --device cuda --embedding native-gather-v1 > current-results/native.log 2>&1
echo "$?" > current-results/native.exit
python3 scripts/audit-tools.py --output current-results/tools-audit.json --artifacts current-results/tools-artifacts --backend torch --device cuda > current-results/tools.log 2>&1
echo "$?" > current-results/tools.exit
python3 scripts/audit-mcp.py --output current-results/stdio-audit.json --artifacts current-results/stdio-artifacts --backend torch --device cuda > current-results/stdio.log 2>&1
echo "$?" > current-results/stdio.exit
python3 scripts/audit-http-mcp.py --output current-results/http-audit.json --artifacts current-results/http-artifacts --backend torch --device cuda > current-results/http.log 2>&1
echo "$?" > current-results/http.exit
python3 - <<'PY'
import json
from pathlib import Path
root=Path('current-results');names=('tests','transfer','dense','native','tools','stdio','http')
codes={name:int((root/(name+'.exit')).read_text()) for name in names}
(root/'job.json').write_text(json.dumps({'exit_codes':codes,'all_checks_passed':all(v==0 for v in codes.values()),
    'scope':'Synthetic mechanics, actual random-student negatives and scripted transport controls; not full-size trajectory or learned capability acceptance'},indent=2)+'\n')
print(json.dumps(codes))
if not all(v==0 for v in codes.values()):raise SystemExit(1)
PY
