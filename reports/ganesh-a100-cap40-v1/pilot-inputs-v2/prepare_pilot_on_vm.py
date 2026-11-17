"""Bind approved English tasks only after actual A100 qualification and fixed provider-stop verification.
Creates a request; never starts training, changes budgets, or fabricates semantic review.
"""
import datetime as dt,hashlib,json,subprocess,sys
from pathlib import Path
from cloud_training.nano_recovery_controller import validate_graph,canonical
from cloud_training.nano_recovery_gate import inspect,digest
from cloud_training.nano_recovery_tasks import train_argv
ROOT=Path('/opt/english');P=ROOT/'pilot-evidence';P.mkdir(exist_ok=True)
cfg=json.loads((ROOT/'config.json').read_text());controls=json.loads((P/'controls.json').read_text())
qpath=ROOT/'results/qualification.json';q=json.loads(qpath.read_text())
assert q['status']=='qualification_pass_pending_provider_stop' and q['backup_verified']
assert all(q[k]['status']=='pass' for k in ('comparison','signal','rollback','traces'))
assert q['fresh_process_gcs_restore'] and q['upload_rejection']['real_gcs_rejection'] and q['upload_rejection']['no_committed_receipt']
assert q['decode_benchmark']['fits_predeclared_probe_timeouts']
provider=json.loads((P/'provider-stop-schedule.json').read_text())
assert provider['actual_stop_deferred_until_closeout'] and provider['same_instance_retained'] and provider['fixed_stop_verified'] and provider['disk_preserved_on_stop']
assert provider['instance_id']==controls['instance_id'] and provider['final_provider_stop_utc']==cfg['deadline_utc']
assert controls['approved_cap_usd']==40 and controls['prior_cost_reserve_usd']==2 and controls['future_reserve_usd']==6
inventory=json.loads((P/'inventory.json').read_text());assert len(inventory['instances'])==1
vm=inventory['instances'][0];assert vm['id']==controls['instance_id'] and vm['status']=='RUNNING' and vm['machineType'].endswith('/a2-highgpu-1g')
assert vm['scheduling']['terminationTime']==cfg['deadline_utc'] and vm['scheduling']['instanceTerminationAction']=='STOP' and all(not d['autoDelete'] for d in vm['disks'])
now=dt.datetime.now(dt.timezone.utc);stop=dt.datetime.fromisoformat(cfg['deadline_utc'].replace('Z','+00:00'));start=dt.datetime.fromisoformat(controls['lease_start_utc'].replace('Z','+00:00'))
assert (stop-now).total_seconds()>3*3600,'Insufficient time for bounded training, full probes and backup reserve'
r=json.loads((P/'controller-template.json').read_text());oldbase=r['training_inputs']['base']
r['files'].pop('runs/ganesh-controller-v1/runtime-qualified-local.tar.gz')
r['files'].pop(oldbase+'/manifest.json');r['files']['base/manifest.json']=cfg['base_manifest_sha256']
r['files']['runtime.tar.gz']=controls['runtime_sha256'];assert digest(ROOT/'runtime.tar.gz')==controls['runtime_sha256']
r['files']['qualification-runtime.tar.gz']=controls['qualification_runtime_sha256'];assert digest(ROOT/'qualification-runtime.tar.gz')==controls['qualification_runtime_sha256']
equivalence=json.loads((P/'runtime-equivalence.json').read_text());assert equivalence['changed_files']==['cloud_training/nano_recovery_gate.py'] and equivalence['training_optimizer_serving_tokenizer_upstream_sources_unchanged']
r['files']['pilot-evidence/runtime-equivalence.json']=digest(P/'runtime-equivalence.json')
r['files']['cloud_training/nano_recovery_gate.py']=controls['recovery_gate_sha256']
for name,h in r['files'].items():assert digest(ROOT/name)==h,name
r['training_inputs'].update(repo='nanochat-source',base='base',tokenizer='tokenizer')
r['protected_roots']=['base' if n==oldbase else n for n in r['protected_roots']]
r['python']=sys.executable
for t in r['tasks']:
 if t['kind']=='command':t['argv'][0]=sys.executable
