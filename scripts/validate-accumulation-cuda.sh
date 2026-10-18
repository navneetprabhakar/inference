#!/usr/bin/env bash
# Creator: Navneet Prabhakar
# Offline dependencies/source/fixtures are uploaded separately; no cloud credentials.
set -uo pipefail
cd "${1:?pass extracted project directory}"
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=4
mkdir -p accumulation-results
export SLM_CUDA_STRESS_REPORT="$PWD/accumulation-results/cuda-100-updates.json"
nvidia-smi > accumulation-results/nvidia-smi.txt
python3 -m pip freeze > accumulation-results/requirements-cuda.lock
python3 -m slm.eval.portability verify --bundle checkpoints/accumulation-tiny-origin-v1 --output accumulation-results/tiny-cuda --backend torch --device cuda > accumulation-results/tiny.log 2>&1
echo "$?" > accumulation-results/tiny.exit
python3 -m slm.eval.state_transfer --checkpoint checkpoints/accumulation-fullsize-origin-v1/initial --fixture checkpoints/accumulation-fullsize-origin-v1 --output accumulation-results/full-exact-import.json --backend torch --device cuda > accumulation-results/import.log 2>&1
echo "$?" > accumulation-results/import.exit
python3 -m slm.eval.accumulated_transfer continue --fixture checkpoints/accumulation-fullsize-origin-v1 --checkpoint checkpoints/accumulation-fullsize-origin-v1/initial --output accumulation-results/full-cuda --backend torch --device cuda --updates 2 > accumulation-results/continue.log 2>&1
echo "$?" > accumulation-results/continue.exit
python3 -m slm.eval.accumulation --config configs/target-81m.json --output accumulation-results/full-own-resume.json --backend torch --device cuda > accumulation-results/own.log 2>&1
echo "$?" > accumulation-results/own.exit
python3 -m slm.eval.benchmark --config configs/target-81m.json --output accumulation-results/benchmark.json --backend torch --device cuda --length 1024 --warmup 2 --steps 5 --accumulation-steps 2 > accumulation-results/benchmark.log 2>&1
echo "$?" > accumulation-results/benchmark.exit
python3 -m pytest -q --junitxml=accumulation-results/tests.xml > accumulation-results/tests.log 2>&1
echo "$?" > accumulation-results/tests.exit
python3 - <<'PY'
import json
from pathlib import Path
root=Path('accumulation-results')
codes={name:int((root/(name+'.exit')).read_text()) for name in ('tiny','import','continue','own','benchmark','tests')}
(root/'job.json').write_text(json.dumps({'exit_codes':codes,'all_checks_passed':all(v==0 for v in codes.values()),
    'scope':'Named mechanics, tiny numerical, throughput and host tests only; full-size cross-backend trajectory and language gates remain open'},indent=2)+'\n')
print(json.dumps(codes))
if not all(v==0 for v in codes.values()):raise SystemExit(1)
PY
