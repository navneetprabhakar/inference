#!/usr/bin/env bash
# Creator: Navneet Prabhakar
# Actual CUDA proof only. Main continuation requires a separate frozen contract.
set -euo pipefail
cd "${1:?extracted project directory}"
export NVIDIA_TF32_OVERRIDE=0 OMP_NUM_THREADS=4
export PYTHONPATH="$PWD/src:$PWD/../dependencies"
finish_proof() {
  task_exit_code=$?
  python3 - "$task_exit_code" <<'PY'
import json,sys
from pathlib import Path
from datetime import datetime,timezone
Path('data/english-balanced-experiment-v2/cloud-proof-exit.json').write_text(json.dumps(dict(
 complete=int(sys.argv[1])==0,returncode=int(sys.argv[1]),main_training_started=False,
 finished_at_utc=datetime.now(timezone.utc).isoformat()),indent=2)+'\n')
PY
}
trap finish_proof EXIT
python3 - <<'PY'
import json,sys,torch,numpy,safetensors,tokenizers
from pathlib import Path
if not torch.cuda.is_available() or torch.cuda.device_count()!=1 or 'L4' not in torch.cuda.get_device_name(0):
 raise RuntimeError('Actual single L4 required')
torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
Path('data/english-balanced-experiment-v2/cuda-runtime.json').write_text(json.dumps(dict(
 python=sys.version,torch=torch.__version__,numpy=numpy.__version__,safetensors=safetensors.__version__,
 tokenizers=tokenizers.__version__,cuda=torch.version.cuda,gpu=torch.cuda.get_device_name(0),tf32=False),indent=2)+'\n')
PY
python3 scripts/run-english-learning-v2.py cuda
python3 scripts/run-english-learning-v2.py paired-check