r.update(provider_stop_validation='closeout',machine='a2-highgpu-1g',lease_start_utc=controls['lease_start_utc'],provider_stop_utc=cfg['deadline_utc'],worker_stop_utc=(stop-dt.timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%SZ'),backup_reserve_seconds=3600,maximum_incremental_cost_usd=controls['campaign_envelope_usd'],reserve_usd=6,backup_prefix=cfg['backup_prefix']+'/english',approval_scope='User approved $40 cumulative A100 English training; same VM retained; qualification then bounded fit and conditional curriculum')
validate_graph(r,ROOT)
# Actual contract/tokenizer/data validation using exactly the frozen task recipe.
for ident in ('fit_train','curriculum_train'):
 task=next(t for t in r['tasks'] if t['id']==ident)
 with (P/(ident+'-preflight.log')).open('x') as f:subprocess.run(train_argv(r,task,ROOT)+['--validate-only'],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
# Validation-only may make an output directory; require no training artifacts and
# preserve its evidence outside the task destination so controller won't overwrite.
for ident in ('fit_train','curriculum_train'):
 task=next(t for t in r['tasks'] if t['id']==ident);directory=ROOT/task['directory']
 if directory.exists():
  assert not list(directory.glob('step-*')) and not (directory/'result.json').exists()
  directory.rename(P/(ident+'-preflight-output'))
for name in ('controller-template.json','controls.json','provider-stop-schedule.json'):
 r['files']['pilot-evidence/'+name]=digest(P/name)
spec=canonical({k:v for k,v in r.items() if k not in ('authorization','evidence')})
r['authorization']={'spec_sha256':spec,'explicit_user_approval':True,'approval_reference':'User: use A100 instead of L4; $40 total; retain VM through useful work; goal English conversation','cap_usd':40,'retain_vm_until_work_complete':True,'expires_utc':cfg['deadline_utc']}
r['evidence']={}
def proof(name,source,extra=None):
 body={'status':'pass','check':name,'spec_sha256':spec,'checked_utc':now.isoformat(),'raw_receipt':str(source.relative_to(ROOT)),'raw_sha256':digest(source),**(extra or {})};path=P/(name+'-receipt.json');path.write_text(json.dumps(body,indent=2)+'\n');r['evidence'][name]={'path':str(path.relative_to(ROOT)),'sha256':digest(path)}
proof('fresh_inventory',P/'inventory.json')
backups=json.loads((P/'input-backups.json').read_text());assert all(i['independent_readback'] for i in backups['inputs']);assert backups['inputs'][0]['sha256']==controls['runtime_sha256']
proof('input_backups',P/'input-backups.json',{'base_manifest_sha256':cfg['base_manifest_sha256'],'gpu_base_and_resume_readback':True})
proof('price_quote',P/'price-catalog.json',{'hourly_rate_usd':controls['vm_disk_hourly_usd'],'margin_multiplier':1.25})
for name in ('cuda_runtime','exact_restart','signal_recovery','gcs_restore','upload_rejection'):proof(name,qpath)
proof('provider_stop_configured',P/'provider-stop-schedule.json')
admission=ROOT/'reports/ganesh-english-curriculum-v2/admission.json';assert json.loads(admission.read_text())['training_admitted']
proof('production_admission',admission)
proof('production_preflight',P/'curriculum_train-preflight.log')
gate=inspect(ROOT,r,'fit');assert gate['allowed'],gate
path=ROOT/'pilot-request.json'
with path.open('x') as f:json.dump(r,f,indent=2);f.write('\n')
(P/'fit-gate.json').write_text(json.dumps(gate,indent=2)+'\n');print(json.dumps({'status':'prepared_not_started','gate':gate,'remaining_hours':(stop-now).total_seconds()/3600}))
