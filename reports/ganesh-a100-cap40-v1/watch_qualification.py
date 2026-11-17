"""Read-only monitoring of the one active VM; never allocates or retries training."""
import datetime as dt,json,subprocess,sys,time
from pathlib import Path
P=Path(__file__).resolve().parent;s=json.loads((P/'zone-sweep.json').read_text());a=next(a for a in s['attempts'] if a['status']=='allocated_monitor_qualification');A=Path(a['directory']);cfg=json.loads((A/'config.json').read_text());deadline=dt.datetime.fromisoformat(cfg['qualification_deadline_utc'].replace('Z','+00:00')).timestamp();previous=None;failures=0
while time.time()<deadline:
 r=subprocess.run([sys.executable,str(P/'monitor_active.py')],capture_output=True,text=True,timeout=110)
 if r.returncode:
  failures+=1
  if failures==1:print(json.dumps({'monitor_read_error':r.stderr[-500:]+r.stdout[-500:]}),flush=True)
  if failures>=5:raise RuntimeError('Repeated monitoring errors; inspect current VM')
 else:
  failures=0;j=json.loads(r.stdout);brief={'utc':j['checked_utc'],'branches':{n:{k:v.get(k) for k in ('status','step','reason')} for n,v in j['branches'].items()},'qualification_status':j.get('qualification.json',{}).get('status'),'backup_ready':'normal-stop-ready' in j,'backup_failure':j.get('backup-failure.txt')}
  key=json.dumps({k:v for k,v in brief.items() if k!='utc'},sort_keys=True)
  if key!=previous:print(json.dumps(brief),flush=True);previous=key
  if brief['backup_ready'] or brief['backup_failure']:break
 time.sleep(30)
else:raise RuntimeError('Qualification window reached; inspect before any further work')
