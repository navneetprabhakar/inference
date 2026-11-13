"""Archive failed attempt and retry same bounded GPU in another zone, no parallel allocation."""
import json,os,signal,subprocess,sys,time,shutil
from pathlib import Path
R=Path('runs/ownbase-budget50-v1');P=Path('reports/ownbase-budget50-v1');zone=sys.argv[1]
old=json.loads((R/'launch-receipt.json').read_text());op=json.loads((R/'create-operation.json').read_text());assert op['status']=='DONE' and op.get('error')
archive=R/('attempt-'+old['zone']);archive.mkdir(exist_ok=False)
for name in ['launch-receipt.json','create-argv.json','create-result.json','create-stderr.txt','create-operation.json']:shutil.copy2(R/name,archive/name)
pid=old['guard_pid'];args=subprocess.check_output(['ps','-p',str(pid),'-o','command='],text=True);assert 'ownbase-budget50-v1/guard.py' in args;os.kill(pid,signal.SIGTERM);time.sleep(.3)
c=json.loads((P/'launch-config.json').read_text());c['zone']=zone;c['config_uri']=c['run_prefix']+'/launch/launch-config-'+zone+'-queued.json';(P/'launch-config.json').write_text(json.dumps(c,indent=2)+'\n')
env=dict(os.environ,CLOUDSDK_PYTHON_SITEPACKAGES='1',PYTHONPATH=str((R/'ipv4').resolve()));subprocess.run(['gcloud','storage','cp',str(P/'launch-config.json'),c['config_uri'],'--if-generation-match=0','--quiet'],env=env,check=True,timeout=120)
s=P/'launch.py';text=s.read_text().replace("zone='us-central1-b';project=", "zone=c['zone'];project=").replace("'config-uri':c['run_prefix']+'/launch/launch-config.json'","'config-uri':c.get('config_uri',c['run_prefix']+'/launch/launch-config.json')");s.write_text(text)
subprocess.run([sys.executable,str(s)],check=True)
