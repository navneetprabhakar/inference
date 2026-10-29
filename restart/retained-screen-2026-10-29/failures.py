"""Descriptive endpoint error audit; frozen primary scores are never changed."""
import json,re
from pathlib import Path
P=Path(__file__).resolve().parent

def main():
 result={}
 for i in range(4):
  folder=P/'private'/f'arm-{i}'/'evaluation';rows=[json.loads(s) for s in (folder/'1000-matrix.jsonl').read_text().splitlines()];D=[r for r in rows if r['cell']=='D'];fail=[r for r in D if not r['complete']]
  terminal=[r for r in fail if not r['eos'] or r['bos'] or r['overflow']]
  punctuation=[r for r in fail if r['eos'] and not r['bos'] and not r['overflow'] and re.findall(r'\w+',r['response'].casefold())==re.findall(r'\w+',r['expected'].casefold())]
  examples={}
  for f in sorted({r['family'] for r in D}):
   examples[f]=[{k:r[k] for k in ['id','turn','response','expected','eos','bos','overflow','review_required']} for r in fail if r['family']==f][:3]
  result[str(i)]={'D_failures':len(fail),'D_termination_failures':len(terminal),'punctuation_only_sensitivity_cases':len(punctuation),'D_review_required':sum(r['review_required'] for r in D),'examples':examples,'note':'Punctuation sensitivity is not adjudication and does not change primary scores. Only first3 failures per task shown; not a representative random sample.'}
 (P/'failure-audit.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
