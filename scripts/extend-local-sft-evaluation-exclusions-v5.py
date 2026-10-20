"""Preserve prior exclusions and protect every actual SFT reply/new heldout context."""
# Creator: Navneet Prabhakar
import json
from pathlib import Path
from slm.data.evaluation_exclusions import EvaluationExclusions,compile_inventory
from slm.data.prose_screen import word_key
from slm.data.stream_hash import sha
ROOT=Path('data/evaluation-exclusions-v4')
def main():
 if ROOT.exists():raise FileExistsError(ROOT)
 old=json.loads(Path('configs/future-intake-evaluation-exclusions-v3.json').read_text());prior=EvaluationExclusions(old['inventory'],old['inventory_sha256']);records=[];bindings={old['inventory']:old['inventory_sha256']};short=[]
 for r in prior.entries.values():
  for kind in r['kinds']:
   for origin in r['origins']:records.append(dict(kind=kind,text=r['text'],origin=origin))
 def add(kind,text,origin,history):
  key=word_key(text)
  if len(key)>=16 and len(key.split())>=4:records.append(dict(kind=kind,text=text,origin=origin))
  else:
   full='\n'.join(m['content'] for m in history)
   if len(word_key(full))<16 or len(word_key(full).split())<4:raise ValueError('Nontrivial actual full context required for short text')
   short.append(dict(kind=kind,text=text,origin=origin,complete_context=history));records.append(dict(kind=kind,text=full,origin=origin+'/complete-context'))
 for name in ['development-100','regression-100']:
  path=Path('data/local-conversation-run-v1')/name/'turns.jsonl';bindings[str(path)]=sha(path);history=[]
  for line in path.open():
   r=json.loads(line)
   if r['turn']==1:history=[]
   history.append(dict(role='user',content=r['user']));add('request',r['user'],f'{path}#{r["conversation"]}.{r["turn"]}/request',list(history));history.append(dict(role='assistant',content=r['response']['text']));add('generated_response',r['response']['text'],f'{path}#{r["conversation"]}.{r["turn"]}/student-reply',list(history))
 path=Path('data/conversation-acceptance-v1/source-references.jsonl');bindings[str(path)]=sha(path)
 for line in path.open():
  r=json.loads(line);history=[]
  for i,m in enumerate(r['messages']):
   history.append(m);add('request' if m['role']=='user' else 'generated_response',m['content'],f'{path}#{r["row_index"]}.{i}/source-evaluation-reference',list(history))
 value=compile_inventory(records,bindings);ROOT.mkdir();target=ROOT/'inventory.json';target.write_text(json.dumps(value,indent=2,ensure_ascii=False,sort_keys=True)+'\n');(ROOT/'short-context-protections.json').write_text(json.dumps(short,indent=2,ensure_ascii=False)+'\n');checked=EvaluationExclusions(target,sha(target))
 if not {r['key'] for r in prior.entries.values()}<={r['key'] for r in checked.entries.values()}:raise ValueError('Prior protections lost')
 config=dict(creator='Navneet Prabhakar',kind='future-intake-evaluation-exclusions-v4',inventory=str(target),inventory_sha256=sha(target),prior_config_sha256=sha('configs/future-intake-evaluation-exclusions-v3.json'),new_raw_bindings=bindings,distinct_texts=len(checked.entries),short_context_protections=str(ROOT/'short-context-protections.json'),short_context_protections_sha256=sha(ROOT/'short-context-protections.json'),training_approved=False,scope='All prior protections,600actualSFTreplies/requests and all200newsource-heldout evaluation reference conversations. Exact whole normalized sequences/complete contexts only, not semantic/paraphrase-family certification. Original inventories unchanged.')
 Path('configs/future-intake-evaluation-exclusions-v4.json').write_text(json.dumps(config,indent=2,sort_keys=True)+'\n');print('Protected normalized texts',len(checked.entries),'short contexts',len(short),'inventory bytes',target.stat().st_size)
if __name__=='__main__':main()
