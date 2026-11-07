"""Independent final activation metadata audit; no trainer/model/GPU imports."""
import hashlib,json,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[2];HERE=pathlib.Path(__file__).resolve().parent
def read(p):return json.loads(pathlib.Path(p).read_text())
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def require(ok,why):
 if not ok:raise ValueError(why)
def main():
 allocation=read(ROOT/'reports/grounded-sft-preflight-v1/allocation.json');allocation_proof=read(HERE/'allocation-independent-review.json');require(allocation_proof['state']=='PASS_independent_allocation_metadata' and allocation_proof['allocation_sha256']==sha(ROOT/'reports/grounded-sft-preflight-v1/allocation.json'),'independent allocation identity')
 spec=read(HERE/'activation.json');old=read(ROOT/'reports/own-base-sft-diagnostic-v1/activation.json');prepath=ROOT/'reports/grounded-sft-preflight-v1/activation-v1.json';pre=read(prepath)
 allowed={'run','datasets','hardware_preflight','code_sha256','checkpoint_updates','validation_updates','scheduler','work_limits','stop_paths'}
 require(set(spec)==set(old),'activation schema unchanged')
 require(all(spec[k]==old[k] for k in spec if k not in allowed),'unchanged parent/runtime/batching/time/guard settings')
 require(spec['run']==str(ROOT/'runs/own-base-grounded-sft-diagnostic-01'),'bound new run')
 require(spec['datasets']==allocation['datasets'] and spec['work_limits']==allocation['work_limits'] and spec['scheduler']==allocation['scheduler_proposal'],'allocation exact')
 require(spec['checkpoint_updates']==100 and spec['validation_updates']==2000 and spec['stop_paths']==pre['stop_paths'],'cadence/stops')
 for key in ('microbatch','evaluation_microbatch','accumulation','seed','mixing','schedule_rows_limit'):require(spec[key]==allocation['configuration'][key],'schedule config '+key)
 require(spec['code_sha256']==old['code_sha256']==pre['runtime_sha256'],'unchanged frozen runtime')
 for name,digest in spec['code_sha256'].items():require(sha(ROOT/name)==digest,'runtime pin '+name)
 for source in spec['datasets']:
  for key in ('receipt','admission','verification'):require(sha(source[key]['path'])==source[key]['sha256'],'source proof pin')
  d=pathlib.Path(source['receipt']['path']).parent;receipt=read(source['receipt']['path']);admission=read(source['admission']['path']);verification=read(source['verification']['path'])
  require(admission['training_admitted'] is True and not admission['quality_certified'] and not admission['launch_authorized'],'bounded diagnostic source admission')
  require(admission['verification_sha256']==source['verification']['sha256'] and verification['state']=='PASS' and verification['failures']==[],'admission independent proof')
  require(admission['dataset_sha256']==verification['dataset_sha256']==source['receipt']['sha256'],'dataset identity')
  for name,meta in receipt['outputs'].items():require((d/name).stat().st_size==meta['bytes'] and sha(d/name)==meta['sha256'],'stream unchanged')
  if source['name']=='four_call_extension':
   q=read(d/'four-call-qualification.json');require(q['state']=='PASS' and q['dataset_sha256']==source['receipt']['sha256'] and q['session_calls']==4 and q['final_turn']==2 and q['final_prefixes']=={'train':498,'exposed-development':54},'full four-call qualification')
 hp=pathlib.Path(spec['hardware_preflight']['path']);require(hp==pathlib.Path(pre['run'])/'hardware-receipt.json' and sha(hp)==spec['hardware_preflight']['sha256'],'new hardware proof pin');hardware=read(hp);directory=hp.parent
 require(hardware['state']=='PASS' and hardware['disposable_weights_released'] and hardware['validation_exercised'],'completed hardware PASS')
 for field,name in [('watchdog_sha256','watchdog.json'),('candidate_sha256','hardware-candidate.json'),('ledger_sha256','preflight-ledger.json'),('selection_sha256','selection.json')]:require(hardware[field]==sha(directory/name),'hardware supporting hash')
 watch=read(directory/'watchdog.json');ledger=read(directory/'preflight-ledger.json');signature=ledger.pop('sha256');require(signature==hashlib.sha256(canonical(ledger)).hexdigest(),'preflight ledger signature')
 require(watch['spec_sha256']==sha(prepath) and watch['returncode']==0 and watch['within_deadline'] and not watch['timed_out'] and not watch['interrupted'],'complete watchdog')
 require(ledger['identity']['spec']==pre and ledger['identity']['spec_sha256']==sha(prepath) and ledger['completed_updates']==40 and ledger['completed_evaluation_rows']==48 and ledger['pending'] is None,'completed exact hardware work')
 require(hardware['runtime_sha256']==spec['code_sha256'] and hardware['preflight_code_sha256']==pre['preflight_code_sha256'],'hardware code identities')
 for name,digest in pre['preflight_code_sha256'].items():require(sha(ROOT/name)==digest,'preflight code pin')
 require(hardware['parent']==spec['parent']==pre['parent'] and hardware['datasets']=={s['name']:s['receipt']['sha256'] for s in spec['datasets']},'hardware exact parent/sources')
 require(hardware['configuration']=={k:spec[k] for k in ('context','microbatch','evaluation_microbatch','accumulation','bf16')}|{'evaluation_precision':'fp32'},'hardware exact batching/precision')
 result={'state':'PASS_independent_training_activation_metadata','activation_sha256':sha(HERE/'activation.json'),'review_code_sha256':sha(__file__),'allocation_proof_sha256':sha(HERE/'allocation-independent-review.json'),'hardware_receipt_sha256':sha(hp),'updates':3975,'evaluation_steps':[0,2000,3975],'one_pass_training_rows':31794,'full_development_rows':2938,'training_assistant_targets':820293,'global_work_limits':spec['work_limits'],'original_runtime_unchanged':True,'parent_is_same_selected_ownbase':True,'launch_performed':False,'limitations':['Existing runtime uses cumulative source/global attempt budgets; allowance is100-update replay plus1full-development evaluation, not a separate count of permitted interruptions.','Full-state parent tensor/optimizer verification occurs in the existing launch path; this review reads metadata and streams only.','Teacher-forced CE is not conversation or tool usability. Full unchanged behavioral evaluation is still required after export.']}
 out=HERE/'activation-independent-review.json';require(not out.exists(),'preserve final review');out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
