"""Validate a paused proposal using CPU JSON/arithmetic only; not a launcher."""
import ast,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parents[1]
def read(name):return json.loads((ROOT/name).read_text())
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
 return h.hexdigest()
def main():
 p=read('plan.json');phases={r['id']:r for r in p['phases']};b=p['budgets'];m=p['fixed_model'];r=read('reference-snapshot.json')
 assert p['status']=='PROPOSED_ONLY_ALL_EXECUTION_PAUSED'
 assert all(not p['authority'][k] for k in ['model_inference_authorized','training_authorized','data_admission_authorized','paid_teacher_authorized','new_downloads_authorized','conversation_training_authorized','tool_training_authorized'])
 assert m['parameters']==15191712 and m['parameters']<m['ceiling']==100000000
 assert m['targets_per_update']==m['context']*m['microbatch']*m['accumulation']==131072
 assert [x['id'] for x in p['phases']]==['R0','D0','R1','R2']
 assert sum(x['wall_minutes_cap'] for x in p['phases'])==b['wall_minutes_cap_sum']==495
 assert sum(x['positions_cap'] for x in p['phases'])==b['new_student_processed_positions_cap']==88000000
 assert sum(x['teacher_requests_cap'] for x in p['phases'])==b['new_teacher_requests_cap']==38
 assert b['new_teacher_observed_output_plus_reasoning_tokens_cap']==38*8000==304000
 assert b['combined_teacher_requests_ceiling']==b['closed_prior_teacher_requests']+38
 assert b['combined_teacher_output_plus_reasoning_tokens_ceiling']==b['closed_prior_teacher_output_plus_reasoning_tokens']+304000
 assert b['combined_continuation_resolution_positions_ceiling']==b['closed_prior_continuation_resolution_positions']+88000000
 assert sum(a['updates'] for a in phases['R1']['arms'])+phases['R2']['updates']==512
 physical=sum(a['targets'] for a in phases['R1']['arms'])+phases['R2']['targets'];assert physical==b['new_physical_training_targets']==67108864
 assert phases['R1']['arms'][1]['targets']+phases['R2']['targets']==b['new_selected_retained_targets_max']==50331648
 assert b['new_broad_exposures_max']==b['new_selected_retained_targets_max']//2==25165824
 assert b['new_broad_exposures_max']<=3*phases['D0']['minimum_native_broad_content_tokens']['train']
 for phase,actual in [('R0',60),('R1',72),('R2',96)]:
  packets=phases[phase]['teacher_packets'];assert packets['rounds']==2
  assert packets['packets_per_round']*12==actual
  assert packets['packets_per_round']*2==phases[phase]['teacher_requests_cap']
  assert packets['anchors_per_packet']==4 and packets['total_rows_per_request']==16
 assert phases['R1']['arms'][0]['mixture']['native_TinyStories']==1
 assert phases['R1']['arms'][1]['mixture']==phases['R2']['mixture']
 assert phases['R1']['LR_both']==phases['R2']['LR']==m['training_LR']==.00005
 assert phases['R2']['stop_even_if_pass'] and p['after_R2']['always_stop']
 assert p['reporting']['written_interval_seconds']==600
 for c in p['source_candidates']:assert sha(PROJECT/c['path'])==c['sha256']
 for path,digest in r['files'].items():assert sha(PROJECT/path)==digest,path
 for f in ROOT.glob('*.py'):ast.parse(f.read_text())
 result=dict(status='PROPOSAL_CONSISTENCY_PASS_NO_EXECUTION',checks=['All execution authority remains false','Source checkpoint and reference hashes match','Phase deadlines/positions/teacher requests add correctly','All matched-work and retained-token calculations agree','Packet counts include repeated reviews and all anchors','Only broader B can release R2; final stop retained','All source syntax parses'],phase_wall_cap_minutes=495,new_training_targets=physical,new_retained_targets_max=50331648,teacher_calls_max=38,model_inference=0,training_updates=0,teacher_requests=0,plan_sha256=sha(ROOT/'plan.json'),readable_plan_sha256=sha(ROOT/'PLAN.md'))
 (ROOT/'validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
