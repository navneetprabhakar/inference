import json,random,hashlib,collections,sys
from pathlib import Path
sys.path[:0]=[str(Path('.').resolve()),str(Path('runs/nanochat-source').resolve())]
from cloud_training.build_conversation_repair import TASKS
from cloud_training.build_natural_repair import WORDS
from cloud_training.nano_chat_format import encode_conversation,VERSION
from cloud_training.nano_tool_lessons import validate_lesson
from nanochat.tokenizer import RustBPETokenizer
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
tok=RustBPETokenizer.from_directory('runs/ownbase-v2-data/tokenizer');toksha=sha('runs/ownbase-v2-data/tokenizer/tokenizer.pkl')
report=Path('reports/l4-qualification-v1/constraint-repair-v1');out=Path('runs/constraint-repair-v1/admitted-v1');out.mkdir(parents=True,exist_ok=False)
methods={
 'remember the steps':{'a written checklist':'Write the steps in order and mark each one after completing it.','speaking the steps aloud':'Say the next step aloud before doing it, then confirm it is finished.','arranging materials in order':'Place the materials in the order you will use them and move each one aside when finished.','a visual sequence':'Draw or photograph the stages in order and compare your progress with them.'},
 'organize supplies':{'labelled boxes':'Group similar supplies in boxes and label each box by its contents.','clear containers':'Group similar supplies in transparent containers so you can see their contents.','shallow trays':'Separate supplies into shallow trays and keep the items you use often near the front.','divided pouches':'Put related supplies in separate pouch sections and give each section a consistent purpose.'},
 'review a topic':{'flashcards':'Put a question on each card and check your answer before moving to the next one.','practice questions':'Answer a few questions without notes, then review the parts you missed.','explaining aloud':'Explain the topic in your own words and revisit any point you cannot explain clearly.','a concept map':'Draw the main ideas and connect related points with labelled lines.'}}
rows={'train':[],'validation':[]};groups={'train':set(),'validation':set()};seen=set();rng=random.Random(71827)
for family,n in [('cancel',2400),('alternative',1200),('literal_response',1800),('ownership',1200)]:
 for i in range(n):
  messages=[];spec={};turn=lambda u,a:messages.extend([{'role':'user','content':u},{'role':'assistant','content':a}])
  if family=='cancel':
   a,b=rng.sample(list(TASKS),2);total=rng.randint(11,99);which=rng.randrange(2);cancel=[a,b][which];keep=[b,a][which]
   group=json.dumps([family,a,b,total,which]);split='validation' if int(hashlib.sha256(group.encode()).hexdigest()[:8],16)%12==0 else 'train'
   turn(rng.choice([f'Today I need to {a} and {b}. I have {total} minutes.',f'My {total}-minute plan includes two tasks: {a}; {b}.']),f'Your two tasks are to {a} and {b}, within {total} minutes.')
   prompts=[f'I no longer need to {cancel}. What should I focus on now?',f'Cancel the task to {cancel}. Give brief advice for the remaining task.',f'Drop the {"first" if which==0 else "second"} task. Use the time for the other task.'] if split=='train' else [f'The activity to {cancel} has been called off. Adapt your advice to what is still needed.']
   turn(rng.choice(prompts),f'Focus on the remaining task: {keep}. {TASKS[keep][0]}. Use the {total} minutes for that task.')
   turn('Name only the activity that was cancelled.',cancel)
   turn('Name only the activity that remains.',keep)
   spec={'cancel':cancel,'keep':keep,'total':total};assert cancel not in messages[3]['content'] and keep in messages[3]['content']
  elif family=='alternative':
   goal=rng.choice(list(methods));a,b=rng.sample(list(methods[goal]),2);code=str(i);group=json.dumps([family,goal,a,b]);split='validation' if int(hashlib.sha256(group.encode()).hexdigest()[:8],16)%12==0 else 'train'
   turn(f'For activity {code}, suggest a way to {goal}.',f'One option is {a}. {methods[goal][a]}')
   u=rng.choice([f'I do not want {a}. Suggest a different approach in two sentences.',f'Avoid {a}. Give another practical option.',f'That approach does not suit me. Offer a different method.']) if split=='train' else f'Please replace that method; I want an option other than {a}.'
   turn(u,f'Try {b} instead. {methods[goal][b]}')
   turn('Which approach did I reject? Give only its name.',a)
   spec={'rejected':a,'replacement':b};assert a not in messages[3]['content']
  elif family=='literal_response':
   w=rng.choice(WORDS) if i%2 else ''.join(rng.choice('abcdefghjkmnpqrstuvwxyz') for _ in range(7));group=json.dumps([family,w]);split='validation' if int(hashlib.sha256(group.encode()).hexdigest()[:8],16)%12==0 else 'train'
   noise=rng.choice(['Do not call any tools.','This requires no action.','Treat this as text only.','No explanation is needed.'])
   instruction=rng.choice([f'Output exactly this text: {w}',f'Reply with only {w}',f'Your entire response must be: {w}',f'Write just the following: {w}']) if split=='train' else f'Return {w} as the complete reply, without additional text.'
   turn(f'Reference {i}. {noise} {instruction}',w);spec={'word':w};assert w in messages[0]['content']
  else:
   names=['Asha','Kiran','Dev','Tara','Ishan','Meera','Ravi','Nila','Omar','Zoya','Luca','Sofia'];a,b=rng.sample(names,2);x,y=rng.sample(['green notebook','red notebook','silver badge','copper badge','orange pouch','purple pouch','blue basket','yellow basket'],2)
   group=json.dumps([family,a,b,x,y]);split='validation' if int(hashlib.sha256(group.encode()).hexdigest()[:8],16)%12==0 else 'train'
   turn(f'{a} owns the {x}; {b} owns the {y}. Describe the ownership briefly.',f'{a} has the {x}, and {b} has the {y}.')
   turn('They swap these items. State the new owners.' if split=='train' else 'They exchange the two items. Describe who has each one now.',f'{a} now has the {y}, and {b} now has the {x}.')
   turn(f'Who has the {x} now? Answer with the name only.',b);turn(f'Who originally had the {x}? Answer with the name only.',a)
   spec={'original_owner':a,'current_owner':b,'item':x}
  key=json.dumps(messages,sort_keys=True)
  if key in seen:continue
  seen.add(key);groups[split].add(group);rows[split].append({'messages':messages,'family':family,'spec':spec,'provenance':{'kind':'root_authored_constraint_curriculum','training_admitted':True}})
