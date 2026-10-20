"""Preserve prior exclusions and protect every actual grounded/core reply and new protected context."""
# Creator: Navneet Prabhakar
import json
from pathlib import Path
from slm.data.evaluation_exclusions import EvaluationExclusions,compile_inventory
from slm.data.prose_screen import word_key
from slm.data.stream_hash import sha
ROOT=Path('data/evaluation-exclusions-v5')
def main():
 if ROOT.exists():raise FileExistsError(ROOT)
 old=json.loads(Path('configs/future-intake-evaluation-exclusions-v4.json').read_text());prior=EvaluationExclusions(old['inventory'],old['inventory_sha256']);records=[];bindings={old['inventory']:old['inventory_sha256']};short=[]
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
 paths=[Path('data/grounded-conversation-run-v1')/name/'turns.jsonl' for name in ('initial-grounded-100','grounded-100','regression-100')]+[Path('data/grounded-core-comparison-v1')/name/'turns.jsonl' for name in ('source','trained')]
 for path in paths:
  done=json.loads((path.parent/'completion.json').read_text())
  if not done['complete'] or done['actual_turns']!=300:raise ValueError('All1500actual capture rows required')
  bindings[str(path)]=sha(path);history=[]
  for line in path.open():
   r=json.loads(line)
   if r['turn']==1:history=[]
   history.append(dict(role='user',content=r['user']));add('request',r['user'],f'{path}#{r["conversation"]}.{r["turn"]}/request',list(history));history.append(dict(role='assistant',content=r['response']['text']));add('generated_response',r['response']['text'],f'{path}#{r["conversation"]}.{r["turn"]}/student-reply',list(history))
 for part in ('development','reserved'):
  path=Path('data/grounded-conversations-v1')/(part+'-references.jsonl');bindings[str(path)]=sha(path)
  for line in path.open():
   r=json.loads(line);history=[];add('request',r['context'],f'{path}#{r["id"]}/supplied-passage',[r['messages'][0]])
   for i,m in enumerate(r['messages']):
    history.append(m);add('request' if m['role']=='user' else 'generated_response',m['content'],f'{path}#{r["id"]}.{i}/original-human-evaluation-reference',list(history))
 protocol=Path('data/core-english-development-v1/protocol-v2.json');bindings[str(protocol)]=sha(protocol)
 for case in json.loads(protocol.read_text())['conversations']:
  for i,t in enumerate(case['turns']):add('request',t['user'],f'{protocol}#{case["id"]}.{i+1}/frozen-user-request',[dict(role='user',content=p['user']) for p in case['turns'][:i+1]])
 value=compile_inventory(records,bindings);ROOT.mkdir();target=ROOT/'inventory.json';target.write_text(json.dumps(value,indent=2,ensure_ascii=False,sort_keys=True)+'\n');(ROOT/'short-context-protections.json').write_text(json.dumps(short,indent=2,ensure_ascii=False)+'\n');checked=EvaluationExclusions(target,sha(target))
 if not {r['key'] for r in prior.entries.values()}<={r['key'] for r in checked.entries.values()}:raise ValueError('Prior protections lost')
 config=dict(creator='Navneet Prabhakar',kind='future-intake-evaluation-exclusions-v5',inventory=str(target),inventory_sha256=sha(target),prior_config_sha256=sha('configs/future-intake-evaluation-exclusions-v4.json'),new_raw_bindings=bindings,distinct_texts=len(checked.entries),short_context_protections=str(ROOT/'short-context-protections.json'),short_context_protections_sha256=sha(ROOT/'short-context-protections.json'),training_approved=False,scope='All prior protections,1500actualgrounded/core replies and requests,200original human QA evaluation dialogues/passages and authored core requests. Short answers/requests retain complete actual/static request contexts; no global exclusion of common one-word labels. Exact whole normalized sequences/complete contexts only, not semantic/paraphrase-family certification. Original inventories unchanged.')
 Path('configs/future-intake-evaluation-exclusions-v5.json').write_text(json.dumps(config,indent=2,sort_keys=True)+'\n');print('Protected normalized texts',len(checked.entries),'short contexts',len(short),'inventory bytes',target.stat().st_size)
if __name__=='__main__':main()
