#!/usr/bin/env bash
# Creator: Navneet Prabhakar
# Run after uploading/extracting the portability archive on the temporary VM.
set -euo pipefail
cd "${1:?pass extracted project directory}"
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=2
mkdir -p validation-results
export SLM_CUDA_STRESS_REPORT="$PWD/validation-results/cuda-100-updates.json"
nvidia-smi > validation-results/nvidia-smi.txt
python3 -m pip freeze > validation-results/requirements-cuda.lock
python3 -m slm.eval.portability verify --bundle checkpoints/portability-origin-v2 --output validation-results/cpu --backend torch --device cpu
python3 -m slm.eval.portability verify --bundle checkpoints/portability-origin-v2 --output validation-results/cuda --backend torch --device cuda
python3 -m pytest -q --junitxml=validation-results/tests.xml
