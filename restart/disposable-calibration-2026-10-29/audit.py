import sys,json,hashlib
from pathlib import Path
P=Path(__file__).resolve().parent;sys.path.insert(0,str(P))
from calibrate import verify,LIMITS
from runner import Meter,read,atomic

def main():
 verify();result=read(P/'result.json');m=Meter(P/'private/calibration.sqlite',LIMITS,True);before=m.totals();cursor=m.cursor()
 try:m.reserve('forbidden-thirteenth-update',0,updates=1)
 except RuntimeError as e:assert str(e)=='CAP_updates'
 else:raise AssertionError('Update13 admitted')
 assert m.totals()==before and m.cursor()==cursor and before['updates']==12
 maxima={};steps=0
 for replay in [0.,.5]:
  for step in range(1,4):
   a=read(P/'private'/f'r{replay}-continuous'/f'step-{step}.json');b=read(P/'private'/f'r{replay}-resumed'/f'step-{step}.json');assert a==b
  for kind in ['continuous','resumed']:
   for step in range(1,4):
    r=read(P/'private'/f'r{replay}-{kind}'/f'step-{step}.json');steps+=1
    for k,v in r['optimizer_check']['max_abs_error'].items():maxima[k]=max(maxima.get(k,0),v)
 assert steps==12
 receipt={'status':'PASS','verified_optimizer_applications':steps,'per_step_loss_norm_and_reference_checks_exact_across_resume':True,'thirteenth_update_refused_without_charge':True,'max_absolute_numpy_reference_errors':maxima,'source_and_runner_manifests_unchanged':True,'charges':before,'active_seconds':result['seconds'],'retained_training_started':False,'study_budget_carry_forward':{'proposed_total_updates':4612,'consumed_here':12,'remaining_if_study_approved_unchanged':4600},'limitations':['One fixed engineering LR2e-5, not selected for acquisition','Three updates per trajectory; does not prove long-run stability or model quality','Both replay settings tested on first three diverse-curriculum batches only']}
 atomic(P/'audit.json',json.dumps(receipt,indent=2).encode());print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
