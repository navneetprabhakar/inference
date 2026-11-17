"""Complete unstarted qualification checks, not a retry of an executed writer."""
import json,hashlib,datetime,subprocess,shlex,ast
from pathlib import Path
from cloud_training.nano_recovery_gate import inspect,digest
P=Path(__file__).resolve().parent;Q=P/'eager-qualification';R=Path.cwd()
s=(P/'complete_recovery_on_vm.py').read_text();ast.parse(s)
assert "assert not (ORIGINAL/'signal_resume').exists()" in s and 'Deadline must allow reserve and be within6hours' in s
assert "config['worker_deadline_utc']='2026-11-17T22:26:13Z'" in s and "config['qualification_deadline_utc']=='2026-11-17T22:31:13Z'" in s
assert s.count("sft('signal_resume'")==1 and s.count("sft('upload_fault'")==1
r=json.loads((Q/'request.json').read_text());r['worker_stop_utc']='2026-11-17T22:26:13Z';r['completion_scope']='Only unstarted signal resume after CLI deadline rejection, upload fault and decode; prior exact checks reused; overall qualification deadline unchanged'
r['files'][str((P/'complete_recovery_on_vm.py').relative_to(R))]=digest(P/'complete_recovery_on_vm.py')
raw=subprocess.check_output(['gcloud','compute','instances','list','--project=executespecv1','--format=json'],text=True,timeout=60);j=json.loads(raw);assert len(j)==1;v=j[0]
assert v['id']==r['existing_instance_id'] and v['status']=='RUNNING' and v['scheduling']['terminationTime']==r['provider_stop_utc'] and v['scheduling']['instanceTerminationAction']=='STOP' and all(not d['autoDelete'] for d in v['disks'])
now=datetime.datetime.now(datetime.timezone.utc);assert now<datetime.datetime(2026,11,17,22,6,13,tzinfo=datetime.timezone.utc)
(P/'completion-inventory.json').write_text(raw)
spec=hashlib.sha256(json.dumps({k:x for k,x in r.items() if k not in ('authorization','evidence')},sort_keys=True,separators=(',',':')).encode()).hexdigest();r['authorization']['spec_sha256']=spec
for n,e in list(r['evidence'].items()):
 b=json.loads((R/e['path']).read_text());b['spec_sha256']=spec
 if n=='input_backups':
  proof=P/'completion-code-backup.json';backup=json.loads(proof.read_text());assert backup['full_gcs_readback_verified'] and backup['sha256']==digest(P/'complete_recovery_on_vm.py');b.update(checked_utc=backup['checked_utc'],raw_receipt=str(proof.relative_to(R)),raw_sha256=digest(proof))
 if n=='fresh_inventory':b.update(checked_utc=now.isoformat(),raw_receipt=str((P/'completion-inventory.json').relative_to(R)),raw_sha256=digest(P/'completion-inventory.json'))
 path=P/('completion-'+n+'-receipt.json');path.write_text(json.dumps(b,indent=2)+'\n');r['evidence'][n]={'path':str(path.relative_to(R)),'sha256':digest(path)}
g=inspect(R,r,'qualification');assert g['allowed'],g
(P/'completion-request.json').write_text(json.dumps(r,indent=2)+'\n');(P/'completion-gate.json').write_text(json.dumps(g,indent=2)+'\n')
sha=digest(P/'complete_recovery_on_vm.py');pilotsha=digest(P/'prepare_pilot_on_vm.py')
cmd="set -euo pipefail\nsudo test -f /opt/english-eager/normal-stop-ready\nsudo test ! -e /opt/english-eager/backup-failure.txt\nsudo flock -n /opt/english-eager/worker.lock true\nprintf '%s  %s\\n' "+shlex.quote(sha)+" /home/admin_executespec_ai/complete_recovery_on_vm.py | sha256sum -c -\nprintf '%s  %s\\n' "+shlex.quote(pilotsha)+" /home/admin_executespec_ai/prepare_pilot_on_vm.py | sha256sum -c -\nsudo test ! -e /opt/english-eager/pilot-request.json\nsudo cp /home/admin_executespec_ai/prepare_pilot_on_vm.py /opt/english-eager/pilot-evidence/prepare_pilot_on_vm.py\n"
duration=int((datetime.datetime(2026,11,17,22,31,13,tzinfo=datetime.timezone.utc)-now).total_seconds())-30
cmd+='sudo systemd-run --unit=ganesh-recovery-completion --working-directory=/opt/english-eager --setenv=PYTHONPATH=/opt/english-eager/vendor:/opt/english-eager:/opt/english-eager/nanochat-source --setenv=HF_HUB_OFFLINE=1 --setenv=WANDB_MODE=disabled --property=KillMode=control-group --property=RuntimeMaxSec='+str(duration)+' /usr/bin/python3 -u /home/admin_executespec_ai/complete_recovery_on_vm.py'
with (P/'completion-launch-intent.json').open('x') as f:json.dump({'utc':now.isoformat(),'spec_sha256':spec,'only_unstarted_checks':True,'provider_deadline_unchanged':True},f)
p=subprocess.run(['gcloud','compute','ssh',v['name'],'--project=executespecv1','--zone=us-central1-c','--tunnel-through-iap','--quiet','--command='+cmd],capture_output=True,text=True,timeout=90)
(P/'completion-launch.log').write_text(p.stdout+p.stderr);assert p.returncode==0,p.stderr;print(p.stdout+p.stderr)
