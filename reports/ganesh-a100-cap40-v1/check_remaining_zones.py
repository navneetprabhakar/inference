import json,subprocess,sys
from pathlib import Path
P=Path(__file__).resolve().parent
for zone in ('us-central1-c','us-west1-b','us-east1-b'):
 s=json.loads((P/'zone-sweep.json').read_text())
 if s['status']=='allocated_no_further_attempts':break
 if any(a['zone']==zone for a in s['attempts']):raise RuntimeError('Never repeat an attempted zone')
 subprocess.run([sys.executable,str(P/'try_other_zone.py'),'--zone='+zone],check=True)
else:print('US zone checks complete; no automatic repeated attempt queued',flush=True)
