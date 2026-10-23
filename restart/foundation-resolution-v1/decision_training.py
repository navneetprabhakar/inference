"""Prospective R1 selection and R2 endpoint decisions; all gates required."""
import re,sys,time
import numpy as np
from common import *
from scorer import binary,kappa
from decide import reviews,calibration

def paired(review,group,baseline):
 ids=sorted(review[group]);assert ids==sorted(review[baseline]) and len(ids)==40
 mean=lambda g:float(np.mean([sum(review[g][i]['scores']) for i in ids]))
 incoherent=lambda g:float(np.mean([review[g][i]['incoherent_sentence'] for i in ids]))
 return dict(mean=mean(group),baseline_mean=mean(baseline),mean_delta=mean(group)-mean(baseline),incoherent_fraction=incoherent(group),incoherent_delta=incoherent(group)-incoherent(baseline))

def main():
 phase=sys.argv[1];assert phase in ['R1','R2'];check(phase);freeze_check(phase)
 assert read(ROOT/f'{phase}-computation-pass.json')['status']=='PASS'
 cal=calibration(phase);rs=[reviews(phase,i) for i in [1,2]]
 if phase=='R1':
  baseline=read(ROOT/'baseline/summary.json');arms={}
  for arm in ['A','B']:
   endpoint=read(ROOT/arm/'summary.json');pair=[paired(r,arm,'baseline') for r in rs]
   nll_gain=baseline['validation_nll']-endpoint['validation_nll'];ground_delta=endpoint['grounded_intact_correct']-baseline['grounded_intact_correct'];grammar_delta=endpoint['grammar_unique_correct']-baseline['grammar_unique_correct']
   gates=dict(NLL_gain=nll_gain>=.01,grounding_nonregression=ground_delta>=-5,distinct_grammar_nonregression=grammar_delta>=-2,paired_mean_nonregression=all(r['mean_delta']>=-.25 for r in pair),incoherent_nonregression=all(r['incoherent_delta']<=.10 for r in pair),behavior_gain=ground_delta>=5 or all(r['mean_delta']>=.25 for r in pair),calibration=cal['pass_all'])
   arms[arm]=dict(eligible=all(gates.values()),gates=gates,NLL_gain=nll_gain,grounding_delta=ground_delta,distinct_grammar_delta=grammar_delta,paired_reviews=pair,summary=endpoint)
  eligible=[arm for arm in ['A','B'] if arms[arm]['eligible']];selected=None;cooldown='UNPROVEN'
  if len(eligible)==1:selected=eligible[0]
  elif len(eligible)==2:
   A=arms['A']['summary'];B=arms['B']['summary']
   if B['validation_nll']<=A['validation_nll']-.01 and B['grounded_intact_correct']>=A['grounded_intact_correct']-5 and B['grammar_unique_correct']>=A['grammar_unique_correct']-2:selected='B';cooldown='SELECTED_BY_PROSPECTIVE_RULE'
   else:selected='A'
  result=dict(status='PASS' if selected else 'FAIL_STOP',phase=phase,selected_arm=selected,cooldown_advantage=cooldown,arms=arms,calibration=cal,physical_training_targets=67108864,selected_retained_new_targets=33554432 if selected else 0,positions=Meter(phase).total(),epoch=time.time())
 else:
  selected=read(ROOT/'R1-result.json')['selected_arm'];old=read(ROOT/selected/'summary.json');base=read(ROOT/'baseline/summary.json');end=read(ROOT/'R2/summary.json')
  primary={r['id']:r for r in read(ROOT/'R2-primary.json')['reviews'] if r['group']=='current-original'}
  ids=sorted(primary);assert len(ids)==100 and all(ids==sorted(r['current-original']) for r in rs)
  pb=[binary(primary[i]) for i in ids];tb=[[binary(r['current-original'][i]) for i in ids] for r in rs]
  kappas=[kappa(pb,b) for b in tb];repeat=float(np.mean(np.array(tb[0])==np.array(tb[1])))
  stories=read(ROOT/'R2/original-stories.json')
  import importlib.util
  spec=importlib.util.spec_from_file_location('historical_degeneration',OLD/'finalize.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
  degenerate={k:v['degenerate'] for k,v in mod.behavior(stories).items()}
  conservative=sum(pb[j] and tb[0][j] and tb[1][j] and not degenerate[i] for j,i in enumerate(ids))
  probes=read(ROOT/'probes.json')['stories'];deltas={}
  for row in probes:
   i=row['id'];delta=float(np.mean([sum(r['current-new'][i]['scores'])-sum(r['selected'][i]['scores']) for r in rs]));deltas.setdefault(row['family'],[]).append(delta)
  families=np.array([np.mean(v) for v in deltas.values()]);assert len(families)==20
  rng=np.random.default_rng(20261023);means=families[rng.integers(0,20,size=(10000,20))].mean(axis=1);interval=[float(v) for v in np.quantile(means,[.025,.975])];gain=float(families.mean())
  ground_threshold=max(50,min(100,base['grounded_intact_correct']+10));grammar_threshold=max(36,old['grammar_unique_correct']);nll_gain=old['validation_nll']-end['validation_nll']
  gates=dict(NLL_gain=nll_gain>=.03,grammar=end['grammar_correct']>=75,distinct_grammar=end['grammar_unique_correct']>=grammar_threshold,grounding=end['grounded_intact_correct']>=ground_threshold,passage_controls=all(end['grounded_intact_correct']-end['grounded_'+v+'_correct']>=15 for v in ['empty','shuffled']),conservative_stories=conservative>=20,new_probe_gain=gain>=.5 and interval[0]>0,primary_teacher_kappa=all(v>=.6 for v in kappas),teacher_repeat=repeat>=.85,degeneration=sum(degenerate.values())<=5,calibration=cal['pass_all'])
  result=dict(status='PASS_DEVELOPMENT_STOP' if all(gates.values()) else 'FAIL_STOP',phase=phase,gates=gates,summary=end,NLL_gain=nll_gain,grounding_threshold=ground_threshold,distinct_grammar_threshold=grammar_threshold,conservative_original_stories=conservative,new_probe_mean_gain=gain,family_bootstrap95=interval,primary_teacher_kappas=kappas,teacher_binary_repeat_agreement=repeat,degeneration_count=sum(degenerate.values()),calibration=cal,positions=Meter(phase).total(),epoch=time.time(),conversation_training_authorized=False)
 save(ROOT/f'{phase}-result.json',result)
 if result['status']=='FAIL_STOP' or phase=='R2':save(ROOT/'STOP.json',dict(phase=phase,reason=result['status'],epoch=time.time(),training_authorized=False,conversation_training_authorized=False))
 print(__import__('json').dumps(result),flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:
  save(ROOT/'STOP.json',dict(phase=sys.argv[1],reason=type(e).__name__+': '+str(e),epoch=time.time(),training_authorized=False));raise
