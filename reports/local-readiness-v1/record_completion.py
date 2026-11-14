"""Record only completed local checks; pending GPU work never becomes a pass."""
import datetime,hashlib,json,subprocess
from pathlib import Path
from cloud_training.nano_checkpoint import validate_bundle
from cloud_training.nano_corpus_guard import verify_freeze
from cloud_training.nano_quality_gate import campaign_decision
P=Path('reports/local-readiness-v1');base=Path('runs/local-readiness-v1/base10b')
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert sha(base/'manifest.json')=='7d803e32928ca9ecc1fe38bf7d47c54bca80c0996d6bb006b718cfd851975e53'
validate_bundle(base)
preflight=json.loads((P/'base-preflight.json').read_text());assert preflight['status']=='admitted_inputs_verified_not_GPU_qualified' and preflight['packing_buffer_size']==1 and preflight['planned_updates']==35
log=(P/'tests.log').read_text();assert 'Ran 150 tests' in log and log.rstrip().endswith('OK')
assert json.loads((P/'gpu-proposal.json').read_text())['authorized_usd'] is None
port=subprocess.run(['lsof','-nP','-iTCP:8765','-sTCP:LISTEN'],capture_output=True,text=True);assert port.returncode==1 and not port.stdout.strip()
packet=verify_freeze('reports/corrective-corpus-v1')
base_receipt={'manifest_sha256':sha(base/'manifest.json'),'full_bundle_sha_verified':True,'local_path':str(base),'payload_bytes':(base/'payload.pt').stat().st_size,'source':'gs://forge-ownbase-a100-20261110/ownbase-v2/budget50-v1/base/checkpoints/checkpoint-bcfb32abdbba44eaa3c7107af1adb7b2','note':'Restored required immutable base for real CLI validation and future pilots. No new model trained.'}
(P/'base-restore-receipt.json').write_text(json.dumps(base_receipt,indent=2)+'\n')
code=['cloud_training/nano_sft.py','cloud_training/nano_quality.py','cloud_training/nano_package.py','cloud_training/nano_restart_compare.py','verify_nano_sft.py','verify_nano_quality.py','verify_nano_package.py','verify_nano_restart_compare.py','verify_nano_campaign_watch.py']
report={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'local_checks':'pass','gpu_authorized':False,'gpu_qualified':False,'tests_passed':150,'actual_training_cli_preflight':preflight,'freeze':packet,'http_8765':'off','new_training':False,'code_sha256':{p:sha(p) for p in code},'remaining_gates':['Explicit user-approved finite cap','Bind new STOP/non-auto-delete lease and bootstrap; reject retired DELETE launch path','CUDA4K memory/runtime/exact fresh-process restart and signal/backup/provider-stop qualification','Bounded pilot generated behavior, then separately gated release and selected-model local acceptance'],'caveats':['CPU and full-size MPS forward checks do not certify CUDA training.','Budget figures bound attempts, not guaranteed completion or repaired quality.']}
(P/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

checks={
 'data_review':'reports/corrective-corpus-v1/semantic-review.json',
 'group_split_audit':'reports/corrective-corpus-v1/candidate-split-audit.json',
 'policy_coverage':'reports/corrective-corpus-v1/candidate-4k/admission.json',
 'source_intent':'reports/corrective-corpus-v1/quality-contract.json',
 'token_mask_audit':str(P/'actual-packet-checks.json'),
 'release_suite_frozen':'reports/corrective-corpus-v1/freeze.json',
 'protected_suite_frozen':'reports/corrective-corpus-v1/protected-suite.json',
 'cpu_tests':str(P/'validation.json'),
 'generation_sentinels':str(P/'development-checks.json'),
 'local_qualification_plan':str(P/'gpu-proposal.json')}
state={'schema':1,'phase':'quality_hold_awaiting_cap_and_GPU_qualification','failed_pilots':0,'active_training_vms':0,'budget':{'authorized_usd':None,'spent_upper_bound_usd':0,'reserve_usd':5,'pilot_upper_bound_usd':10},'checks':{k:{'status':'pass','path':v,'sha256':sha(v)} for k,v in checks.items()}}
state['decision']=campaign_decision(state);assert state['decision']['action']=='hold_vm_off'
(P/'campaign-readiness.json').write_text(json.dumps(state,indent=2)+'\n')
