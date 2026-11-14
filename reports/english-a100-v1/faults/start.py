"""Fresh finite fault lease after verified stop; cumulative $10 cap remains binding."""
import datetime as dt,hashlib,json,subprocess,tarfile
from pathlib import Path
p=Path(__file__).parent;parent=p.parent;ROOT=p.resolve().parents[2]
if (p/'start-response.json').exists():raise ValueError('Fault stage already attempted')
request=json.loads((parent/'launch-request.json').read_text());name=request['run_id'];zone='us-central1-f'
def call(args):return subprocess.check_output(['gcloud',*args],text=True,timeout=120)
proof=json.loads((parent/'repair/worker-backup-check.json').read_text());result=json.loads((parent/'repair/worker-qualification.json').read_text())
if not proof['local_archive_readback_verified'] or result['status']!='restart_pass_pending_fault_drills' or result['comparison']['status']!='pass':raise ValueError('Exact GPU restart/backup prerequisite failed')
i=json.loads(call(['compute','instances','describe',name,'--zone='+zone,'--project=executespecv1','--format=json']))
if i['status']!='TERMINATED' or i['scheduling']['terminationTime']!=request['latest_local_stop_utc'] or i['disks'][0]['autoDelete']:raise ValueError('Prior worker not safely stopped')
ledger=json.loads((parent/'spend-ledger.json').read_text());previous=ledger['allocations'][-1]
if previous.get('fault_stage_started') or previous['name']!=name:raise ValueError('Unexpected previous allocation')
second_seconds=(dt.datetime.fromisoformat(i['lastStopTimestamp'])-dt.datetime.fromisoformat(i['lastStartTimestamp'])).total_seconds()
seconds=previous['first_runtime_seconds']+second_seconds
if not 0<=seconds<=request['max_runtime_seconds']:raise ValueError('Unreconciled previous runtime')
accounted=seconds/3600*request['list_rate_usd_per_hour']*1.25
reserved=(40/60)*request['list_rate_usd_per_hour']*1.25
if accounted+reserved+ledger['reserve_usd']>ledger['operational_cap_usd']:raise ValueError('Cumulative budget insufficient for fault stage')
(p/'instance-before.json').write_text(json.dumps(i,indent=2)+'\n')
subprocess.run([str(ROOT/'.venv/bin/python'),str(p/'check_injectors.py')],check=True)
subprocess.run([str(ROOT/'.venv/bin/python'),str(p/'check_live_capture.py')],check=True)
now=dt.datetime.now(dt.timezone.utc);deadline=now+dt.timedelta(minutes=40)
c=json.loads((parent/'config.json').read_text());c.update(backup_prefix=c['backup_prefix']+'/faults',deadline_utc=deadline.strftime('%Y-%m-%dT%H:%M:%SZ'),worker_deadline_utc=(deadline-dt.timedelta(minutes=5)).strftime('%Y-%m-%dT%H:%M:%SZ'))
(p/'config.json').write_text(json.dumps(c,indent=2)+'\n')
packet=ROOT/'runs/english-a100-v1/fault-packet.tar.gz'
with tarfile.open(packet,'w:gz') as t:
 for f in ['config.json','worker.py','signal_inject.py','upload_fault_shim.py']:t.add(p/f,arcname=f)
sha=hashlib.sha256(packet.read_bytes()).hexdigest();uri=c['backup_prefix']+'/inputs/packet.tar.gz'
call(['storage','cp',str(packet),uri,'--quiet','--if-generation-match=0']);copy=packet.with_suffix('.readback');call(['storage','cp',uri,str(copy),'--quiet'])
if hashlib.sha256(copy.read_bytes()).hexdigest()!=sha:raise ValueError('Fault packet mismatch')
copy.unlink();(p/'packet-receipt.json').write_text(json.dumps({'sha256':sha,'uri':uri,'independent_readback':True,'new_bounded_stage_deadline':c['deadline_utc']},indent=2)+'\n')
previous.update(state='closed_restart_qualified_backup_reconciled',reserved_compute_usd=0,conservative_accounted_compute_usd=accounted,estimated_compute_spend_usd=accounted/1.25,invoice_verified=False,restart_qualification_runtime_seconds=second_seconds)
allocation={'name':name+'-faults','instance':name,'state':'reserved_before_start','reserved_compute_usd':reserved,'duration_minutes':40,'provider_stop_utc':c['deadline_utc'],'no_pilot_authorized':True}
ledger['allocations'].append(allocation);ledger['active_allocations']=1
stage_request={'stage':'signal_upload_provider_stop_qualification','instance':name,'zone':zone,'deadline_utc':c['deadline_utc'],'duration_minutes':40,'conservative_prior_compute_usd':accounted,'reserved_compute_usd':reserved,'reserve_usd':ledger['reserve_usd'],'total_envelope_usd':accounted+reserved+ledger['reserve_usd'],'operational_cap_usd':10,'prior_lease_closed':True,'packet_sha256':sha,'bootstrap_sha256':hashlib.sha256((p/'bootstrap.sh').read_bytes()).hexdigest()}
(p/'lease-request.json').write_text(json.dumps(stage_request,indent=2)+'\n')
allocation['request_sha256']=hashlib.sha256((p/'lease-request.json').read_bytes()).hexdigest()
(parent/'spend-ledger.json').write_text(json.dumps(ledger,indent=2)+'\n')
call(['compute','instances','set-scheduling',name,'--zone='+zone,'--project=executespecv1','--termination-time='+c['deadline_utc'],'--instance-termination-action=STOP','--no-restart-on-failure','--quiet'])
call(['compute','instances','add-metadata',name,'--zone='+zone,'--project=executespecv1','--metadata=own-deadline-utc='+c['deadline_utc']+',fault-packet-uri='+uri+',fault-packet-sha256='+sha,'--metadata-from-file=startup-script='+str(p.resolve()/'bootstrap.sh'),'--quiet'])
check=json.loads(call(['compute','instances','describe',name,'--zone='+zone,'--project=executespecv1','--format=json']))
if check['status']!='TERMINATED' or check['scheduling']['terminationTime']!=c['deadline_utc'] or check['scheduling']['instanceTerminationAction']!='STOP' or check['disks'][0]['autoDelete']:raise ValueError('Provider lease not bound safely')
(p/'provider-before-start.json').write_text(json.dumps(check,indent=2)+'\n')
allocation['state']='start_requested';(parent/'spend-ledger.json').write_text(json.dumps(ledger,indent=2)+'\n')
try:
 x=subprocess.run(['gcloud','compute','instances','start',name,'--zone='+zone,'--project=executespecv1','--quiet','--async','--format=json'],text=True,capture_output=True,timeout=120)
 response={'returncode':x.returncode,'stdout':x.stdout,'stderr':x.stderr}
except BaseException as e:response={'error':repr(e),'reconcile_required':True}
(p/'start-response.json').write_text(json.dumps(response,indent=2)+'\n');print(json.dumps(response))
