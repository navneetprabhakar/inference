"""Fixed prospective calibration and phase decisions; no gate relaxation."""
import sys,time
import numpy as np
from common import *
from scorer import binary,kappa

def reviews(phase,index):
 stem=f'{phase}-teacher-{index}';assert read(ROOT/f'{stem}-receipt.json')['status']=='PASS'
 mapping=read(ROOT/f'{stem}-map.json');rows=read(ROOT/f'{stem}-review.json')['reviews'];groups={}
 for r in rows:
  ref=mapping[r['id']];groups.setdefault(ref['group'],{})[ref['id']]=r
 return groups

def calibration(phase):
 a,b=reviews(phase,1),reviews(phase,2);anchors=read(ROOT/'anchors-private.json');scores=[]
 for review in [a,b]:
  counts={str(positive):sum(binary(review['anchor'][r['id']])==positive for r in anchors if r['positive']==positive) for positive in [True,False]}
  scores.append(counts)
 agreement=kappa([binary(a['anchor'][r['id']]) for r in anchors],[binary(b['anchor'][r['id']]) for r in anchors])
 return dict(anchor_classification_counts=scores,anchor_inter_review_kappa=agreement,pass_all=all(v>=9 for c in scores for v in c.values()) and agreement>=.6)

def main():
 phase=sys.argv[1];check(phase);c=calibration(phase);a,b=reviews(phase,1),reviews(phase,2)
 if phase=='R0':
  assert read(ROOT/'R0-computation-pass.json')['status']=='PASS'
  ids=sorted(a['baseline']);assert len(ids)==40 and ids==sorted(b['baseline'])
  repeat=float(np.mean([binary(a['baseline'][i])==binary(b['baseline'][i]) for i in ids]))
  mad=float(np.mean([abs(sum(a['baseline'][i]['scores'])-sum(b['baseline'][i]['scores'])) for i in ids]))
  passed=c['pass_all'] and repeat>=.85 and mad<=1
  result=dict(status='PASS' if passed else 'INCONCLUSIVE_STOP',phase=phase,calibration=c,baseline_binary_repeat_agreement=repeat,baseline_total_score_MAD=mad,training_updates=0,positions=Meter(phase).total(),epoch=time.time())
  save(ROOT/'R0-result.json',result)
  if not passed:save(ROOT/'STOP.json',dict(phase=phase,reason='GRADING_CALIBRATION_INCONCLUSIVE',epoch=time.time(),training_authorized=False))
  print(__import__('json').dumps(result))
 else:raise NotImplementedError('Future phase decision source must be prepared before its own freeze')
if __name__=='__main__':main()
