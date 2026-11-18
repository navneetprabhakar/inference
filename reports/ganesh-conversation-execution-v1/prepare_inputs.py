"""Create reviewed pilot-only manifests. Never allocates or authorizes a GPU."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from cloud_training.nano_chat_format import VERSION
P=Path(__file__).resolve().parent;C=P.parent/'ganesh-conversation-pilot-v1'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(name,value):
 path=P/name
 if path.exists():raise FileExistsError(path)
 path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
spec=json.loads((C/'pilot-spec.json').read_text());freeze=json.loads((C/'freeze.json').read_text())
for name,h in freeze['files'].items():assert sha(C/name)==h
write('authorization.json',{'schema':1,'approved':True,'user_message':'ok approved','interpreted_scope':'New $25 A100 cap for reviewed controlled Fit30 pilot; local readiness and changed-path CUDA checks required before learning','approved_usd':25,'machine':'a2-highgpu-1g','region':'us-central1','maximum_vm_count':1,'maximum_compute_minutes_including_fallback':196,'recovery_disk_gib':200,'automatic_budget_extension':False,'automatic_retry':False,'release_authorized':False,'proposal_sha256':sha(C/'pilot-spec.json'),'cost_plan_sha256':sha(C/'cost-plan.json')})
for arm,name in spec['arms'].items():
 admission={'schema':1,'training_admitted':True,'scope':'Reviewed controlled pilot only; does not clear allocation/runtime gates','release_eligible':False,'format_version':VERSION,'context_tokens':2048,'tokenizer_sha256':spec['tokenizer_sha256'],'parent_manifest_sha256':spec['parent_manifest_sha256'],'jsonl_sha256':[sha(C/name),sha(C/'development.jsonl')],'candidate_freeze_sha256':sha(C/'freeze.json'),'review_sha256':sha(C/'review.json'),'source_manifest_sha256':sha(C/'source-manifest.json')}
 write(arm+'-admission.json',admission)
 manifest={'schema':1,'training_admitted':True,'format_version':VERSION,'context_tokens':2048,'tokenizer_sha256':spec['tokenizer_sha256'],'admission':{'receipt':arm+'-admission.json','sha256':sha(P/(arm+'-admission.json'))},'train':{'file':'../ganesh-conversation-pilot-v1/'+name,'sha256':sha(C/name)},'validation':{'file':'../ganesh-conversation-pilot-v1/development.jsonl','sha256':sha(C/'development.jsonl')}}
 write(arm+'-manifest.json',manifest)
 rows=[json.loads(l) for l in (C/name).read_text().splitlines()];families=sorted({r['family'] for r in rows})
 contract={'schema':1,'objective':'controlled_conversation_pilot','release_eligible':False,'dataset_manifest_sha256':sha(P/(arm+'-manifest.json')),'tokenizer_sha256':spec['tokenizer_sha256'],'context_tokens':2048,'required_parent_manifest_sha256':spec['parent_manifest_sha256'],'protected_suite_sha256':sha(ROOT/'cloud_training/evaluation/conversation-tools-dev.json'),'training_sha256':sha(C/name),'block_plan_sha256':sha(C/'exposure-plan.json'),'block_arm':arm,'review_sha256':sha(C/'review.json'),'source_manifest_sha256':sha(C/'source-manifest.json'),'coverage':{'minimum_training_turns':{'disabled_no_call':1,'enabled_no_call':1,'enabled_call':1},'minimum_unique_assistant_targets':1128 if arm=='control' else 2286,'minimum_family_sessions':{f:1 for f in families}},'recipe_limits':{'max_epochs':1,'max_lr_multiplier':.25,'max_eval_interval':5,'max_pilot_updates':40},'regression':{'relative_tolerance':.05,'patience':2},'unresolved_required_data':[]}
 write(arm+'-contract.json',contract)
print('Prepared two pilot-only input contracts and $25 approval receipt; no VM launched.')
