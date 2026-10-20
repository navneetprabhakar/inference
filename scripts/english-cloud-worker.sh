#!/usr/bin/env bash
# Creator: Navneet Prabhakar
set -euo pipefail
cd "${1:?extracted project directory required}"
export NVIDIA_TF32_OVERRIDE=0 OMP_NUM_THREADS=4
export PYTHONPATH="$PWD/src:$PWD/../dependencies"
python3 - <<'PY'
import sys,json,torch,numpy,safetensors,tokenizers
from pathlib import Path
if not torch.cuda.is_available():raise RuntimeError('Actual CUDA unavailable')
if torch.cuda.get_device_name(0).find('L4')<0:raise RuntimeError('Expected the one authorized NVIDIA L4')
if torch.cuda.device_count()!=1:raise RuntimeError('Single GPU contract required')
torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
Path('data/english-recovery-experiment-v1/cuda-runtime.json').write_text(json.dumps(dict(python=sys.version,torch=torch.__version__,numpy=numpy.__version__,safetensors=safetensors.__version__,tokenizers=tokenizers.__version__,cuda=torch.version.cuda,gpu=torch.cuda.get_device_name(0),tf32=False),indent=2)+'\n')
PY
python3 scripts/run-english-learning.py cuda
python3 scripts/run-english-learning.py paired-check
python3 scripts/run-english-learning.py language
