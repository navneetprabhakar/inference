#!/usr/bin/env bash
# Creator: Navneet Prabhakar
# Runs independent checks without hiding individual failures.
set -uo pipefail
cd "${1:?pass extracted project directory}"
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=4
mkdir -p fullsize-results
nvidia-smi > fullsize-results/nvidia-smi.txt
python3 -m slm.eval.state_transfer --checkpoint checkpoints/fullsize-overfit-mlx/checkpoint --fixture checkpoints/fullsize-overfit-mlx --output fullsize-results/exact-state-import.json --backend torch --device cuda > fullsize-results/state.log 2>&1
echo "$?" > fullsize-results/state.exit
python3 -m slm.eval.context --model checkpoints/fullsize-overfit-mlx/checkpoint/model --output fullsize-results/context --backend torch --device cuda --reference checkpoints/learned100-context-mlx > fullsize-results/context.log 2>&1
echo "$?" > fullsize-results/context.exit
python3 -m slm.eval.benchmark --config configs/target-81m.json --output fullsize-results/benchmark.json --backend torch --device cuda --length 1024 --warmup 2 --steps 5 > fullsize-results/benchmark.log 2>&1
echo "$?" > fullsize-results/benchmark.exit
python3 -m pytest -q --junitxml=fullsize-results/tests.xml > fullsize-results/tests.log 2>&1
echo "$?" > fullsize-results/tests.exit
python3 - <<'PY'
import json
from pathlib import Path
root=Path('fullsize-results')
statuses={name:int((root/(name+'.exit')).read_text()) for name in ('state','context','benchmark','tests')}
(root/'job.json').write_text(json.dumps({'exit_codes':statuses,'all_checks_passed':all(v==0 for v in statuses.values())},indent=2)+'\n')
print(json.dumps(statuses))
if not all(v==0 for v in statuses.values()):raise SystemExit(1)
PY
