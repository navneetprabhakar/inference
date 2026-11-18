"""Build reviewed candidates with real tokenizer/prefix tests, not training admission."""
import collections,hashlib,importlib.util,json,sys
from pathlib import Path
ROOT=Path.cwd();R=ROOT/'reports/ganesh-english-sourcing-v1';OUT=ROOT/'runs/ganesh-english-sourcing-v1'
sys.path[:0]=[str(ROOT),str(ROOT/'runs/nanochat-source')]
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_chat_format import encode_conversation
spec=importlib.util.spec_from_file_location('authored',R/'authored_source.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
plan=json.loads((R/'authoring-plan.json').read_text());assert {x['group'] for x in m.ROWS}=={g for gs in plan['scenario_groups_assigned_before_authoring'].values() for g in gs}
def digest(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
tok=RustBPETokenizer.from_directory(str(ROOT/'runs/ownbase-v2-data/tokenizer'))
reviews=[json.loads(l) for l in (R/'semantic-review.jsonl').read_text().splitlines()]
raw=[json.loads(l) for l in (OUT/'source-candidates.jsonl').read_text().splitlines()];byid={r['id']:r for r in raw}
rows=[]
for review in reviews:
 if review['decision']!='shortlist':continue
 row=dict(byid[review['id']]);assert digest(row['messages'])==review['source_messages_sha256'];row['family']=review['family'];row['review_decision']='shortlist';rows.append(row)
authored_reviews={x['group']:x for x in json.loads((R/'authored-review.json').read_text())}
for a in m.ROWS:
 messages=[{'role':role,'content':text} for pair in a['turns'] for role,text in zip(('user','assistant'),pair)]
 assert authored_reviews[a['group']]['messages_sha256']==digest(messages)
 assert authored_reviews[a['group']]['decision']=='shortlist'
 rows.append({'id':digest(messages),'source':'original Codex authoring','provenance':'original_synthetic','group':a['group'],'family':a['family'],'partition':'train_candidate','upstream_split':None,'messages':messages,'review_decision':'author_review_complete','training_admitted':False})
counts=collections.Counter();results=[]
for i,row in enumerate(rows):
 turn_count=len(row['messages'])//2; encs=[]
 for enabled in (False,True):
  policy={'permit_calls':enabled,'allowed_names':['calculate','convert'] if enabled else []};policies=[policy]*turn_count
  enc=encode_conversation(tok,row['messages'],policies=policies,context=2048)
  for j in range(0,len(row['messages']),2):
   prefix=encode_conversation(tok,row['messages'][:j+1],policies=policies[:j//2+1],for_generation=True,context=2048,reply_budget=256)
   # Real training encoding must have the exact serving prompt prefix.
   assert enc['ids'][:len(prefix['ids'])]==prefix['ids'],row['id']
  encs.append({'tools_enabled':enabled,'tokens':len(enc['ids']),'assistant_targets':sum(enc['mask'])})
 row['encoding']=encs;row['assigned_policy']={'permit_calls':bool(i%2),'allowed_names':['calculate','convert'] if i%2 else []}
 row['reply_budget']=256
 counts[row['family']]+=1;results.append(row)
with (OUT/'reviewed-candidates.jsonl').open('w') as f:
 for row in results:f.write(json.dumps(row,ensure_ascii=False)+'\n')
report={'status':'candidate_encoding_pass_not_admission','source_shortlist':len(rows)-len(m.ROWS),'authored_second_pass_reviewed':len(m.ROWS),'candidate_sessions':len(rows),'assistant_turns':sum(len(x['messages'])//2 for x in rows),'target_positions_single_policy':sum(x['encoding'][0]['assistant_targets'] for x in rows),'max_context':max(y['tokens'] for x in rows for y in x['encoding']),'both_no_call_modes_prefix_checks':'pass','positive_tool_training':False,'family_sessions':dict(counts),'training_admitted':False,'remaining':['Source/template grouping across all retained historical data','Source licenses/generator provenance admission','Curriculum breadth and positive-tool coverage','1000-session target not reached']}
(R/'candidate-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
