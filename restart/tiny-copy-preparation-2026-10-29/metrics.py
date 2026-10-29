"""Strict copying diagnostics; no model execution."""
def score(expected,response,eos,bos=False,overflow=False):
 # Permit only outer whitespace; case, punctuation, time digits and full name must match.
 exact=response.strip()==expected
 return dict(exact=exact,terminal=bool(eos and not bos and not overflow),complete=bool(exact and eos and not bos and not overflow))
def summarize(records,outputs):
 assert len(outputs)==len(records) and len({r['id'] for r in outputs})==len(records)
 by={r['id']:r for r in outputs};groups={}
 for r in records:
  o=by[r['id']];grade=score(r['value'],o['response'],o['eos'],o.get('bos',False),o.get('overflow',False));key=(r['family'],r['split'],r['scope']);g=groups.setdefault(key,dict(correct=0,total=0,terminal=0,pairs={}))
  g['correct']+=grade['complete'];g['total']+=1;g['terminal']+=grade['terminal'];g['pairs'].setdefault(r['pair'],{})[r['side']]=(grade['complete'],o['response'].strip())
 result={}
 for key,g in groups.items():
  assert len(g['pairs'])==8 and all(set(v)=={'before','after'} for v in g['pairs'].values())
  paired=sum(v['before'][0] and v['after'][0] for v in g['pairs'].values());unchanged=sum(v['before'][1]==v['after'][1] for v in g['pairs'].values())
  result['|'.join(key)]={k:g[k] for k in ['correct','total','terminal']}|dict(both_correct=paired,pairs=8,unchanged_answer=unchanged,passes=(paired==8 if key[1]=='fit' else paired>=7) and g['terminal']==g['total'])
 return result

def select_lr(losses,baseline):
 # losses: list of {lr, family, loss} from endpoint teacher-forced fit evaluations only.
 import math
 assert len(losses)==4
 assert set(baseline)=={'name','time'} and all(math.isfinite(v) and v>0 for v in baseline.values())
 assert all(math.isfinite(r['loss']) and r['loss']>=0 for r in losses)
 options={}
 for lr in [.0001,.0005]:
  rows=[r for r in losses if r['lr']==lr];assert {r['family'] for r in rows}=={'name','time'}
  options[lr]=max(r['loss']/baseline[r['family']] for r in rows)
 return min(options,key=lambda lr:(options[lr],lr))
