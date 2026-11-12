import json,time,subprocess,fcntl
from pathlib import Path
p=Path('runs/conversation-recovery-150-v1');lock=(p/'guard.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
deadline=json.loads((p/'budget.json').read_text())['absolute_controller_deadline']
while time.time()<deadline:time.sleep(min(60,deadline-time.time()))
for attempt in range(6):
 r=subprocess.run(['gcloud','compute','instances','stop','forge-ownbase-v2-retained-01','--zone=us-central1-b','--project=executespecv1','--quiet'],capture_output=True,text=True,timeout=180)
 (p/'budget-guard-result.json').write_text(json.dumps({'attempt':attempt,'utc_epoch':time.time(),'returncode':r.returncode,'stderr':r.stderr}))
 if r.returncode==0:break
 time.sleep(30)
