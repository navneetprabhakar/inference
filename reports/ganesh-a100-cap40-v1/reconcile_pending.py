"""Read-only reconciliation of the existing asynchronous create; never reallocate."""
import datetime as dt,json,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent;s=json.loads((P/'zone-sweep.json').read_text());a=s['attempts'][-1];assert a['status'] in ('allocation_intent','allocated_monitor_qualification');A=Path(a['directory']);ops=json.loads((A/'operations.json').read_text());assert len(ops)==1
cloud=lambda args:json.loads(subprocess.check_output(['gcloud',*args,'--project=executespecv1','--format=json'],text=True,timeout=90))
def write(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
op=cloud(['compute','operations','describe',ops[0]['name'],'--zone='+a['zone']]);write(A/'operation.json',op)
if op['status']=='DONE' and op.get('error'):
 assert all(e['code'].startswith('ZONE_RESOURCE_POOL_EXHAUSTED') for e in op['error']['errors']),op
 instances=cloud(['compute','instances','list']);disks=cloud(['compute','disks','list']);assert not instances and not disks
 write(A/'reconciliation.json',{'instances':instances,'disks':disks,'checked_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'provider_rolled_back_allocation':True})
 a['status']='closed_capacity_unavailable';s['status']='other_zone_checks_authorized';write(P/'zone-sweep.json',s)
 print(json.dumps({'operation':'DONE','status':'capacity_unavailable','resources_empty':True}));raise SystemExit(3)
name=json.loads((A/'config.json').read_text())['run_id'];vm=cloud(['compute','instances','describe',name,'--zone='+a['zone']]);write(A/'instance.json',vm)
r=json.loads((A/'launch-request.json').read_text());assert vm['scheduling']['instanceTerminationAction']=='STOP' and vm['scheduling']['terminationTime']==r['provider_stop_utc'];assert all(not d['autoDelete'] for d in vm['disks']) and not vm['scheduling']['automaticRestart'] and all(not n.get('accessConfigs') for n in vm['networkInterfaces'])
assert vm['machineType'].endswith('/a2-highgpu-1g')
if op['status']=='DONE':
 assert not op.get('error'),op
 a.update(status='allocated_monitor_qualification',name=name);s['status']='allocated_no_further_attempts';write(P/'zone-sweep.json',s)
 ledger=json.loads((P/'spend-ledger.json').read_text());ledger.update(status='allocated_qualification_then_conditional_English',active_reserved_compute_usd=r['maximum_incremental_cost_usd']-8,active_attempt_directory=str(A),instance_id=vm['id'],no_vm_or_disk=False);write(P/'spend-ledger.json',ledger)
print(json.dumps({'operation':op['status'],'vm':vm['status'],'name':name,'zone':a['zone'],'fixed_stop':r['provider_stop_utc'],'safe_configuration':True}))
