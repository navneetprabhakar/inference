import json,copy,hashlib
from pathlib import Path
from gates import readiness,conversation,next_stage,FAMILIES
P=Path(__file__).resolve().parent;ROOT=P.parents[1];spec=json.loads((P/'campaign.json').read_text());checks=0

def yes(x):
 global checks
 assert x;checks+=1
r=dict(measurement_valid=True,generation_correct=48,domain_correct=[12]*4,grounding_correct=96,empty_correct=72,shuffled_correct=72,grammar_correct=54)
yes(readiness(r))
for key,val in [('measurement_valid',False),('grounding_correct',95),('empty_correct',73),('shuffled_correct',73),('grammar_correct',53)]:yes(not readiness({**r,key:val}))
yes(not readiness({**r,'domain_correct':[10,12,13,13]}))
for final in [False,True]:
 n=240 if final else 120;t=3*n
 good=dict(conversations=n,turns=t,correct=int(.9*t),language=int(.95*t),relevant=int(.9*t),terminal=__import__('math').ceil(.98*t),complete=int(.8*n),families={f:dict(total=n//6,complete=int(.8*n//6)) for f in FAMILIES},unsupported=int(.05*t),contradictions=int(.02*t),measurement_valid=True,foundation_still_ready=True,native_ratio=1.25,foundation_decline=.05)
 yes(conversation(good,final))
 for k,v in [('correct',good['correct']-1),('language',good['language']-1),('relevant',good['relevant']-1),('terminal',good['terminal']-1),('unsupported',good['unsupported']+1),('contradictions',good['contradictions']+1),('native_ratio',1.25001),('foundation_decline',.05001),('measurement_valid',False),('foundation_still_ready',False)]:
  case={**good,k:v}
  try:answer=conversation(case,final)
  except ValueError:answer=False
  yes(not answer)
 bad=copy.deepcopy(good);f=next(iter(FAMILIES));bad['families'][f]['complete']-=1;bad['complete']-=1;yes(not conversation(bad,final))
yes(next_stage('readiness',False)=='foundation_recovery');yes(next_stage('readiness',False,True)=='STOP_FOUNDATION');yes(next_stage('foundation_recovery',False)=='STOP_FOUNDATION');yes(next_stage('conversation_screen',False)=='STOP_RECIPE');yes(next_stage('confirmation',False)=='STOP_UNCONFIRMED');yes(next_stage('final',False)=='STOP_FINAL');yes(next_stage('final',True)=='BOUNDED_PILOT_PASS')
for k in ['updates','seconds','positions']:yes(sum(s[k] for s in spec['stages'])==spec['new_caps'][k])
yes(spec['aggregate_caps']['updates']==spec['carry_forward']['charges']['updates']+3268);yes(spec['aggregate_caps']['positions']==spec['carry_forward']['charges']['positions']+100000000);yes(abs(spec['aggregate_caps']['seconds']-spec['carry_forward']['seconds']-17100)<1e-6)
yes(not spec['execution_authorized'] and bool(spec['launch_blockers']))
e=json.loads((P/'evidence.json').read_text())
for f,h in e['source_hashes'].items():yes(hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h)
yes(hashlib.sha256((ROOT/spec['carry_forward']['source']).read_bytes()).hexdigest()==spec['carry_forward']['sha256'])
result=dict(status='PASS',assertions=checks,scope='Decision boundary/count/stop/budget and evidence-integrity fixtures; not semantic measurement or launch readiness.',new_inference=0,new_optimizer_updates=0,new_teacher_calls=0,launch_ready=False)
(P/'checks.json').write_text(json.dumps(result,indent=2)+'\n');print(result)
