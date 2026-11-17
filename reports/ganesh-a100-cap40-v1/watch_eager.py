import time,subprocess,json,datetime
from pathlib import Path
P=Path(__file__).resolve().parent;end=time.monotonic()+3900;last=None
while time.monotonic()<end:
 r=subprocess.run(['.venv/bin/python',str(P/'monitor_eager.py')],capture_output=True,text=True,timeout=100)
 if r.returncode:print('Monitor unavailable: '+r.stderr[-300:],flush=True)
 else:
  j=json.loads(r.stdout);s={'branches':{n:{k:v.get(k) for k in ('status','step','result_written')} for n,v in j['branches'].items()},'checks':{n:j[n].get('status',j[n].get('input_values_layout_equal')) for n in ('normal-comparison.json','capture-comparison.json','signal-comparison.json') if n in j},'qualification':j.get('qualification.json',{}).get('status'),'backups':bool(j.get('normal-stop-ready')),'backup_failure':j.get('backup-failure.txt')}
  if s!=last:print(json.dumps({'utc':j['checked_utc'],**s}),flush=True);last=s
  if s['backups'] or s['backup_failure']:break
 time.sleep(45)
