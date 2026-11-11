"""Bounded local teacher generation; candidate output only, no training/GCP writes."""
import argparse,copy,hashlib,json,os,subprocess,sys,time
from pathlib import Path
from datetime import datetime,timezone
from cloud_training.nano_tool_lessons import build_lessons,validate_lesson
from cloud_training.nano_chat_format import encode_conversation


def main():
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--batches',type=int,default=4);p.add_argument('--seed-offset',type=int,default=8103);a=p.parse_args()
 if not 1<=a.batches<=4:raise ValueError('One invocation limited to4batches')
 root=Path(a.output).resolve();root.mkdir(parents=True,exist_ok=False)
 schema=Path('reports/l4-qualification-v1/terra-generation-v1/schema.json').resolve()
 sys.path.insert(0,str(Path('runs/nanochat-source').resolve()))
 from nanochat.tokenizer import RustBPETokenizer
 tok=RustBPETokenizer.from_directory('runs/ownbase-v2-data/tokenizer')
 state={'model':'gpt-5.6-sol','transport':'codex_cli','seed_offset':a.seed_offset,'status':'running','training_admitted':False,'batches':[]};seen=set()
 def save():state['updated_utc']=datetime.now(timezone.utc).isoformat();(root/'progress.json').write_text(json.dumps(state,indent=2)+'\n')
 save()
 for i in range(a.batches):
  d=root/f'batch-{i:03d}';d.mkdir();seeds=build_lessons('train',per_family=4,seed=a.seed_offset+i*113)
  (d/'seeds.json').write_text(json.dumps(seeds,ensure_ascii=False))
  prompt='''Return only the JSON matching the schema. Do not use tools, shell, agents, network, or files. Generate16 different self-contained English conversations with2-4 user/assistant pairs each, concise natural answers under60words. Focus on tracking changed facts/preferences across turns, corrections, grounded extraction, missing information that actually requires clarification, and revising practical plans. Supply all required facts in user turns. No external factual knowledge, code, current events, tool instructions, or unsupported claims of actions performed. Avoid needless clarification and ambiguous constraint changes. Use varied names and situations. Batch index: '''+str(i)+'''. Separately rewrite user messages of ALL32 supplied broker lessons. Preserve every number, unit, entity, operation, turn order, output requirement, permission, and missing-information condition. Return original session_id plus one replacement string per original user turn. Do not generate tool results or calls; real broker traces will be retained.\nSEEDS:\n'''+json.dumps([{'session_id':s['session_id'],'family':s['family'],'messages':s['messages']} for s in seeds],ensure_ascii=False)
  settings=['community garden, craft supplies, borrowed equipment, and event setup','repair desk, delivery instructions, storage labels, and shared calendars','school club, library loans, picnic packing, and room arrangements','volunteer shifts, recipe constraints supplied by the user, workshop materials, and sports equipment']
  prompt='Conversation scenario settings for this batch: '+settings[i%len(settings)]+'. Use varied fictional names. Do not reuse Maya aisle/window seat examples. Generation cohort '+str(a.seed_offset)+'.\n'+prompt
  (d/'prompt.txt').write_text(prompt)
  argv=['codex','exec','--ignore-user-config','--ephemeral','--skip-git-repo-check','--sandbox','read-only','-C',str(d),'-m','gpt-5.6-sol','-c','model_reasoning_effort="low"','--output-schema',str(schema),'--output-last-message',str(d/'output.json'),'--json','-']
  with (d/'events.jsonl').open('w') as out,(d/'stderr.log').open('w') as err:
   result=subprocess.run(argv,input=prompt,text=True,stdout=out,stderr=err,timeout=600)
  if result.returncode:state.update(status='blocked_cli_error',failed_batch=i);save();return 2
  raw=json.loads((d/'output.json').read_text());rows=[];rejected=[];calls=0;seedmap={s['session_id']:s for s in seeds}
  for c in raw['conversations']:
   try:
    messages=c['messages'];assert 4<=len(messages)<=8
    assert all(m['role']==('user' if n%2==0 else 'assistant') for n,m in enumerate(messages))
    assert len(messages)%2==0
    row={'messages':messages,'provenance':{'model':'gpt-5.6-sol','family':c['family'],'semantic_review':'pending','training_admitted':False}}
    encode_conversation(tok,messages);rows.append(row)
   except (ValueError,AssertionError) as e:rejected.append({'family':c.get('family'),'reason':str(e)})
  ids=[r['session_id'] for r in raw['tool_rewrites']]
  if len(ids)!=len(seeds) or set(ids)!=set(seedmap):state.update(status='blocked_seed_coverage',failed_batch=i);save();return 2
  for r in raw['tool_rewrites']:
   s=copy.deepcopy(seedmap[r['session_id']]);users=[m for m in s['messages'] if m['role']=='user']
   if len(users)!=len(r['user_messages']):raise ValueError('Teacher changed turn count')
   for m,text in zip(users,r['user_messages']):m['content']=text
   replay=validate_lesson(s);calls+=replay['actual_calls']
   encode_conversation(tok,s['messages'],policies=s['policies'])
   rows.append({'messages':s['messages'],'policies':s['policies'],'provenance':{'model':'gpt-5.6-sol','family':s['family'],'seed_id':r['session_id'],'broker_replayed':True,'prompt_semantic_review':'pending','training_admitted':False}})
  accepted=[];positions=targets=0
  for row in rows:
   h=hashlib.sha256(json.dumps(row['messages'],sort_keys=True).encode()).hexdigest()
   if h in seen:continue
   seen.add(h);rendered=encode_conversation(tok,row['messages'],policies=row.get('policies'));positions+=len(rendered['ids']);targets+=sum(rendered['mask'][1:]);accepted.append(row)
  (d/'candidates.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in accepted))
  state['batches'].append({'batch':i,'status':'structurally_verified_semantic_review_pending','sessions':len(accepted),'broker_calls_replayed':calls,'serialized_positions':positions,'assistant_targets':targets,'rejected':rejected,'teacher_output_sha256':hashlib.sha256((d/'output.json').read_bytes()).hexdigest()});save()
 state['status']='generation_complete_semantic_review_pending';save();return 0

if __name__=='__main__':raise SystemExit(main())
