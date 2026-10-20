#!/usr/bin/env bash
# Creator: Navneet Prabhakar
set -euo pipefail
cd "${1:?extracted project directory}"
task_proof="${2:?pinned proof-only worker}"
task_proof="$(cd "$(dirname "$task_proof")" && pwd)/$(basename "$task_proof")"
export NVIDIA_TF32_OVERRIDE=0 OMP_NUM_THREADS=4
export PYTHONPATH="$PWD/src:$PWD/../dependencies"
finish_pipeline() {
 task_exit_code=$?
 python3 - "$task_exit_code" <<'PY'
import json,sys
from pathlib import Path
from datetime import datetime,timezone
Path('data/english-balanced-experiment-v2/cloud-pipeline-exit.json').write_text(json.dumps(dict(
 complete=int(sys.argv[1])==0,returncode=int(sys.argv[1]),finished_at_utc=datetime.now(timezone.utc).isoformat(),
 direct_assessment_pending=True),indent=2)+'\n')
PY
}
trap finish_pipeline EXIT
bash "$task_proof" "$PWD"
python3 scripts/freeze-uniform-main-v3.py
python3 scripts/run-uniform-main-v3.py language
