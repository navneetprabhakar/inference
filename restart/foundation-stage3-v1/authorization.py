"""Owner receipt, immutable proposal/source pins and elapsed-budget gate. No ML imports."""
import hashlib,json,time
from pathlib import Path

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def validate_authorization(root,now=None):
 root=Path(root);now=time.time() if now is None else now
 c=json.loads((root/'contract.json').read_text())
 if c.get('current_stage_training_authorized') is not True:raise PermissionError('Successor training not approved')
 if not (root/'approval.json').is_file():raise PermissionError('Explicit successor approval receipt required')
 a=json.loads((root/'approval.json').read_text());proposal=json.loads((root/'proposal.json').read_text());clock=json.loads((root/'clock.json').read_text())
 if a.get('approved') is not True or not a.get('owner_message') or a.get('proposal_sha256')!=sha(root/'proposal.json'):raise PermissionError('Approval does not match frozen successor proposal')
 if c['next_stage_authorized'] or c['conversation_training_authorized'] or c['full_training_authorized']:raise PermissionError('Unauthorized scope expansion')
 expected=dict(model_parameters=15191712,parameter_ceiling=100000000,additional_retained_updates_max=1144,additional_retained_targets_max=149946368,aggregate_positions_cap=160000000,overall_original_position_cap=320000000,prior_new_run_positions_charged=153846537,wall_seconds_max=18000)
 if any(c.get(k)!=v for k,v in expected.items()):raise PermissionError('Successor limits differ from reviewed scope')
 if c['reference']!=proposal['reference'] or c['teacher_model']!='gpt-6-sol':raise PermissionError('Checkpoint or teacher changed')
 start=clock['start_epoch'];end=clock['authorized_stage_deadline_epoch']
 if not isinstance(start,(int,float)) or not isinstance(end,(int,float)) or start!=a['approved_epoch'] or end-start!=18000 or now<start or now>=end-300:raise PermissionError('Missing, changed or exhausted five-hour clock')
 if c['prior_new_run_positions_charged']+c['aggregate_positions_cap']>c['overall_original_position_cap']:raise PermissionError('Original position cap exceeded')
 pins=root/'source-pins.json'
 if sha(pins)!=proposal['source_pins_sha256']:raise PermissionError('Source manifest changed')
 for name,digest in json.loads(pins.read_text()).items():
  if sha(root/name)!=digest:raise PermissionError('Prepared source changed: '+name)
 return True
