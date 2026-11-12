"""Bounded Codex CLI teacher candidates, never directly admitted for training."""
import argparse,json,random,subprocess,fcntl,datetime,sys,re
from pathlib import Path
sys.path[:0]=[str(Path('.').resolve()),str(Path('runs/nanochat-source').resolve())]
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_chat_format import encode_conversation
p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--batches',type=int,default=1);p.add_argument('--seed',type=int,default=94311);a=p.parse_args();assert 1<=a.batches<=24
lock=Path('runs/concise-teacher-generation.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=False);rng=random.Random(a.seed);tok=RustBPETokenizer.from_directory('runs/ownbase-v2-data/tokenizer');schema=Path('reports/l4-qualification-v1/terra-generation-v1/schema.json').resolve()
state={'status':'running','teacher':'gpt-6.1-terra','training_admitted':False,'batches':[]}
def save():state['updated_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();(out/'progress.json').write_text(json.dumps(state,indent=2)+'\n')
save()
topics=['paper folding','sketching','sorting postcards','organizing stationery','reading a short story','preparing a notice','packing a class bag','arranging a book shelf','writing a short poem','sorting photographs','planning a craft session','reviewing class notes']
for batch in range(a.batches):
 d=out/f'batch-{batch:03d}';d.mkdir();seeds=[]
 for i in range(12):
  family=['edit','summary','compare','explain','cancel','preference'][(batch+i)%6];topic=rng.choice(topics);name=rng.choice(['Mira','Dev','Lena','Omar','Nina','Ravi','Tara','Isha']);old,new=rng.sample(['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'],2);room=rng.choice(['Cedar','Maple','Birch','Willow','Oak']);n=rng.choice([12,18,24,30,36]);checks=[{} for _ in range(4)]
  if family=='edit':
   users=[f'Write a two-sentence notice for {topic} on {old} in the {room} room. {name} is the organizer. Use only these facts.',f'It will be on {new} instead. Rewrite the full notice and keep the other details.', 'Make that notice one sentence long, keeping all current facts.', 'What day did I initially give? Reply with the day only.'];checks=[{'contains':[old,room,name]},{'contains':[new,room,name],'forbid':[old]},{'contains':[new,room,name]},{'exact':old}]
  elif family=='summary':
   users=[f'Here are fictional notes: {name} will lead a session about {topic}; the room is {room}; the day is {old}; there are {n} places. Summarize them in two short sentences.',f'Correction: there are only {n//2} places, and the day is {new}. Update the summary.', 'Give a compact bullet list of the current facts without adding anything.', 'How many places were available before the correction? Give the number only.'];checks=[{'contains':[name,room,old,str(n)]},{'contains':[new,str(n//2)],'forbid':[old]},{'contains':[name,room,new,str(n//2)]},{'exact':str(n)}]
  elif family=='compare':
   users=[f'For {topic}, option A is a quiet room with {n} seats; option B is a noisy room with {n+6} seats. Compare them briefly using only these facts.',f'We have {n-2} people and quiet matters most. Recommend one option and explain why.',f'Correction: we now have {n+3} people, and everyone needs a seat. Reconsider using the original room facts.', 'How many seats does option A have? Answer with only the number.'];checks=[{}, {'contains':['option A']},{'contains':['option B']},{'exact':str(n)}]
  elif family=='explain':
   users=[f'Give one simple practical suggestion for someone beginning {topic}. Keep it to two short sentences.', 'That is too abstract. Give a small concrete example of your suggestion.', 'Now explain the same example in simpler words for a beginner, without adding new steps.', 'What activity are we discussing? Answer with its name only.'];checks=[{}, {}, {}, {'exact':topic}]
  elif family=='cancel':
   other=rng.choice([t for t in topics if t!=topic]);users=[f'I have {n} minutes for {topic} and {other}. Give a short plan with time allocations that total {n} minutes.',f'The second activity is cancelled. Use the time only for {topic}. Revise the actual plan.',f'I have only {n//2} minutes now. Give a shorter practical plan for the remaining activity.', 'Which activity did I cancel? Return its name only.'];checks=[{'contains':[topic,other]},{'contains':[topic],'forbid':[other]},{'contains':[topic],'forbid':[other]},{'exact':other}]
  else:
   users=[f'I want to get better at {topic}. Suggest a brief way to practice on my own.', 'I prefer to work with another person. Adapt your suggestion for two people instead.', 'We cannot buy any materials. Revise the plan using only things we already have.', 'Did I ultimately prefer practicing alone or with another person? Reply only: with another person'];checks=[{}, {}, {'forbid':['buy new','purchase']},{'exact':'with another person'}]
  seeds.append({'id':f'diverse-{a.seed}-{batch}-{i}','family':family,'users':users,'checks':checks})
 (d/'seeds.json').write_text(json.dumps(seeds,indent=2))
 prompt='''Generate JSON matching schema. tool_rewrites must be empty. No tool calls, shell, browsing or file operations. Produce exactly12 conversations, one per seed; family must equal seed.id. Each has exactly8 messages, alternating user/assistant. Copy user strings verbatim in order. Assistant replies must be useful, concise, natural, at most60words each. Follow every correction and preserve unchanged facts. Actually rewrite/revise when asked: do not just acknowledge. Do not invent facts, people, dates, actions performed or unsupported quantities. For time plans allocations must add up to the stated budget. Prefer concrete advice to generic boilerplate. Explain differences between earlier and current facts only when requested. Obey final exact answer and all contains/forbid checks, plus all user constraints. Vary response wording. All scenarios are fictional or ordinary low-risk tasks, no external knowledge needed.\nSEEDS:\n'''+json.dumps(seeds)
 (d/'prompt.txt').write_text(prompt)
 try:
  args=['codex','exec','--ignore-user-config','--ephemeral','--skip-git-repo-check','--sandbox','read-only','-C',str(d),'-m','gpt-6.1-terra','-c','model_reasoning_effort="low"','--output-schema',str(schema),'--output-last-message',str(d/'output.json'),'--json','-']
  with (d/'events.jsonl').open('w') as log,(d/'stderr.log').open('w') as err:r=subprocess.run(args,input=prompt,text=True,stdout=log,stderr=err,timeout=600)
  if r.returncode:raise RuntimeError('CodexCLI error; no paidAPI fallback')
  raw=json.loads((d/'output.json').read_text());lookup={s['id']:s for s in seeds};assert len(raw['conversations'])==12 and {c['family'] for c in raw['conversations']}==set(lookup)
  kept=[];rejected=[];targets=0
  for c in raw['conversations']:
   s=lookup[c['family']];m=c['messages']
   try:
    assert len(m)==8 and all(x['role']==('user' if j%2==0 else 'assistant') for j,x in enumerate(m))
    for j,check in enumerate(s['checks']):
     assert m[j*2]['content']==s['users'][j];t=m[j*2+1]['content'];assert len(t.split())<=60
     if 'exact' in check:assert t==check['exact']
     assert all(v.casefold() in t.casefold() for v in check.get('contains',[]))
     assert all(v.casefold() not in t.casefold() for v in check.get('forbid',[]))
    e=encode_conversation(tok,m);assert len(e['ids'])<=2048;targets+=sum(e['mask'][1:]);kept.append({'messages':m,'family':s['family'],'provenance':{'teacher':'gpt-6.1-terra','seed':s,'training_admitted':False,'semantic_review':'pending'}})
   except (AssertionError,ValueError):rejected.append(s['id'])
  (d/'candidates.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in kept));state['batches'].append({'batch':batch,'candidates':len(kept),'assistant_targets':targets,'rejected':rejected});save()
  if len(kept)<9:raise RuntimeError('Mechanical rejection above25percent; review required')
 except Exception as e:state.update(status='blocked',error=str(e));save();raise
state['status']='complete_pending_semantic_review';save()
