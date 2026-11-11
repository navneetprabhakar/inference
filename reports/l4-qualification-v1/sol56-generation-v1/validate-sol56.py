import json,hashlib,copy,sys
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path.cwd()))
from cloud_training.nano_tool_lessons import validate_lesson
from cloud_training.nano_chat_format import encode_conversation
sys.path.insert(0,'runs/nanochat-source')
from nanochat.tokenizer import RustBPETokenizer
root=Path('runs/terra-conversation-v1');data=json.loads((root/'sol56-output.json').read_text());seeds={s['session_id']:s for s in json.loads((root/'tool-seeds.json').read_text())}
tok=RustBPETokenizer.from_directory('runs/ownbase-v2-data/tokenizer')
reject={'pronoun_clarification':'Unnecessary clarification of clear antecedent','missing_information':'Unnecessarily asks time when original requested draft can retain scheduled-time wording','preference_constraint':'Unclear whether quiet preference replaces active constraint'}
rows=[];calls=0
for c in data['conversations']:
 if c['family'] not in reject:rows.append({'messages':c['messages'],'provenance':{'teacher_model':'gpt-5.6-sol','family':c['family'],'transport':'codex_cli','training_admitted':False}})
assert len(data['tool_rewrites'])==len(seeds)
assert len(set(x['session_id'] for x in data['tool_rewrites']))==len(seeds)
for rewrite in data['tool_rewrites']:
 s=copy.deepcopy(seeds[rewrite['session_id']]);users=[m for m in s['messages'] if m['role']=='user'];assert len(users)==len(rewrite['user_messages'])
 for m,text in zip(users,rewrite['user_messages']):m['content']=text
 calls+=validate_lesson(s)['actual_calls']
 rows.append({'messages':s['messages'],'policies':s['policies'],'provenance':{'teacher_model':'gpt-5.6-sol','family':s['family'],'seed_id':rewrite['session_id'],'transport':'codex_cli','tool_observations':'unchanged_actual_broker_execution_replayed','training_admitted':False}})
positions=targets=0
for row in rows:
 r=encode_conversation(tok,row['messages'],policies=row.get('policies'));positions+=len(r['ids']);targets+=sum(r['mask'][1:])
(root/'sol56-candidates.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
receipt={'utc':datetime.now(timezone.utc).isoformat(),'model':'gpt-5.6-sol','status':'candidate_batch_verified_not_admitted','raw_general_sessions':16,'retained_general_sessions':13,'tool_sessions':8,'rejected_general':reject,'broker_calls_replayed':calls,'serialized_positions':positions,'assistant_targets':targets,'training_admitted':False,'teacher_output_sha256':hashlib.sha256((root/'sol56-output.json').read_bytes()).hexdigest(),'limitations':['Small hand-reviewed pilot; no held-out improvement demonstrated','Exclusion filtering against all training/development sources remains required before admission']}
(root/'sol56-validation.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
