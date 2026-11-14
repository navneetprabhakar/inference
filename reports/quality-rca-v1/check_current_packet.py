"""Exercise production preflight against the actual completed SFT packet; no GPU."""
import sys,json,hashlib
from pathlib import Path
sys.path.insert(0,str(Path('.').resolve()));sys.path.insert(0,str(Path('runs/nanochat-source').resolve()))
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_sft import load_manifest,JsonlConversations
from cloud_training.nano_quality_gate import dataset_coverage,contract_errors,campaign_decision
P=Path('reports/quality-rca-v1');root=Path('runs/ownbase-budget50-v1/sft-2k')
toksha='ad777bb448ea8fcf115835548596f9303f3ee5e85a014b0bb315567091080cc5';tok=RustBPETokenizer.from_directory('runs/ownbase-v2-data/tokenizer');m=load_manifest(root/'manifest.json',toksha,2048)
cov={k:dataset_coverage(JsonlConversations(m[k]['_file'],tok,m[k]['sha256'],context=2048)) for k in ['train','validation']}
contract={'schema':1,'objective':'conversation_and_tools','status':'BLOCKED_TEMPLATE_NOT_LAUNCH_AUTHORIZATION','dataset_manifest_sha256':m['_sha256'],'tokenizer_sha256':toksha,'context_tokens':2048,'required_parent_manifest_sha256':'d453f03566861975b85d85120b097c8554ba800f2e93d87a0448e4c4149992ba','release_suite_sha256':None,'protected_suite_sha256':None,'unresolved_required_data':['User-requested V21 3K–4K examples do not fit the actual 2048-token packet; qualify 4096 context separately and record any staged exclusions.'],'coverage':{'minimum_training_turns':{'disabled_no_call':100,'enabled_no_call':100,'enabled_call':100},'minimum_unique_assistant_targets':100000,'minimum_family_sessions':{'natural_dialogue_4k':100,'calculate':50,'convert':50,'tool_correction':50}},'recipe_limits':{'max_epochs':2,'max_lr_multiplier':.125,'max_eval_interval':10},'regression':{'relative_tolerance':.05,'patience':2},'release':{'minimum_turns_by_category':{'natural':60,'code_state':60,'tool':60},'minimum_category_pass_rate':.9,'minimum_complete_session_rate':.8},'threshold_note':'Provisional engineering risk limits, not empirically sufficient training sizes or statistical guarantees. Do not lower them to make a failed experiment pass. Final curriculum/family taxonomy and immutable release/protected suite hashes must be frozen before any new pilot.'}
(P/'blocked-contract-template.json').write_text(json.dumps(contract,indent=2)+'\n')
a=json.loads((root/m['admission']['receipt']).read_text());errors=contract_errors(contract,manifest=m,admission=a,train=cov['train'],dev=cov['validation'],epochs=8,lr_multiplier=1,eval_interval=50)
assert any('enabled_no_call' in e for e in errors)
(P/'current-packet-preflight.json').write_text(json.dumps({'status':'blocked','quality_accepted':False,'errors':errors,'coverage':cov},indent=2)+'\n')
state={'schema':1,'phase':'quality_hold','failed_pilots':0,'active_training_vms':0,'budget':{'authorized_usd':None,'spent_upper_bound_usd':0,'reserve_usd':None,'pilot_upper_bound_usd':None},'checks':{},'note':'Prior $55 campaign closed. No new numeric training budget assigned. This is a new remediation campaign, not an automatic extension.'}
state['decision']=campaign_decision(state);(P/'campaign-state.json').write_text(json.dumps(state,indent=2)+'\n');print(json.dumps(errors,indent=2))
