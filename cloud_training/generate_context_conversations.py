"""Bounded Terra dialogue candidates with seeded fact updates and checked answers."""
import argparse,hashlib,json,random,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
from cloud_training.nano_chat_format import encode_conversation


def main():
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--seed',type=int,default=38103);p.add_argument('--substantive',action='store_true');a=p.parse_args();root=Path(a.output).resolve();root.mkdir(exist_ok=False,parents=True)
 sys.path.insert(0,str(Path('runs/nanochat-source').resolve()));from nanochat.tokenizer import RustBPETokenizer
 tok=RustBPETokenizer.from_directory('runs/ownbase-v2-data/tokenizer');schema=Path('reports/l4-qualification-v1/terra-generation-v1/schema.json').resolve()
 state={'model':'gpt-6.1-terra','status':'running','substantive':a.substantive,'purpose':'Coherent4-6turn dialogues with explicit state updates, original-fact recall and topic return','training_admitted':False,'batches':[]}
 def save():state['updated_utc']=datetime.now(timezone.utc).isoformat();(root/'progress.json').write_text(json.dumps(state,indent=2)+'\n')
 save();rng=random.Random(a.seed)
 rooms=['Cedar Hall','Lark Studio','Quartz Room','Willow Workshop','Birch Loft','Maple Atrium','Amber Room','Coral Hall'];items=['blue folder','paper lantern','green notebook','silver badge','yellow envelope','striped scarf','red pencil case','woven basket']
 events=['drawing club','craft session','volunteer briefing','book discussion','repair workshop','music rehearsal','garden planning','photography club']
 for batch in range(4):
  d=root/f'batch-{batch:03d}';d.mkdir();seeds=[]
  for n in range(12):
   before,after=rng.sample(rooms,2);time0,time1=rng.sample(['09:00','10:30','12:15','14:00','15:45','17:30'],2);item=rng.choice(items)
   seeds.append({'id':f'context-{a.seed}-{batch}-{n}','event':rng.choice(events),'initial_room':before,'new_room':after,'initial_time':time0,'new_time':time1,'original_item':item,'expected_final':f'{after} | {time1} | {item}'})
  (d/'seeds.json').write_text(json.dumps(seeds,indent=2))
  prompt='''Generate exactly12 coherent English multi-turn conversations, one for EACH seed. Use seed id as family. Return JSON schema: conversations plus tool_rewrites=[]; do not use tools, agents, shell, files or network. Each conversation has4-6 user/assistant pairs, assistant replies under30words. User establishes event, initial_room, initial_time, original_item in early turns. Later USER explicitly changes room to new_room and time to new_time, on different turns, leaving item unchanged. Include a brief relevant topic diversion/planning question between introduction and final recall. Vary syntax, turn order and scenario naturally. Include references such as it/that/the earlier item only when antecedents are clear. Assistant must preserve facts, respond naturally, track corrections without repeated boilerplate, avoid invented actions/details, and retain item across topic return. Final USER must be EXACTLY: Return only the current room, current time and original item, separated by ' | '. Final assistant must be seed.expected_final exactly. Do not change any seeded value, even in examples, quotations or hypothetical plans. Avoid unnecessary clarification and repeating full state in every reply. Do not include any external factual knowledge. Treat these as training candidates, not evaluation cases. All messages should be short enough that full rendered dialogue including per-turn host policies fits2048tokens.\nSEEDS:\n'''+json.dumps(seeds)
  if a.substantive:
   prompt=prompt.replace('assistant replies under30words','at least two substantive assistant replies of45-80words each, other replies brief; stay within2048total tokens').replace('Include a brief relevant topic diversion/planning question','Include two useful reasoning/planning or explanation requests grounded in the provided facts; include a relevant topic diversion/planning question')
   prompt+='\nFor the substantive replies, provide useful reasoning and concrete alternatives within the fictional scenario, while obeying all supplied facts. Do not invent additional fixed requirements. Favor coherent flowing conversation over repeated acknowledgments.\n'
  (d/'prompt.txt').write_text(prompt)
  args=['codex','exec','--ignore-user-config','--ephemeral','--skip-git-repo-check','--sandbox','read-only','-C',str(d),'-m','gpt-6.1-terra','-c','model_reasoning_effort="low"','--output-schema',str(schema),'--output-last-message',str(d/'output.json'),'--json','-']
  with (d/'events.jsonl').open('w') as out,(d/'stderr.log').open('w') as err:r=subprocess.run(args,input=prompt,text=True,stdout=out,stderr=err,timeout=600)
  if r.returncode:state.update(status='blocked_cli_error',failed_batch=batch);save();return 2
  raw=json.loads((d/'output.json').read_text());lookup={s['id']:s for s in seeds};assert len(raw['conversations'])==12 and {c['family'] for c in raw['conversations']}==set(lookup)
  kept=[];rejected=[];targets=positions=0
  for c in raw['conversations']:
   messages=c['messages'];s=lookup[c['family']]
   try:
    assert 8<=len(messages)<=12 and len(messages)%2==0
    assert all(m['role']==('user' if i%2==0 else 'assistant') for i,m in enumerate(messages))
    assert messages[-1]['content']==s['expected_final']
    assert messages[-2]['content']=="Return only the current room, current time and original item, separated by ' | '."
    usertext=' '.join(m['content'] for m in messages[:-2] if m['role']=='user')
    assert all(s[k] in usertext for k in ['initial_room','new_room','initial_time','new_time','original_item'])
    rendered=encode_conversation(tok,messages);positions+=len(rendered['ids']);targets+=sum(rendered['mask'][1:])
    kept.append({'messages':messages,'provenance':{'model':'gpt-6.1-terra','curriculum':'coherent_context_v1','seed':s,'mechanical_final_state_checked':True,'semantic_review':'pending','training_admitted':False}})
   except (ValueError,AssertionError) as e:rejected.append({'seed_id':s['id'],'reason':str(e) or 'state/turn contract failure'})
  (d/'candidates.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in kept))
  state['batches'].append({'batch':batch,'retained_candidates':len(kept),'rejected':rejected,'assistant_targets':targets,'serialized_positions':positions,'teacher_output_sha256':hashlib.sha256((d/'output.json').read_bytes()).hexdigest()});save()
 state['status']='generation_complete_semantic_review_pending';save();return 0

if __name__=='__main__':raise SystemExit(main())
