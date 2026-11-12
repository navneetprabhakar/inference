import json,hashlib,random,collections,sys,re
from pathlib import Path
sys.path[:0]=[str(Path('.').resolve()),str(Path('runs/nanochat-source').resolve())]
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_chat_format import encode_conversation,VERSION
from cloud_training.nano_tool_lessons import Lesson,validate_lesson,number
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
tok=RustBPETokenizer.from_directory('runs/ownbase-v2-data/tokenizer');toksha=sha('runs/ownbase-v2-data/tokenizer/tokenizer.pkl')
report=Path('reports/l4-qualification-v1/literal-state-repair-v1');out=Path('runs/literal-state-repair-v1/admitted-v1');out.mkdir(parents=True,exist_ok=False)
source=Path('runs/balanced-constraint-repair-v1/admitted-v1');rows={s:[r for r in map(json.loads,(source/(s+'.jsonl')).read_text().splitlines()) if not r['family'].startswith('teacher_')] for s in ['train','validation']}
for s in rows:rows[s]+=[r for r in map(json.loads,(Path('runs/teacher-conversation-pilot-v1/admitted-v1')/(s+'.jsonl')).read_text().splitlines()) if r['family'].startswith('teacher_')]
vocab=sorted({tok.decode([i]).strip().lower() for i in range(32758) if re.fullmatch('[a-zA-Z]{3,12}',tok.decode([i]).strip())})
assert len(vocab)>3000
newrows={'train':[],'validation':[]}
for split in newrows:
 rng=random.Random(72191+(split=='validation')*100009)
 bank=[w for w in vocab if (int(hashlib.sha256(w.encode()).hexdigest()[:8],16)%10==0)==(split=='validation')]
 for f,n in [('wide_copy',6000 if split=='train' else 100),('update_state',4000 if split=='train' else 100),('ordered_subtract',2000 if split=='train' else 60)]:
  for i in range(n):
   m=[];turn=lambda u,a:m.extend([{'role':'user','content':u},{'role':'assistant','content':a}]);spec={}
   def code():return ''.join(rng.choice('ABCDEFGHJKLMNPQRSTUVWXYZ') for _ in range(4))+'-'+str(rng.randint(100,999))
   ref=code()
   if f=='wide_copy':
    words=rng.sample(bank,rng.choice([1,1,1,3,5,7]));text=' '.join(words)
    prompts=[f'Text-only request {ref}. Repeat exactly: {text}',f'No tools are needed for request {ref}. The complete answer must be "{text}".',f'Reference {ref}. Print only this text, unchanged: {text}',f'Request {ref}: copy the text between brackets and nothing else: [{text}]'] if split=='train' else [f'For {ref}, reproduce this text verbatim without additions: {text}']
    turn(rng.choice(prompts),text);spec={'text':text};assert text in m[0]['content']
   elif f=='update_state':
    old,new=code(),code();obj=rng.choice(['bag','camera','notebook','folder','box','keyring','coat'])
    turn(f'For record {ref}, my {obj} is in {old}. Acknowledge briefly.','Understood.')
    update=rng.choice([f'Use {new} as the current storage location. Confirm briefly.',f'The latest location should be {new}. Keep that as the current value.',f'Replace the previous location with {new}.',f'It is no longer in {old}; the location to remember now is {new}.']) if split=='train' else f'Please record {new} as its latest location instead of the earlier one.'
    turn(update,'Updated.')
    turn(rng.choice(['Which location is current? Give only the code.','Give the latest location code and nothing else.','Return just the new location.']) if split=='train' else 'What is the latest recorded location? Output its code alone.',new)
    turn('Give only the earlier location code.',old);spec={'old':old,'new':new}
   else:
    a,b=rng.randint(-3000,3000),rng.randint(-3000,3000)
    if (a,b) in [(205,1838),(73,19)]:continue
    lesson=Lesson(f,split,ref,{});lesson.messages=[]
    question=rng.choice([f'For case {ref}, calculate the signed difference in the supplied order: first {a}, second {b}.',f'Record {ref}: first operand {a}, second operand {b}. Use calculate for first minus second.',f'Case {ref}: subtract the second number from the first, where the first number is {a} and the second number is {b}. Use calculate.']) if split=='train' else f'Using calculate, subtract the second operand ({b}) from the first operand ({a}) for {ref}.'
    lesson.user(question+' Reply with the number alone.',permit=True,allowed=('calculate','convert'));record=lesson.call('calculate',{'op':'subtract','a':a,'b':b});assert record['data']['result']==a-b;lesson.text(number(a-b));m=lesson.messages;spec={'a':a,'b':b,'result':a-b}
   r={'messages':m,'family':f,'spec':spec,'provenance':{'kind':'root_authored_broad_copy_state_order_curriculum','training_admitted':True}}
   if f=='ordered_subtract':r['policies']=lesson.policies;r['grounding_checks']=[{'message_index':len(m)-1,'call_id':record['call_id'],'observed_value':a-b,'expected_text':number(a-b)}];validate_lesson(r)
   newrows[split].append(r)
