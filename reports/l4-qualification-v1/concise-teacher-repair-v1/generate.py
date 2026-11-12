"""Bounded concise Terra candidates; never admits data or writes cloud control."""
import json,random,hashlib,subprocess,sys,re,fcntl,argparse,datetime
from pathlib import Path
sys.path[:0]=[str(Path('.').resolve()),str(Path('runs/nanochat-source').resolve())]
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_chat_format import encode_conversation
p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--batches',type=int,default=1);p.add_argument('--seed',type=int,default=83211);a=p.parse_args();assert 1<=a.batches<=12
root=Path(a.output).resolve();root.mkdir(parents=True,exist_ok=False);lock=Path('runs/concise-teacher-generation.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
tok=RustBPETokenizer.from_directory('runs/ownbase-v2-data/tokenizer');rng=random.Random(a.seed);schema=Path('reports/l4-qualification-v1/terra-generation-v1/schema.json').resolve();state={'status':'running','teacher':'gpt-6.1-terra','training_admitted':False,'batches':[]}
def save():state['updated_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();(root/'progress.json').write_text(json.dumps(state,indent=2)+'\n')
save()
activities=['sketching circle','puzzle afternoon','origami session','poetry reading','gardening workshop','music practice','craft swap','photography walk','book discussion','painting class','paper folding session','storytelling circle']
tasks=['clear the dining table','sort the shoe rack','prepare for a phone call','organize the kitchen drawer','pack a swimming bag','water the balcony plants','arrange the reading shelf','sort the laundry','plan a grocery list','organize the art cupboard','prepare a lesson outline','label the storage baskets','review the class notes','clear the hallway','pack the school bag','sort the sewing supplies']
methods=[('remember a sequence','a written list','saying each step aloud'),('review a topic','flashcards','answering practice questions'),('organize small items','labelled boxes','transparent trays'),('plan a day','a calendar','a short priority list'),('learn a process','watching a video','a small practice example'),('remember an idea','taking notes','explaining it aloud')]
for batch in range(a.batches):
 d=root/f'batch-{batch:03d}';d.mkdir();seeds=[]
 for i in range(12):
  family=['invitation','cancellation','preference','clarification'][(i+batch)%4];identifier=f'concise-{a.seed}-{batch}-{i}';checks=[]
  if family=='invitation':
   activity=rng.choice(activities);day,newday=rng.sample(['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'],2);room,newroom=rng.sample([f'{c} Room' for c in ['Amber','Violet','Silver','Copper','Teal','Coral','Ivory','Indigo','Olive','Pearl','Saffron','Ruby']],2)
   users=[f'Write a friendly invitation to a {activity} on {day} in the {room}. Use exactly two short sentences and give only the invitation.',f'Change the day to {newday}. Keep everything else, and give only the revised two-sentence invitation.',f'The location is now the {newroom}. Update the invitation again without changing the current day.', 'What is the current day? Reply with its name only.']
   checks=[{'contains':[activity,day,room],'sentences':2},{'contains':[activity,newday,room],'forbid':[day],'sentences':2},{'contains':[activity,newday,newroom],'forbid':[day,room],'sentences':2},{'exact':newday}]
  elif family=='cancellation':
   x,y=rng.sample(tasks,2);minutes,newminutes=rng.sample([12,18,24,30,36,42,48,54],2)
   users=[f'I have {minutes} minutes to {x} and {y}. Suggest a brief plan for both activities.',f'I no longer need to {y}. Revise the plan to focus on the remaining activity.',f'Actually I have only {newminutes} minutes now. Adapt your advice for that shorter time.' if newminutes<minutes else f'I now have {newminutes} minutes. Adapt your advice to that time.', 'How many minutes did I originally have? Answer with only the number.']
   checks=[{'contains':[x,y]},{'contains':[x,str(minutes)],'forbid':[y]},{'contains':[x,str(newminutes)],'forbid':[y]},{'exact':str(minutes)}]
  elif family=='preference':
   goal,old,new=rng.choice(methods);users=[f'Explain briefly how {old} could help me {goal}.',f'I do not want to use {old}. Suggest a genuinely different method, briefly.', 'Give me one practical first step for your new suggestion, without returning to the rejected method.', 'Which method did I reject? Return only its name.']
   checks=[{'contains':[old]},{'contains':[new],'forbid':[old]},{'forbid':[old]},{'exact':old}]
  else:
   item=rng.choice(['colouring pencils','sewing threads','paint brushes','postcards','charging cables','craft ribbons','recipe cards','drawing pens','stickers','camera accessories','small notebooks','knitting needles']);place=rng.choice(['a shared room','a small cupboard','a busy work area','a narrow shelf'])
   users=[rng.choice(['Can you sort that out for me?','Could you put those somewhere else?','Can you handle the arrangement?']),f'I mean suggest where to keep my {item} in {place}, so I can find them. I will move them myself.','I cannot buy any new containers. Revise the suggestion using what I already have.', 'What items are we organizing? Answer with only the item name.']
   checks=[{'question':True},{'contains':[item]},{'forbid':['buy a','purchase a'],'contains':[]},{'exact':item}]
  if family=='invitation':
   users[0]=rng.choice([users[0],f'Invite people to a {activity} in the {room} on {day}. Write exactly two friendly sentences, with no extra explanation.',f'Please draft a warm two-sentence invitation: {activity}, {day}, {room}. Return the invitation only.'])
   users[1]=rng.choice([users[1],f'The day has changed to {newday}. Rewrite the invitation in two sentences while preserving the activity and room.',f'Use {newday} instead of the old day. Give only the updated two-sentence invitation.'])
  elif family=='cancellation':
   users[0]=rng.choice([users[0],f'Help me divide {minutes} minutes between two tasks: {x} and {y}. Keep your advice short.'])
   users[1]=rng.choice([users[1],f'The plan to {y} has been called off. Focus your advice on the other task.',f'Drop the activity to {y}. Use the available time for the task that remains.',f'Cancel the activity to {y}; please adapt the advice.'])
  elif family=='preference':
   users[0]=rng.choice([users[0],f'How could {old} help someone {goal}? Explain briefly.',f'Tell me, in a sentence or two, how {old} could help me {goal}.'])
   users[1]=rng.choice([f'I would prefer an alternative to {old}. Suggest a different method briefly.',f'Please avoid {old}. What other method could I try?',f'That approach does not suit me. Recommend something other than {old}.'])
   users[2]=rng.choice([users[2],'How could I begin with your alternative? Give one brief, practical step.'])
  seeds.append({'id':identifier,'family':family,'users':users,'checks':checks})
 (d/'seeds.json').write_text(json.dumps(seeds,indent=2))
 prompt='''Return only JSON matching the supplied schema; tool_rewrites must be empty. No tools, shell, agents, network or file operations. Produce exactly one conversation for each seed. Set conversation.family to seed.id. Each conversation has exactly8 messages, four alternating user/assistant pairs. Copy the four supplied user strings verbatim and in order. Write concise, useful natural assistant responses: generally15–40words, never more than45words per turn. Follow each user request and latest correction; preserve unchanged facts. Do not invent times, quantities, actions taken, reasons, participants or requirements. Give advice or requested drafts, not a claim that you performed an action. No boilerplate about unspecified information when it is already supplied. For cancellation, focus only on the remaining activity and its current time budget. If a method is rejected, recommend the seeded alternative and do not return to the rejected method. For ambiguous requests, ask a specific clarifying question; never pretend you can physically move things. For invitation turns, return the actual two-sentence invitation only, no preface, signature or placeholders. Exact final answers must equal checks.exact. Other checks list literal phrases to include or avoid; use grammatical sentences around them. Planning time allocations must not exceed the budget. Keep all intermediate replies coherent and satisfy all checks. Vary invitation openings, second sentences and advice wording across the batch; do not reuse one stock response for every seed.\nSEEDS:\n'''+json.dumps(seeds)
 (d/'prompt.txt').write_text(prompt)
 args=['codex','exec','--ignore-user-config','--ephemeral','--skip-git-repo-check','--sandbox','read-only','-C',str(d),'-m','gpt-6.1-terra','-c','model_reasoning_effort="low"','--output-schema',str(schema),'--output-last-message',str(d/'output.json'),'--json','-']
 try:
  with (d/'events.jsonl').open('w') as out,(d/'stderr.log').open('w') as err:r=subprocess.run(args,input=prompt,text=True,stdout=out,stderr=err,timeout=600)
  if r.returncode:raise RuntimeError('CLI failed; no retry or paid fallback')
  raw=json.loads((d/'output.json').read_text());lookup={s['id']:s for s in seeds};assert len(raw['conversations'])==12 and {c['family'] for c in raw['conversations']}==set(lookup)
  kept=[];reject=[];targets=0
  for c in raw['conversations']:
   s=lookup[c['family']];m=c['messages']
   try:
    assert len(m)==8 and all(x['role']==('user' if n%2==0 else 'assistant') for n,x in enumerate(m))
    for j,check in enumerate(s['checks']):
     assert m[j*2]['content']==s['users'][j];t=m[j*2+1]['content'];assert len(t.split())<=45
     if 'exact' in check:assert t==check['exact']
     assert all(x.casefold() in t.casefold() for x in check.get('contains',[]))
     assert all(x.casefold() not in t.casefold() for x in check.get('forbid',[]))
     if check.get('question'):assert '?' in t
     if check.get('sentences'):assert len(re.findall(r'[.!?](?:\s|$)',t))==check['sentences']
     assert not re.search(r"\bI(?:'ve| have| will|’ll|'ll) (?:sent|send|book|move|arrange|purchase)",t,re.I)
    e=encode_conversation(tok,m);targets+=sum(e['mask'][1:]);kept.append({'messages':m,'family':s['family'],'provenance':{'model':'gpt-6.1-terra','seed':s,'mechanical_check':True,'semantic_review':'pending','training_admitted':False}})
   except (AssertionError,ValueError) as error:reject.append({'id':s['id'],'reason':str(error) or 'constraint_or_format'})
  (d/'candidates.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in kept));state['batches'].append({'batch':batch,'candidates':len(kept),'assistant_targets':targets,'rejected':reject});save()
  if len(kept)<9:raise RuntimeError('More than25percent rejected; review before scaling')
 except Exception as e:state.update(status='blocked',error=str(e));save();sys.exit(2)
state['status']='complete_pending_semantic_review';save()
