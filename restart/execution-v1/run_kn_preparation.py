import datetime,json,os,pathlib,sys,hashlib
from slm.restart.custody import profile,runtime_roots,command
from slm.restart.supervisor import TimeBudget,supervise
O=pathlib.Path(__file__).resolve().parent;R=O.parents[1];P=O/'kn-preparation'
if P.exists():raise FileExistsError('Existing preparation run; inspect its receipt instead of resetting')
P.mkdir();auth=json.loads((O/'authorization.json').read_text())
deadline=datetime.datetime.fromisoformat(auth['M1_execution_started_at_utc']).timestamp()+auth['M1_elapsed_cap_seconds']
policy=P/'worker.sb';policy.write_text(profile(read_roots=runtime_roots(R)+[O/'data-train',O/'data-dev'],write_root=P))
identity=hashlib.sha256((R/'src/slm/restart/fit_kn.py').read_bytes()+(R/'src/slm/restart/kneser_ney.py').read_bytes()+(O/'data-train/manifest.json').read_bytes()+(O/'data-dev/manifest.json').read_bytes()).hexdigest()
budget=TimeBudget(P/'time.sqlite',identity=identity,seconds_cap=1800,deadline_utc=deadline)
args=command(policy,[sys.executable,'-m','slm.restart.fit_kn','--train',str(O/'data-train'),'--dev',str(O/'data-dev'),'--out',str(P/'model'),'--heartbeat',str(P/'heartbeat.json')])
result=supervise(args,cwd=P,env={'PATH':'/usr/bin:/bin','PYTHONPATH':str(R/'src'),'PYTHONDONTWRITEBYTECODE':'1','TMPDIR':str(P)},heartbeat=P/'heartbeat.json',budget=budget,receipt=P/'supervisor-receipt.json')
print(json.dumps(result,indent=2));raise SystemExit(0 if result['status']=='PASS' else 1)
