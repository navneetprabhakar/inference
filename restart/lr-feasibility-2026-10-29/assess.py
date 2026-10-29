import sys,json,hashlib
from pathlib import Path
P=Path(__file__).resolve().parent;sys.path.insert(0,str(P));from calibrate import verify,CalibrationMeter,CAPS,PRIOR
from runner import read,atomic,sha

def main():
 verify()
 for f,h in read(P/'assessment-freeze.json')['files'].items():assert sha(f)==h
 r=read(P/'result.json');t=read(P/'timing.json');c=read(P/'feasibility-counts.json')
 meter=CalibrationMeter(P/'private/study.sqlite',CAPS,True);before=meter.totals();cursor=meter.cursor()
 try:meter.reserve('blocked-601st-calibration-update',0,updates=1)
 except RuntimeError as e:assert str(e)=='CALIBRATION_600_UPDATE_CAP'
 else:raise AssertionError('Calibration cap bypassed')
 assert meter.totals()==before and meter.cursor()==cursor
 train_seconds=sum(2000*max(x['step_seconds']['p95'] for x in r['results'] if x['replay']==rep) for rep in [0.,.5])
 generation_seconds=c['generation_forwards_upper_bound']*max(s['seconds_per_forward'] for s in t['samples'])
 validation_seconds=13*64*max(t['narrative_batch_seconds']);remaining=train_seconds+generation_seconds+validation_seconds
 total=t['cumulative_seconds']+remaining*1.25
 positions=t['cumulative_charges']['positions']+c['training_main_positions']+c['generation_positions_upper_bound']+c['narrative_validation_positions']
 ratios={}
 for lr in [2e-5,1e-4,5e-4]:
  pair=[x for x in r['results'] if x['lr']==lr];vals=[x['endpoint_training_losses'][f]/v for x in pair for f,v in x['source_training_losses'].items()];ratios[str(lr)]=sum(vals)/len(vals)
 artifacts=sum(f.stat().st_size for f in (P/'private').rglob('*') if f.is_file())
 result={'status':'CALIBRATION_PASS_90_MINUTE_ENVELOPE_NOT_READY','selected_common_lr':r['selected_common_lr'],'mean_training_loss_ratio_by_lr':ratios,'new_updates':before['updates']-PRIOR['charges']['updates'],'cumulative_charges':before,'new_active_seconds':t['cumulative_seconds']-PRIOR['seconds'],'cumulative_seconds':t['cumulative_seconds'],'main_training_seconds_p95_projection':train_seconds,'generation_seconds_conservative_projection':generation_seconds,'validation_seconds_projection':validation_seconds,'total_seconds_with_25_percent_remaining_work_reserve':total,'total_minutes_with_reserve':total/60,'fits_90_minutes':total<=5400,'total_input_positions_upper_bound':positions,'fits_50M_positions':positions<=50000000,'remaining_retained_updates':4612-before['updates'],'projected_total_assistant_targets':before['assistant']+c['training_main_assistant_targets'],'projected_total_narrative_targets':before['narrative']+c['training_main_narrative_targets'],'current_private_artifact_bytes':artifacts,'601st_new_update_refused':True,'retained_training':False,'preservation_decision':'Acquisition-versus-native-retention research only; no behavioral preservation pass or promotion','proposed_revised_active_minutes':150,'revised_budget_authorized':False,'projection_limit':'Empirical conservative envelope, not runtime guarantee. Uses longest-prefix maximum observed latency for every generation step, including short prefixes; EOS can reduce actual work. Adds25% reserve. No natural diagnostic generation or extra seeds included.'}
 atomic(P/'assessment.json',json.dumps(result,indent=2).encode());print(json.dumps(result,indent=2))
if __name__=='__main__':main()
