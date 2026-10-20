"""Carry all prior evaluation exclusions and add actual paired response/context evidence."""
# Creator: Navneet Prabhakar
import json
from pathlib import Path
from slm.data.evaluation_exclusions import EvaluationExclusions,compile_inventory
from slm.data.prose_screen import word_key
from slm.data.stream_hash import sha
ROOT=Path('data/evaluation-exclusions-v3')

def main():
 if ROOT.exists():raise FileExistsError('Preserve prior exclusion build')
 old=json.loads(Path('configs/future-intake-evaluation-exclusions-v1.json').read_text());prior=EvaluationExclusions(old['inventory'],old['inventory_sha256']);records=[];bindings={old['inventory']:old['inventory_sha256']};short=[]
 for r in prior.entries.values():
  for kind in r['kinds']:
   for origin in r['origins']:records.append(dict(kind=kind,text=r['text'],origin=origin))
 for model in ('foundation','corrected'):
  path=Path('data/balanced-versus-foundation-assessment-v1')/model/'turns.jsonl';bindings[str(path)]=sha(path)
  with path.open() as f:
   for row in map(json.loads,f):
    for kind,text in [('request',row['user']),('generated_response',row['response']['text'])]:
     key=word_key(text);origin=f'{path}#{row["conversation"]}.{row["turn"]}/{kind}'
     if len(key)>=16 and len(key.split())>=4:records.append(dict(kind=kind,text=text,origin=origin))
     else:
      short.append(dict(kind=kind,text=text,origin=origin,user=row['user']))
      records.append(dict(kind=kind,text=row['user']+'\n'+text,origin=origin+'/full-user-context'))
 value=compile_inventory(records,bindings);ROOT.mkdir();target=ROOT/'inventory.json';target.write_text(json.dumps(value,indent=2,ensure_ascii=False,sort_keys=True)+'\n');(ROOT/'short-context-protections.json').write_text(json.dumps(short,indent=2,ensure_ascii=False)+'\n');check=EvaluationExclusions(target,sha(target))
 if not {r['key'] for r in prior.entries.values()}<={r['key'] for r in check.entries.values()}:raise ValueError('Prior protection lost')
 config=dict(creator='Navneet Prabhakar',kind='future-intake-evaluation-exclusions-v3',inventory=str(target),inventory_sha256=sha(target),prior_config_sha256=sha('configs/future-intake-evaluation-exclusions-v1.json'),new_paired_raw_bindings=bindings,distinct_texts=len(check.entries),short_context_protections=str(ROOT/'short-context-protections.json'),short_context_protections_sha256=sha(ROOT/'short-context-protections.json'),requirement='New conversation intake/release must use this exact inventory and original upstream holdouts. Short generic replies are protected with complete user context rather than globally banning common labels. Whole normalized texts only; near/paraphrase/family isolation remains separate.',training_approved=False)
 Path('configs/future-intake-evaluation-exclusions-v3.json').write_text(json.dumps(config,indent=2,sort_keys=True)+'\n');print('Protected normalized texts',len(check.entries),'short context records',len(short))
if __name__=='__main__':main()
