"""One newly authorized zone attempt, with reconciliation; no repeated failed request."""
import argparse,json,datetime as dt,subprocess,hashlib,fcntl,time
from pathlib import Path
P=Path('reports/ganesh-a100-cap40-v1');ROOT=Path.cwd()
parser=argparse.ArgumentParser();parser.add_argument('--zone',required=True,choices=['us-central1-b','us-central1-c','us-central1-f','us-east1-b','us-west1-b']);args=parser.parse_args();zone=args.zone;region=zone.rsplit('-',1)[0]
def run(a,timeout=120):
 r=subprocess.run(a,capture_output=True,text=True,timeout=timeout)
 if r.returncode:raise RuntimeError('Command failed: '+repr(a[:4])+' '+r.stderr[-3000:])
 return r
def cloud(a):return json.loads(run(['gcloud',*a,'--project=executespecv1','--format=json']).stdout)
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
with (P/'zone-sweep.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 original=json.loads((P/'launch-request.json').read_text());deadline=dt.datetime.fromisoformat(original['campaign_deadline_utc'].replace('Z','+00:00'))
 now=dt.datetime.now(dt.timezone.utc);assert (deadline-now).total_seconds()>7200,'Original campaign lease too short; do not extend'
 assert not cloud(['compute','instances','list']) and not cloud(['compute','disks','list']),'Reconcile resources before next attempt'
 S=P/'zone-sweep.json';state=json.loads(S.read_text()) if S.exists() else {'approval':'User keep checking in other zones; approved $40 cumulative A100 cap','campaign_deadline_utc':original['campaign_deadline_utc'],'attempts':[],'status':'authorized_other_zones'}
 assert not any(a['zone']==zone and a['status']!='preflight_failed_no_allocation' for a in state['attempts']),'Each zone tried once only'
 assert all(a['status'] in ('closed_capacity_unavailable','preflight_unsupported','preflight_failed_no_allocation') for a in state['attempts']),'Prior attempt not reconciled'
 assert json.loads((P/'spend-ledger.json').read_text())['active_reserved_compute_usd']==0
 name=zone+'-'+now.strftime('%H%M%S');A=P/'attempts'/name;A.mkdir(parents=True)
 attempt={'zone':zone,'directory':str(A),'status':'preparing','requested_utc':now.isoformat()};state['attempts'].append(attempt);write(S,state)
 reg=cloud(['compute','regions','describe',region]);write(A/'region.json',reg)
 assert any(q['metric']=='NVIDIA_A100_GPUS' and q['limit']-q['usage']>=1 for q in reg['quotas'])
 machine=cloud(['compute','machine-types','describe','a2-highgpu-1g','--zone='+zone]);write(A/'machine.json',machine);assert machine['memoryMb']==87040
 subnet=cloud(['compute','networks','subnets','describe','default','--region='+region]);write(A/'subnet.json',subnet);assert subnet.get('privateIpGoogleAccess'),'Private GCS access not configured; no network changes implicit'
 cat=json.loads((P/'price-catalog.json').read_text());assert (now-dt.datetime.fromisoformat(cat['checked_utc'])).total_seconds()<86400
 for sku in ('2922-40C5-B19F','2390-DCAF-DA38','039F-D0DA-4055','6AE1-525F-8B80'):assert region in next(s for s in cat['skus'] if s['skuId']==sku)['serviceRegions']
 for n in ('gpu_qualify.py','capture_compare.py','signal_inject.py','upload_fault_shim.py','decode_benchmark.py','bootstrap.sh','price-catalog.json','image.json','adverse-checks.json','local-tests.log'):(A/n).write_bytes((P/n).read_bytes())
 # Same verified runtime; new configuration/packet/lease and approval-bound request.
 prep=(P/'prepare_launch.py').read_text().replace("P=Path('reports/ganesh-a100-cap40-v1');R=Path('runs/ganesh-a100-cap40-v1');ROOT=Path.cwd()",f"P=Path({str(A)!r});R=Path({('runs/ganesh-a100-cap40-v1/'+name)!r});R.mkdir(parents=True);ROOT=Path.cwd()")
 prep=prep.replace("now+dt.timedelta(hours=6,minutes=45)",f"dt.datetime.fromisoformat({original['campaign_deadline_utc']!r}.replace('Z','+00:00'))")
 prep=prep.replace("'--zone=us-central1-a'",repr('--zone='+zone))
 prep=prep.replace("inputs=[upload(runtime,prefix+'/inputs/runtime.tar.gz'),upload(packet,prefix+'/inputs/qualification-packet.tar.gz')]", """prior=json.loads(Path('reports/ganesh-a100-cap40-v1/input-backups.json').read_text())['inputs'][0]
assert prior['independent_readback'] and prior['sha256']==sha(runtime)
remote_runtime=json.loads(command(['gcloud','storage','objects','describe',prior['uri'],'--format=json']).stdout)
runtime_hashes=json.loads(command(['gcloud','storage','hash',str(runtime),'--format=json']).stdout)[0]
assert remote_runtime['crc32c_hash']==runtime_hashes['crc32c_hash'] and int(remote_runtime['size'])==runtime.stat().st_size
write(P/'runtime-reuse-check.json',{'prior_independent_readback':prior,'current_remote_metadata':remote_runtime,'crc32c_match':True,'sha256_matches_prior_readback':True})
inputs=[prior,upload(packet,prefix+'/inputs/qualification-packet.tar.gz')]""")
 prep=prep.replace("'User: approved ho ahead, responding to explicit $20 cap question'","'User: approved ho ahead ($20 cap), then keep checking in other zones; same cumulative cap and campaign deadline'")
 (A/'prepare_launch.py').write_text(prep)
 run([str(ROOT/'.venv/bin/python'),str(A/'prepare_launch.py')],timeout=600)
 allocation=(P/'allocate_once.py').read_text().replace("ROOT=P.parents[1]","ROOT=Path.cwd()").replace("'zone':'us-central1-a'",f"'zone':{zone!r}")
 (A/'allocate_once.py').write_text(allocation)
 attempt['status']='allocation_intent';write(S,state)
 run([str(ROOT/'.venv/bin/python'),str(A/'allocate_once.py')],timeout=180)
 operations=json.loads((A/'operations.json').read_text());assert len(operations)==1
 for _ in range(30):
  op=cloud(['compute','operations','describe',operations[0]['name'],'--zone='+zone]);write(A/'operation.json',op)
  if op['status']=='DONE':break
  time.sleep(2)
 else:raise RuntimeError('Operation unresolved; no further attempts')
 if op.get('error'):
  assert all(e['code'].startswith('ZONE_RESOURCE_POOL_EXHAUSTED') for e in op['error']['errors']),'Noncapacity failure: HOLD'
  for _ in range(12):
   instances=cloud(['compute','instances','list']);disks=cloud(['compute','disks','list'])
   if not instances and not disks:break
   time.sleep(3)
  assert not instances and not disks,'Failed allocation resources remain; HOLD'
  write(A/'reconciliation.json',{'instances':instances,'disks':disks,'checked_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'observed_compute_usd':0})
  attempt['status']='closed_capacity_unavailable';state['status']='other_zone_checks_authorized'
 else:
  name=json.loads((A/'config.json').read_text())['run_id'];vm=cloud(['compute','instances','describe',name,'--zone='+zone]);write(A/'instance.json',vm)
  request=json.loads((A/'launch-request.json').read_text());assert vm['scheduling']['instanceTerminationAction']=='STOP' and vm['scheduling']['terminationTime']==request['provider_stop_utc']
  assert all(not d['autoDelete'] for d in vm['disks']) and not vm['scheduling']['automaticRestart'] and all(not n.get('accessConfigs') for n in vm['networkInterfaces'])
  attempt.update(status='allocated_monitor_qualification',name=name);state['status']='allocated_no_further_attempts'
  ledger=json.loads((P/'spend-ledger.json').read_text());ledger.update(status='allocated_qualification_only',active_reserved_compute_usd=ledger['reserved_campaign_usd']-8,active_attempt_directory=str(A),no_vm_or_disk=False);write(P/'spend-ledger.json',ledger)
 write(S,state);print(json.dumps(attempt))
