import argparse,json,subprocess,time
from pathlib import Path
P=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('task');p.add_argument('--assessment',action='store_true');p.add_argument('--seconds',type=int,default=8000);a=p.parse_args();end=time.monotonic()+a.seconds;last=None
while time.monotonic()<end:
 r=subprocess.run(['.venv/bin/python',str(P/'monitor_english.py')],capture_output=True,text=True,timeout=100)
 if r.returncode:print('Monitor unavailable: '+r.stderr[-300:],flush=True)
 else:
  j=json.loads(r.stdout);s={k:v for k,v in j.items() if k!='utc'}
  if s!=last:print(json.dumps(j),flush=True);last=s
  c=j.get('controller',{})
  if (a.assessment and j.get('assessment_complete')) or (not a.assessment and (c.get('failed') or a.task in c.get('completed',[]))):break
 time.sleep(45)
