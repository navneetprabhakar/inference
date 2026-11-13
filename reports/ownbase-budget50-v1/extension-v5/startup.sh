#!/bin/bash
set -euo pipefail
ROOT=/opt/ownbase-nano
cd "$ROOT"
exec >> "$ROOT/extension-startup.log" 2>&1
shutdown -h +10
exec 9> "$ROOT/gpu.lock"
flock -n 9
metadata() { curl -fsS -H 'Metadata-Flavor: Google' "http://metadata.google.internal/computeMetadata/v1/instance/attributes/$1"; }
gcloud storage cp "$(metadata extension-budget-uri)" extension-budget.json --quiet
EXTENSION_BUDGET_SHA=$(metadata extension-budget-sha)
export EXTENSION_BUDGET_SHA
python3 - <<'PY'
import hashlib,json,os,subprocess,time,math
from pathlib import Path
p=Path('extension-budget.json');assert hashlib.sha256(p.read_bytes()).hexdigest()==os.environ['EXTENSION_BUDGET_SHA']
b=json.loads(p.read_text());assert b['total_cap_usd']==55 and 3600<=b['duration_seconds']<=7200
assert b['prior_compute_hours']+b['duration_seconds']/3600<=16
remaining=b['duration_seconds']-float(Path('/proc/uptime').read_text().split()[0])-120
assert remaining>1800
subprocess.run(['shutdown','-c'],check=False)
subprocess.run(['shutdown','-h','+'+str(max(1,math.floor(remaining/60)))],check=True)
PY
PREFIX=gs://forge-ownbase-a100-20261110/ownbase-v2/budget50-v1/extension-v5
for file in run_sequence.py supervisor.py packet.json; do gcloud storage cp "$PREFIX/$file" "$ROOT/extension-$file" --quiet; done
python3 - <<'PY'
import hashlib,json,os
from pathlib import Path
p=json.loads(Path('extension-packet.json').read_text())
assert {k:p['hashes'][k] for k in ('run_sequence.py','supervisor.py')}=={'run_sequence.py':'b325bd8f4e1384498fa953119862224595614c30d193bb15563ce96b910f2893','supervisor.py':'cb07bfbbe505426db2628df30162681b8f94c715b5810fbea40a0f895a9a60e9'}
for src,dest in [('run_sequence.py','run-extension-sequence.py'),('supervisor.py','run-extension-supervisor.py')]:
 path=Path('extension-'+src);assert hashlib.sha256(path.read_bytes()).hexdigest()==p['hashes'][src];os.replace(path,dest)
PY
export PYTHONPATH="$ROOT:$ROOT/vendor:$ROOT/nanochat-source"
export NANOCHAT_DTYPE=bfloat16
/usr/bin/python3 -u run-extension-supervisor.py
