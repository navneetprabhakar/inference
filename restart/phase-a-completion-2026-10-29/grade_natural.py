"""Aggregate separately reviewed natural outputs; never infer semantic quality from keywords.
Input rows require case_id, turn (1-based), supported, act, instruction booleans,
semantic_grade Accept/Borderline/Fail, eos, bos, overflow, and reviewer_reason.
This validates a review record, not the accuracy or independence of its reviewer.
"""
import json,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def aggregate(cases,reviews):
 expected={(c['id'],i+1) for c in cases for i in range(len(c['turns']))};seen={}
 for r in reviews:
  key=(r['case_id'],r['turn'])
  if key not in expected or key in seen:raise ValueError(f'Unknown/duplicate review: {key}')
  for field in ['supported','act','instruction','eos','bos','overflow']:
   if type(r.get(field)) is not bool:raise ValueError(f'Explicit boolean required: {field}')
  if r.get('semantic_grade') not in ['Accept','Borderline','Fail']:raise ValueError('Invalid grade')
  if not isinstance(r.get('reviewer_reason'),str) or not r['reviewer_reason'].strip():raise ValueError('Review reason required')
  seen[key]=r
 missing=expected-set(seen)
 if missing:raise ValueError(f'Missing {len(missing)} turn reviews; no partial success report')
 passed={k: r['semantic_grade']=='Accept' and all(r[f] for f in ['supported','act','instruction','eos']) and not(r['bos'] or r['overflow']) for k,r in seen.items()}
 return {'correct_turns':sum(passed.values()),'total_turns':len(expected),'complete_conversations':sum(all(passed[(c['id'],i+1)] for i in range(len(c['turns']))) for c in cases),'total_conversations':len(cases),'borderline_turns':sum(r['semantic_grade']=='Borderline' for r in reviews),'semantic_judgments_supplied_externally':True,'automatic_semantic_scoring':False}

def self_test():
 c=[{'id':'a','turns':[{},{}]}]
 good=lambda i:dict(case_id='a',turn=i,supported=True,act=True,instruction=True,eos=True,bos=False,overflow=False,semantic_grade='Accept',reviewer_reason='Fixture, not model evidence')
 assert aggregate(c,[good(1),good(2)])['complete_conversations']==1
 count=1
 for key,value in [('supported',False),('act',False),('instruction',False),('eos',False),('bos',True),('overflow',True),('semantic_grade','Borderline'),('semantic_grade','Fail')]:
  a,b=good(1),good(2);a[key]=value;result=aggregate(c,[a,b]);assert result['correct_turns']==1 and result['complete_conversations']==0;count+=1
 for reviews in [[good(1)],[good(1),good(1)],[dict(good(1),case_id='unknown'),good(2)],[dict(good(1),act='true'),good(2)],[dict(good(1),reviewer_reason=''),good(2)]]:
  try:aggregate(c,reviews)
  except ValueError:count+=1
  else:raise AssertionError('Malformed review accepted')
 return {'status':'PASS','fixtures':count,'scope':'aggregation and completeness only, not semantic reviewer validity'}
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--reviews');parser.add_argument('--self-test',action='store_true');args=parser.parse_args()
 if args.self_test:print(json.dumps(self_test()))
 elif args.reviews:print(json.dumps(aggregate(json.loads((ROOT/'natural-development.json').read_text()),json.loads(Path(args.reviews).read_text())),indent=2))
 else:parser.error('Provide --reviews or --self-test')
