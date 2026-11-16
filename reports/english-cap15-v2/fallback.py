"""One explicitly reviewed capacity-only same-price fallback, original deadline."""
import datetime as dt,hashlib,json,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent;sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
if (P/'fallback-request.json').exists():raise ValueError('Fallback already considered; never retry')
r=json.loads((P/'launch-request.json').read_text());op=json.loads((P/'create-operation.json').read_text())
assert op['status']=='DONE' and op['error']['errors'][0]['code']=='ZONE_RESOURCE_POOL_EXHAUSTED_WITH_DETAILS'
assert json.loads((P/'disks-after-failure.json').read_text())==[]
xs=json.loads((P/'instances-after-failure.json').read_text());assert all(x['status']=='TERMINATED' and x['name']!=r['run_id'] for x in xs)
assert json.loads((P/'fallback-machine.json').read_text())['memoryMb']==87040
assert (dt.datetime.fromisoformat(r['provider_stop_utc'].replace('Z','+00:00'))-dt.datetime.now(dt.timezone.utc)).total_seconds()>2700
for x in r['inputs']:assert x['independent_readback'] and sha(Path(x['path']))==x['sha256']
assert sha(P/'bootstrap.sh')==r['bootstrap_sha256']
for n,h in json.loads((P/'local-preflight.json').read_text())['bound_files'].items():assert sha(P.parents[1]/n)==h
argv=[r['run_id']+'-a' if a==r['run_id'] else '--zone=us-central1-a' if a=='--zone=us-central1-f' else a for a in r['create_argv']]
assert '--termination-time='+r['provider_stop_utc'] in argv
request={'vm_name':r['run_id']+'-a','zone':'us-central1-a','provider_stop_utc':r['provider_stop_utc'],'create_argv':argv,'original_request_sha256':sha(P/'launch-request.json'),'review_sha256':sha(P/'ZONE_FALLBACK.md'),'same_rate_and_runtime_bound':True}
(P/'fallback-request.json').write_text(json.dumps(request,indent=2)+'\n')
l=json.loads((P/'spend-ledger.json').read_text());l['allocations'][0].update(state='closed_capacity_unavailable',observed_compute_usd=0,no_vm_or_disk=True)
l['allocations'].append({'run_id':request['vm_name'],'state':'create_requested','compute_reserved_usd':r['compute_reserved_usd'],'request_sha256':sha(P/'fallback-request.json')})
assert sum(x['compute_reserved_usd'] for x in l['allocations'] if x['state']=='create_requested')<=5
(P/'spend-ledger.json').write_text(json.dumps(l,indent=2)+'\n')
(P/'fallback-response.json').write_text('{"state":"in_flight_reconcile_before_any_action"}\n')
try:
 c=subprocess.run(argv,capture_output=True,text=True,timeout=120);out={'returncode':c.returncode,'stdout':c.stdout,'stderr':c.stderr}
except BaseException as e:out={'state':'uncertain_reconcile_provider','error':repr(e)}
(P/'fallback-response.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