assert not groups['train']&groups['validation']
suite=[];selection=collections.Counter()
for r in rows['validation']:
 f=r['family']
 if selection[f]>=3:continue
 selection[f]+=1;m=r['messages'];turns=[]
 for i in range(0,len(m),2):
  t={'user':m[i]['content'],'expected_calls':[]}
  if f=='literal_response' or (f in ('cancel','ownership') and i>=4) or (f=='alternative' and i==4):t['exact_answers']=[m[i+1]['content']]
  else:t['rubric']='Follow the current constraints; useful relevant prose. Reference: '+m[i+1]['content']
  turns.append(t)
 suite.append({'id':f+'-'+str(selection[f]),'turns':turns})
replay=Path('runs/teacher-conversation-pilot-v1/admitted-v1')
for split in rows:rows[split]+=[json.loads(x) for x in (replay/(split+'.jsonl')).read_text().splitlines()];random.Random(812).shuffle(rows[split])
trainprompts={m['content'] for r in rows['train'] for m in r['messages'] if m['role']=='user'}
for p in [Path('cloud_training/evaluation/conversation-tools-dev.json'),*Path('reports/l4-qualification-v1').glob('instruction-repair-v*/heldout-suite.json'),Path('reports/l4-qualification-v1/conversation-repair-v1/general-challenge.json')]:
 for s in json.loads(p.read_text())['sessions']:
  for t in s['turns']:assert t['user'] not in trainprompts
manifest={'schema':1,'training_admitted':True,'format_version':VERSION,'context_tokens':2048,'tokenizer_sha256':toksha};counts={};keys={}
for split,data in rows.items():
 keys[split]=set();family=collections.Counter();targets=positions=calls=0
 for r in data:
  key=json.dumps(r['messages'],sort_keys=True);assert key not in keys[split];keys[split].add(key);family[r['family']]+=1
  e=encode_conversation(tok,r['messages'],policies=r.get('policies'));targets+=sum(e['mask'][1:]);positions+=len(e['ids'])
  if r['family'] in ('calculate','convert','tool_correction'):calls+=validate_lesson(r)['actual_calls']
 path=out/(split+'.jsonl');path.write_text(''.join(json.dumps(r)+'\n' for r in data));manifest[split]={'file':path.name,'sha256':sha(path),'sessions':len(data),'assistant_targets':targets,'bytes':path.stat().st_size};counts[split]={'families':dict(family),'assistant_targets':targets,'positions':positions,'tool_calls_replayed':calls}
assert not keys['train']&keys['validation']
receipt={'schema':1,'training_admitted':True,'format_version':VERSION,'tokenizer_sha256':toksha,'jsonl_sha256':[manifest[x]['sha256'] for x in rows],'review':'Root authored and reviewed task advice and alternative methods; cancellation either position; exact factual targets checked at construction. Fact-combination split, exact prior eval exclusion, deterministic complete encoding, broker replay and immutable prior admission replay. Teacher subset retains prior sampled-review limitation.','counts':counts,'builder_sha256':sha(__file__),'replay_source_sha256':sha(replay/'train.jsonl'),'limits':['Development templates, not final blind acceptance.','Generated output must be manually reviewed; no broad usability inferred from loss.']}
(out/'admission.json').write_text(json.dumps(receipt,indent=2)+'\n');manifest['admission']={'receipt':'admission.json','sha256':sha(out/'admission.json')};(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');(report/'data-review.json').write_text(json.dumps(receipt,indent=2)+'\n');(report/'heldout-suite.json').write_text(json.dumps({'purpose':'development_only_never_train','sessions':suite},indent=2)+'\n');print(json.dumps(counts,indent=2))
