import json,subprocess,datetime as dt
from pathlib import Path
P=Path(__file__).resolve().parent
def cloud(a):return json.loads(subprocess.check_output(['gcloud',*a,'--project=executespecv1','--format=json'],text=True,timeout=90))
def write(n,j):(P/n).write_text(json.dumps(j,indent=2)+'\n')
ops=json.loads((P/'operations.json').read_text());assert len(ops)==1
op=cloud(['compute','operations','describe',ops[0]['name'],'--zone=us-central1-a']);write('operation.json',op)
if op['status']!='DONE':print(json.dumps({'status':op['status']}));raise SystemExit(2)
if op.get('error'):
 inv=cloud(['compute','instances','list']);disks=cloud(['compute','disks','list']);write('allocation-reconciliation.json',{'instances':inv,'disks':disks,'error':op['error']})
 assert not inv and not disks,'Resources remain: reconcile before next attempt'
 assert all(e['code'].startswith('ZONE_RESOURCE_POOL_EXHAUSTED') for e in op['error']['errors']),op
 print(json.dumps({'status':'capacity_unavailable','resources_empty':True}));raise SystemExit(3)
config=json.loads((P/'config.json').read_text());vm=cloud(['compute','instances','describe',config['run_id'],'--zone=us-central1-a']);write('instance.json',vm)
r=json.loads((P/'launch-request.json').read_text());assert vm['scheduling']['instanceTerminationAction']=='STOP' and vm['scheduling']['terminationTime']==r['provider_stop_utc']
assert all(not d['autoDelete'] for d in vm['disks']) and not vm['scheduling']['automaticRestart'] and all(not n.get('accessConfigs') for n in vm['networkInterfaces'])
ledger=json.loads((P/'spend-ledger.json').read_text());ledger.update(status='allocated_qualification_only',active_reserved_compute_usd=ledger['reserved_campaign_usd']-ledger['reserve_usd']-ledger['prior_cost_reserve_usd'],instance_id=vm['id'],zone='us-central1-a',checked_utc=dt.datetime.now(dt.timezone.utc).isoformat());write('spend-ledger.json',ledger)
write('zone-sweep.json',{'approval':'User approved $40 cumulative and A100','campaign_deadline_utc':r['campaign_deadline_utc'],'status':'allocated_no_further_attempts','attempts':[{'zone':'us-central1-a','directory':str(P.relative_to(Path.cwd())),'name':vm['name'],'status':'allocated_monitor_qualification'}]})
print(json.dumps({'status':vm['status'],'name':vm['name'],'zone':'us-central1-a','provider_stop':r['provider_stop_utc'],'safe_configuration':True}))
