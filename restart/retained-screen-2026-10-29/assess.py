"""Endpoint-only assessment. Never trains, selects an intermediate checkpoint or edits scores."""
import json,math,random
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parent

def read(f):return json.loads(f.read_text())
def lines(f):return [json.loads(s) for s in f.read_text().splitlines()]
def rate(x,n='correct',d='total'):return x[n]/x[d] if x[d] else None

def main():
 run=read(P/'result.json');assert run['status']=='COMPLETED'
 baseline=read(P/'source-baseline.json');source_nll=baseline['native_narrative']['nll'];arms=[];raw={}
 for a in run['arms']:
  i=a['arm'];folder=P/'private'/f'arm-{i}'/'evaluation';summary=read(folder/'1000-summary.json');m=summary['matrix'];c=summary['counterfactual'];D=m['cells']['D'];task={k.split(':')[1]:rate(v) for k,v in m['cell_families'].items() if k.startswith('D:')};state=m['D_state'];pair={k:rate(v,'both_correct') for k,v in c['counterfactual_pairs'].items()}
  checks={'D_overall':rate(D)>=.90,'D_each_task':all(v>=.80 for v in task.values()),'D_complete_state':rate(state,'complete')>=.80,'counterfactual_groups':all(v>=.80 for v in pair.values())};nll=summary['native_narrative']['nll']
  raw[i]=lines(folder/'1000-matrix.jsonl')
  arms.append({**a,'D':D,'D_accuracy':rate(D),'D_task_accuracy':task,'D_state':state,'counterfactual_pair_accuracy':pair,'acquisition_gates':checks,'acquisition_qualified':all(checks.values()),'native_nll':nll,'native_nll_delta':nll-source_nll,'native_nll_percent_change':100*(nll/source_nll-1),'behavior':summary['preservation'],'behavior_preservation':'INCONCLUSIVE_SOURCE_FLOOR','matrix_review_required':m['review_required'],'cells':m['cells'],'no_natural_acceptance_claim':True})
 comparisons=[]
 for replay,ca,di in [(0.5,0,1),(0.,2,3)]:
  left={(r['id'],r['turn']):r for r in raw[ca] if r['cell']=='D'};right={(r['id'],r['turn']):r for r in raw[di] if r['cell']=='D'};assert left.keys()==right.keys()
  gains=sum(not left[k]['complete'] and right[k]['complete'] for k in left);losses=sum(left[k]['complete'] and not right[k]['complete'] for k in left)
  families={}
  for key,l in left.items():families.setdefault(l['family'],{}).setdefault(l['id'],[]).append((int(l['complete']),int(right[key]['complete'])))
  rng=random.Random(291029);samples=[]
  for _ in range(2000):
   x=y=n=0
   for family,clusters in families.items():
    values=list(clusters.values())
    for group in rng.choices(values,k=len(values)):
     for a,b in group:x+=a;y+=b;n+=1
   samples.append((y-x)/n)
  comparisons.append({'replay':replay,'canonical_arm':ca,'diverse_arm':di,'D_turn_gains':gains,'D_turn_losses':losses,'D_turns':len(left),'D_accuracy_difference':(gains-losses)/len(left),'stratified_cluster_bootstrap_95_interval':np.percentile(samples,[2.5,97.5]).tolist(),'uncertainty_limit':'Resamples synthetic scenario clusters within task; not independent linguistic families, population inference or seed variance.'})
 for a in arms:
  a['dominated_by']=[b['arm'] for b in arms if b['arm']!=a['arm'] and b['D_accuracy']>=a['D_accuracy'] and b['native_nll']<=a['native_nll'] and (b['D_accuracy']>a['D_accuracy'] or b['native_nll']<a['native_nll'])]
 # Predeclared same-replay pair selection: eligibility first, then paired D gain, tie replay0.5.
 chosen=max(comparisons,key=lambda x:(int(arms[x['diverse_arm']]['acquisition_qualified']),x['D_accuracy_difference'],x['replay']))
 result={'source_native_nll':source_nll,'arms':arms,'paired_diversity_comparisons':comparisons,'suggested_confirmation_pair':[chosen['canonical_arm'],chosen['diverse_arm']],'confirmation_authorized':False,'single_seed_only':True,'automatic_promotion':False,'acquisition_qualified_arms':[a['arm'] for a in arms if a['acquisition_qualified']],'final_test_used':False,'natural_conversation_evaluated':False}
 (P/'assessment.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'qualified':result['acquisition_qualified_arms'],'pair':result['suggested_confirmation_pair'],'arms':[{k:a[k] for k in ['arm','D_accuracy','native_nll','acquisition_gates']} for a in arms]},indent=2))
if __name__=='__main__':main()
