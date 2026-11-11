import json,time,subprocess
from pathlib import Path
p=Path('runs/recovery-3b-v1');deadline=json.loads((p/'budget.json').read_text())['absolute_controller_deadline']+120
while time.time()<deadline:time.sleep(min(60,deadline-time.time()))
for attempt in range(6):
 result=subprocess.run(['gcloud','compute','instances','stop','forge-ownbase-v2-retained-01','--zone=us-central1-b','--project=executespecv1','--quiet'],capture_output=True,text=True,timeout=180)
 (p/'budget-guard-result.json').write_text(json.dumps({'attempt':attempt,'utc_epoch':time.time(),'returncode':result.returncode,'stderr':result.stderr}))
 if result.returncode==0:break
 time.sleep(30)