suite=[];selected=collections.Counter()
for r in newrows['validation']:
 f=r['family']
 if selected[f]>=4:continue
 selected[f]+=1;turns=[]
 if f=='ordered_subtract':
  turns=[{'user':r['messages'][0]['content'],'policy':r['policies'][0],'expected_calls':[{'name':'calculate','arguments':{'op':'subtract','a':r['spec']['a'],'b':r['spec']['b']}}],'exact_answers':[number(r['spec']['result'])]}]
 else:
  for i in range(0,len(r['messages']),2):turns.append({'user':r['messages'][i]['content'],'expected_calls':[],'exact_answers':[r['messages'][i+1]['content']]})
 suite.append({'id':f+'-'+str(selected[f]),'turns':turns})
for s in rows:
 rows[s]+=newrows[s];unique={json.dumps({'messages':r['messages'],'policies':r.get('policies')},sort_keys=True):r for r in rows[s]};rows[s]=list(unique.values());random.Random(954).shuffle(rows[s])
userseq={s:{json.dumps([m['content'] for m in r['messages'] if m['role']=='user']) for r in rows[s]} for s in rows};assert not userseq['train']&userseq['validation']
trainprompts={m['content'] for r in rows['train'] for m in r['messages'] if m['role']=='user'}
for p in [Path('cloud_training/evaluation/conversation-tools-dev.json'),*Path('reports/l4-qualification-v1').glob('instruction-repair-v*/heldout-suite.json'),Path('reports/l4-qualification-v1/conversation-repair-v1/general-challenge.json')]:
 for s in json.loads(p.read_text())['sessions']:
  for t in s['turns']:assert t['user'] not in trainprompts
manifest={'schema':1,'training_admitted':True,'format_version':VERSION,'context_tokens':2048,'tokenizer_sha256':toksha};counts={};keys={}
for split,data in rows.items():
 keys[split]=set();family=collections.Counter();targetfamily=collections.Counter();targets=positions=calls=0
 for r in data:
  key=json.dumps(r['messages'],sort_keys=True);assert key not in keys[split];keys[split].add(key);family[r['family']]+=1
  e=encode_conversation(tok,r['messages'],policies=r.get('policies'));n=sum(e['mask'][1:]);targets+=n;targetfamily[r['family']]+=n;positions+=len(e['ids'])
  if r['family'] in ('calculate','convert','tool_correction','ordered_subtract'):calls+=validate_lesson(r)['actual_calls']
 path=out/(split+'.jsonl');path.write_text(''.join(json.dumps(r)+'\n' for r in data));manifest[split]={'file':path.name,'sha256':sha(path),'sessions':len(data),'assistant_targets':targets,'bytes':path.stat().st_size};counts[split]={'families':dict(family),'assistant_targets_by_family':dict(targetfamily),'assistant_targets':targets,'positions':positions,'tool_calls_replayed':calls}
assert not keys['train']&keys['validation']
receipt={'schema':1,'training_admitted':True,'format_version':VERSION,'tokenizer_sha256':toksha,'jsonl_sha256':[manifest[x]['sha256'] for x in rows],'review':'Prior admitted replay plus deterministic exact span copying from broad tokenizer word pool, fact-preserving latest/original state changes, independently arithmetic-checked ordered subtraction with actual broker replay. Copy vocabulary split by word hash for new examples; prior replay may contain words in other contexts. All old exact eval user prompts excluded, complete user sequences isolated. Teacherreview remains sampled.','counts':counts,'vocabulary_words':len(vocab),'builder_sha256':sha(__file__),'replay_source_sha256':sha(source/'train.jsonl'),'limits':['Exposed development, not general usability proof.','No inference postprocessing or answer substitution.']}
(out/'admission.json').write_text(json.dumps(receipt,indent=2)+'\n');manifest['admission']={'receipt':'admission.json','sha256':sha(out/'admission.json')};(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');(report/'data-review.json').write_text(json.dumps(receipt,indent=2)+'\n');(report/'heldout-suite.json').write_text(json.dumps({'purpose':'development_only_never_train','sessions':suite},indent=2)+'\n');print(json.dumps(counts['train'],indent=2))
