"""CPU-only explicit metadata preparation. Never invokes training or loads weights."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import own_base_sft_train as train
OUT=Path(__file__).resolve().parent

def read(path):return json.loads(Path(path).read_text())
def pin(path):return {'path':str(Path(path).resolve()),'sha256':train.digest(path)}
def require(condition,message):
 if not condition:raise ValueError(message)

def main():
 allocation=read(ROOT/'reports/grounded-sft-preflight-v1/allocation.json')
 prepath=ROOT/'reports/grounded-sft-preflight-v1/activation-v1.json';pre=read(prepath)
 directory=Path(pre['run']);hardwarepath=directory/'hardware-receipt.json'
 hardware=read(hardwarepath) # Refuses absent/incomplete preflight; no placeholder acceptance.
 require(hardware['state']=='PASS' and hardware['disposable_weights_released'] and hardware['validation_exercised'],'complete hardware PASS required')
 for key,file in [('watchdog_sha256','watchdog.json'),('candidate_sha256','hardware-candidate.json'),('ledger_sha256','preflight-ledger.json'),('selection_sha256','selection.json')]:
  require(hardware[key]==train.digest(directory/file),'hardware proof changed: '+file)
 watch=read(directory/'watchdog.json');ledger=read(directory/'preflight-ledger.json');signature=ledger.pop('sha256')
 require(signature==hashlib.sha256(train.canonical(ledger)).hexdigest(),'ledger signature')
 require(watch['spec_sha256']==train.digest(prepath) and watch['returncode']==0 and watch['within_deadline'] and not watch['timed_out'] and not watch['interrupted'],'watchdog incomplete')
 require(ledger['identity']['spec']==pre and ledger['identity']['spec_sha256']==train.digest(prepath) and ledger['completed_updates']==40 and ledger['completed_evaluation_rows']==48 and ledger['pending'] is None,'incomplete preflight ledger')
 require(hardware['parent']==pre['parent'] and hardware['datasets']=={s['name']:s['receipt']['sha256']for s in allocation['datasets']},'preflight parent/data differ')
 require(hardware['runtime_sha256']==pre['runtime_sha256'] and hardware['preflight_code_sha256']==pre['preflight_code_sha256'],'preflight code identity')
 for pins in (pre['runtime_sha256'],pre['preflight_code_sha256']):
  for name,sha in pins.items():require(train.digest(ROOT/name)==sha,'code changed: '+name)
 spec=read(ROOT/'reports/own-base-sft-diagnostic-v1/activation.json')
 require(spec['parent']==pre['parent'],'selected parent changed')
 spec.update(run=str(ROOT/'runs/own-base-grounded-sft-diagnostic-01'),datasets=allocation['datasets'],hardware_preflight=pin(hardwarepath),code_sha256=pre['runtime_sha256'],checkpoint_updates=100,validation_updates=2000,scheduler=allocation['scheduler_proposal'],work_limits=allocation['work_limits'],stop_paths=pre['stop_paths'])
 require((spec['active_seconds'],spec['calendar_seconds'],spec['lease_seconds'])==(28800,172800,14400),'agreed time ceilings')
 train.validate_launch(spec,Path(spec['run'])) # Metadata only; no verified_parent call.
 data=train.Sources(spec['datasets']);plan=train.updates(data,spec)
 require(len(plan)==3975,'schedule count')
 events={0,len(plan)}|set(range(spec['validation_updates'],len(plan),spec['validation_updates']))
 require(sorted(events)==allocation['evaluation_steps'],'evaluation cadence')
 total=dict.fromkeys(train.WORK,0)
 for source in spec['datasets']:
  batches=[b for b in plan if data.rows['train'][b[0]]['_source']==source['name']]
  ev=[i for i,r in enumerate(data.rows['validation'])if r['_source']==source['name']]
  require(len(ev)==source['validation_rows'] and source['passes']==1,'full development / one pass required')
  cost={k:sum(train.work_for(data,b,1)[k]for b in batches)+len(events)*train.work_for(data,ev,1,'validation')[k]for k in train.WORK}
  require(cost==allocation['sources'][source['name']]['nominal'],'nominal source differs')
  for k in train.WORK:
   require(cost[k]<=source['work_limits'][k],'source work limit');total[k]+=cost[k]
 require(total==allocation['nominal'],'global nominal differs')
 # Root reviews this exact metadata before any --execute-reviewed invocation.
 destination=OUT/'activation.json'
 require(not destination.exists(),'refuse overwriting frozen activation')
 destination.write_text(json.dumps(spec,indent=2)+'\n')
 print(json.dumps({'state':'prepared_pending_root_launch_review','activation':pin(destination),'updates':len(plan),'nominal':total},indent=2))
if __name__=='__main__':main()
