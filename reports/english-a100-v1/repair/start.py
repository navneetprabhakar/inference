"""One corrected qualification attempt on same VM, disk, budget and deadline."""
import datetime as dt,hashlib,json,subprocess
from pathlib import Path
p=Path(__file__).parent;parent=p.parent
if (p/'start-response.json').exists():raise ValueError('Repair already attempted')
r=json.loads((p/'packet-receipt.json').read_text());request=json.loads((parent/'launch-request.json').read_text());name=request['run_id'];zone='us-central1-f'
def call(args):return subprocess.check_output(['gcloud',*args],text=True,timeout=120)
i=json.loads(call(['compute','instances','describe',name,'--zone='+zone,'--project=executespecv1','--format=json']))
if i['status']!='TERMINATED' or i['scheduling']['terminationTime']!=r['fixed_deadline_utc'] or i['disks'][0]['autoDelete']:raise ValueError('VM not safely stopped with original deadline and disk')
if (dt.datetime.fromisoformat(r['fixed_deadline_utc'].replace('Z','+00:00'))-dt.datetime.now(dt.timezone.utc)).total_seconds()<2400:raise ValueError('Too little original lease remains')
proof=json.loads((parent/'worker-backup-check.json').read_text())
if not proof['local_archive_readback_verified'] or not proof['all_required_checkpoint_readbacks']:raise ValueError('Prior evidence unverified')
(p/'instance-before-repair.json').write_text(json.dumps(i,indent=2)+'\n')
call(['storage','cp',r['path'],r['uri'],'--quiet','--if-generation-match=0'])
copy=Path(r['path']+'.readback');call(['storage','cp',r['uri'],str(copy),'--quiet'])
if hashlib.sha256(copy.read_bytes()).hexdigest()!=r['sha256']:raise ValueError('Repair packet mismatch')
copy.unlink();r['independent_readback']=True;(p/'packet-receipt.json').write_text(json.dumps(r,indent=2)+'\n')
call(['compute','instances','add-metadata',name,'--zone='+zone,'--project=executespecv1','--metadata=repair-packet-uri='+r['uri']+',repair-packet-sha256='+r['sha256'],'--metadata-from-file=startup-script='+str(p.resolve()/'bootstrap.sh'),'--quiet'])
l=json.loads((parent/'spend-ledger.json').read_text());a=l['allocations'][-1];a.update(state='repair_start_requested',repair_attempts=1,original_deadline_unchanged=True)
a['first_runtime_seconds']=(dt.datetime.fromisoformat(i['lastStopTimestamp'])-dt.datetime.fromisoformat(i['lastStartTimestamp'])).total_seconds()
a['first_compute_estimate_usd']=a['first_runtime_seconds']/3600*request['list_rate_usd_per_hour']
(parent/'spend-ledger.json').write_text(json.dumps(l,indent=2)+'\n')
try:
 c=subprocess.run(['gcloud','compute','instances','start',name,'--zone='+zone,'--project=executespecv1','--quiet','--async','--format=json'],text=True,capture_output=True,timeout=120)
 result={'returncode':c.returncode,'stdout':c.stdout,'stderr':c.stderr}
except BaseException as e:result={'error':repr(e),'reconcile_required':True}
(p/'start-response.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
