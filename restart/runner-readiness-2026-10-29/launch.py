"""Sequential four-arm screen, gated on a separately approved, frozen launch receipt."""
import argparse,gc
from runner import *
from preservation import PreservationEvaluator

def run(approval_path):
 approval=read(approval_path)
 # This implementation is reviewable now, but no approval receipt exists in this phase.
 required=['training_authorized','numerical_resume_passed','common_lr_selected','feasibility_passed','preservation_policy_reviewed']
 if any(approval.get(k) is not True for k in required):raise RuntimeError('LAUNCH_GATES_NOT_MET')
 identity=verify_manifest()
 if approval.get('runner_manifest_sha256')!=sha(P/'launch-freeze.json'):raise RuntimeError('UNAPPROVED_RUNNER')
 for name,h in read(P/'launch-freeze.json')['files'].items():
  if sha(PROJECT/name)!=h:raise RuntimeError('LAUNCH_INPUT_CHANGED')
 if approval.get('phase_manifest_sha256')!=identity:raise RuntimeError('UNAPPROVED_INPUTS')
 lr=approval['learning_rate']
 if lr not in [2e-5,1e-4,5e-4]:raise ValueError('UNDECLARED_LR')
 limits=read(P/'config.json')['ceilings'];caps=dict(positions=limits['input_positions'],updates=limits['updates'],assistant=limits['assistant_eos_targets'],narrative=limits['narrative_targets'],seconds=limits['active_model_seconds'])
 # Calibration must already have used this same campaign ledger; no independent budget reset.
 work=P/'private/screen';work.mkdir(parents=True,exist_ok=True)
 ledger=work/'campaign.sqlite'
 if not ledger.exists():raise RuntimeError('CALIBRATION_LEDGER_REQUIRED')
 meter=Meter(ledger,caps,True);inputs=Inputs();state_path=work/'campaign.json'
 state=read(state_path) if state_path.exists() else {'next_arm':0,'approval_sha256':sha(approval_path)}
 if state['approval_sha256']!=sha(approval_path):raise RuntimeError('APPROVAL_CHANGED')
 atomic(state_path,json.dumps(state).encode())
 arms=inputs.config['arms']
 for index in range(state['next_arm'],len(arms)):
  resources();arm=arms[index];folder=work/f'arm-{index}';meter.start()
  try:backend=Backend(lr)
  finally:meter.stop()
  runner=Runner(backend,inputs,meter,arm['wording'],arm['replay_coefficient'],identity,folder)
  evaluator=PreservationEvaluator(backend,meter,folder/'evaluation')
  def evaluate(kind,step):
   if kind=='source':
    baseline=work/'shared-source.json'
    if not baseline.exists():
     result=PreservationEvaluator(backend,meter,work/'source-evaluation').checkpoint(kind,step);atomic(baseline,json.dumps(result).encode())
    atomic(folder/'source-reference.json',json.dumps({'shared_source_sha256':sha(baseline),'source_checkpoint_sha256':inputs.config['source_checkpoint_sha256']}).encode())
   else:evaluator.checkpoint(kind,step)
  if (folder/'checkpoint.pkl').exists():runner.restore()
  runner.run(evaluate)
  state['next_arm']=index+1;atomic(state_path,json.dumps(state).encode())
  del runner,evaluator,backend;gc.collect()
 atomic(work/'completed.json',json.dumps({'screen_complete':True,'no_promotion':True,'charges':meter.totals(),'seconds':meter.seconds()}).encode())

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--approval',required=True);args=parser.parse_args();run(args.approval)
