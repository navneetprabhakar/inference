"""Prospective v2 reliability and source-selection decision; no threshold tuning."""
import sys,time,collections,re
import numpy as np
from common import *
from scorer import binary,kappa

def degenerate(text):
 text=text.replace('’',"'").lower();words=re.findall(r"[a-z]+(?:'[a-z]+)?|[0-9]+",text);grams=[tuple(words[i:i+4]) for i in range(max(0,len(words)-3))]
 frac=(len(grams)-len(set(grams)))/max(1,len(grams))
 sentences=[' '.join(re.findall(r"[a-z]+(?:'[a-z]+)?|[0-9]+",s)) for s in re.split(r'[.!?]+',text)]
 maximum=max(collections.Counter(s for s in sentences if s).values(),default=0)
 return dict(repeated_fourgram_fraction=frac,maximum_identical_sentence_count=maximum,degenerate=frac>.20 or maximum>=3)

def teacher_rows(phase,round_no):
 allrows={};anchors=[]
 for p in sorted((ROOT/phase/'teacher').glob(f'round{round_no}-packet*-receipt.json')):
  assert read(p)['status']=='PASS';stem=p.name.replace('-receipt.json','');mapping=read(p.parent/f'{stem}-map.json');reviews=read(p.parent/f'{stem}-review.json')['reviews']
  expected={a['id']:a['positive'] for a in read(ROOT/'anchors-private.json')};correct=[]
  for r in reviews:
   ref=mapping[r['id']]
   if ref['group']=='anchor':correct.append(binary(r)==expected[ref['id']])
   else:
    key=(ref['group'],ref['id']);assert key not in allrows;allrows[key]=r
  anchors.append(dict(packet=stem,correct=sum(correct),total=4,pass_all=len(correct)==4 and all(correct)))
 return allrows,anchors

def reliability(primary,round1,round2,groups,degeneration):
 ids=sorted(primary);assert ids==sorted(round1)==sorted(round2)
 labels=lambda rows:[binary(rows[i]) and not degeneration[i]['degenerate'] for i in ids]
 a,b,p=labels(round1),labels(round2),labels(primary)
 repeat=float(np.mean(np.array(a)==np.array(b)));mad=float(np.mean([abs(sum(round1[i]['scores'])-sum(round2[i]['scores'])) for i in ids]));shifts={}
 for g in groups:
  keys=[i for i in ids if i[0]==g];shifts[g]=abs(float(np.mean([sum(round1[i]['scores'])-sum(round2[i]['scores']) for i in keys])))
 pairs=[]
 for other,rows in [(a,round1),(b,round2)]:
  agree=float(np.mean(np.array(p)==np.array(other)));scoremad=float(np.mean([abs(sum(primary[i]['scores'])-sum(rows[i]['scores'])) for i in ids]))
  try:k=kappa(p,other);passed=k>=.6;fallback=False
  except RuntimeError:
   # Only the explicitly approved constant-label exception is allowed.
   constant=len(set(p))==1 or len(set(other))==1;assert constant
   k=None;passed=agree>=.95 and scoremad<=.5;fallback=True
  pairs.append(dict(kappa=k,constant_label_fallback=fallback,exact_binary_agreement=agree,score_MAD=scoremad,pass_all=passed))
 passed=repeat>=.90 and mad<=.75 and all(x<=.5 for x in shifts.values()) and all(x['pass_all'] for x in pairs)
 return dict(pass_all=passed,binary_repeat_agreement=repeat,total_score_MAD=mad,checkpoint_mean_shifts=shifts,primary_teacher_pairs=pairs)

def main():
 phase=sys.argv[1];assert phase=='R0';check(phase);freeze_check(phase);assert read(ROOT/phase/'computation.json')['status']=='PASS'
 groups=[c['id'] for c in read(ROOT/'plan.json')['source_candidates']]
 raw=read(ROOT/phase/'primary.json');assert sha(ROOT/phase/'primary.json')==read(ROOT/phase/'primary-seal.json')['sha256']
 primary={(r['group'],r['id']):r for r in raw['reviews']};a,anchors1=teacher_rows(phase,1);b,anchors2=teacher_rows(phase,2)
 assert len(primary)==len(a)==len(b)==60 and len(anchors1)==len(anchors2)==5
 degeneration={}
 for group in groups:
  for r in read(ROOT/phase/group/'stories.json'):degeneration[group,r['id']]=degenerate(r['response'])
 reliable=reliability(primary,a,b,groups,degeneration);anchors_pass=all(x['pass_all'] for x in anchors1+anchors2)
 outcomes=[]
 for c in read(ROOT/'plan.json')['source_candidates']:
  keys=[i for i in primary if i[0]==c['id']]
  count=sum(binary(primary[i]) and binary(a[i]) and binary(b[i]) and not degeneration[i]['degenerate'] for i in keys)
  summary=read(ROOT/phase/c['id']/'summary.json')
  outcomes.append(dict(id=c['id'],global_step=c['step'],conservative_coherent=count,total=20,fact_correct=summary['facts_intact']['correct'],native_NLL=summary['validation_nll'],primary_coherent=sum(binary(primary[i]) and not degeneration[i]['degenerate'] for i in keys),teacher_coherent=[sum(binary(r[i]) and not degeneration[i]['degenerate'] for i in keys) for r in [a,b]],teacher_mean_scores=[float(np.mean([sum(r[i]['scores']) for i in keys])) for r in [a,b]]))
 passed=reliable['pass_all'] and anchors_pass;selected=None
 if passed:
  best=max(x['conservative_coherent'] for x in outcomes);eligible=[x for x in outcomes if x['conservative_coherent']>=best-1];selected=sorted(eligible,key=lambda x:(-x['fact_correct'],x['global_step']))[0]['id']
 result=dict(status='PASS' if passed else 'INCONCLUSIVE_STOP',phase=phase,selected_source=selected,reliability=reliable,anchors=anchors1+anchors2,anchors_pass=anchors_pass,candidates=outcomes,positions=Meter(phase).total(),training_updates=0,epoch=time.time(),small_sample_uncertainty='20 cases/checkpoint; descriptive source choice, not proof of superiority',formal_English_pass=False)
 save(ROOT/phase/'result.json',result)
 if passed:save(ROOT/'selected-source.json',dict(source=next(c for c in read(ROOT/'plan.json')['source_candidates'] if c['id']==selected),selection_result_sha256=sha(ROOT/phase/'result.json'),frozen_before_broad_loss=True,epoch=time.time()))
 else:save(ROOT/'STOP.json',dict(phase=phase,status='INCONCLUSIVE_STOP',reason='EVALUATOR_RELIABILITY_GATE_FAILED',epoch=time.time(),training_updates=0,next_phase_authorized=False))
 print(__import__('json').dumps(result))
if __name__=='__main__':main()
