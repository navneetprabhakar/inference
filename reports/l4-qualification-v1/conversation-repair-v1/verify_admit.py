import json,hashlib,collections,sys,shutil,math
from pathlib import Path
sys.path.insert(0,str(Path('.').resolve()));sys.path.insert(0,str(Path('runs/nanochat-source').resolve()))
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_chat_format import encode_conversation,VERSION
from cloud_training.nano_tool_lessons import validate_lesson
from cloud_training.build_conversation_repair import TASKS
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
root=Path('runs/conversation-repair-v1/candidates-reviewed');out=Path('runs/conversation-repair-v1/admitted-v1');out.mkdir(exist_ok=False)
toksha=sha('runs/ownbase-v2-data/tokenizer/tokenizer.pkl');tok=RustBPETokenizer.from_directory('runs/ownbase-v2-data/tokenizer')
source=Path('runs/instruction-repair-v3/admitted-v1/train.jsonl');source_keys={json.dumps({'messages':r['messages'],'policies':r.get('policies')},sort_keys=True) for r in map(json.loads,source.read_text().splitlines())}
manifest={'schema':1,'training_admitted':True,'format_version':VERSION,'context_tokens':2048,'tokenizer_sha256':toksha};counts={};seen={};suite=[]
for split in ['train','validation']:
 keys=set();users=set();family=collections.Counter();targets=positions=calls=0
 for line in (root/(split+'.jsonl')).read_text().splitlines():
  r=json.loads(line);m=r['messages'];s=r['spec'];f=r['family'];family[f]+=1
  k=json.dumps({'messages':m,'policies':r.get('policies')},sort_keys=True);assert k not in keys;keys.add(k)
  answers=[x['content'] for x in m if x['role']=='assistant' and 'content' in x];prompts=[x['content'] for x in m if x['role']=='user'];users.add(json.dumps(prompts))
  assert not any(x['role']=='system' for x in m)
  if f in ('convert','calculate','tool_correction'):assert k in source_keys;calls+=validate_lesson(r)['actual_calls']
  else:
   assert r.get('policies') is None and len(prompts)==len(answers)
   if f in ('acknowledgment','natural_context'):
    assert answers[:2]==s['words'] and all(a in u for a,u in zip(answers[:2],prompts[:2]))
    assert s['old'] in prompts[0] and s['new'] in prompts[1]
    if f=='natural_context':assert answers[-2:]==[s['new'],s['old']]
   else:
    assert f=='grounded_plan' and s['first']+s['second']==s['total']
    assert s['task_a'] in answers[0] and s['task_b'] in answers[0]
    assert s['task_a'] in answers[1] and s['task_b'] not in answers[1]
    assert str(s['total']) in answers[1] and answers[-1]==str(s['total'])
    assert TASKS[s['task_a']][0].lower() in answers[0] and TASKS[s['task_a']][0] in answers[1]
  encoded=encode_conversation(tok,m,policies=r.get('policies'));targets+=sum(encoded['mask'][1:]);positions+=len(encoded['ids'])
  if split=='validation' and family[f]<=4:
   turns=[]
   for index,(u,a) in enumerate(zip(prompts,answers)):
    spec={'user':u,'expected_calls':[]}
    if f=='grounded_plan' and index<2:spec['rubric']=f'Give useful concise advice grounded in the {s["total"]}-minute budget; '+(f'cover {s["task_a"]} and {s["task_b"]}.' if index==0 else f'focus on {s["task_a"]} after {s["task_b"]} is cancelled.')
    else:spec['exact_answers']=[a]
    turns.append(spec)
   suite.append({'id':f+'-'+str(family[f]),'turns':turns})
 seen[split]=(keys,users);counts[split]={'families':dict(family),'assistant_targets':targets,'positions':positions,'tool_calls_replayed':calls}
 shutil.copyfile(root/(split+'.jsonl'),out/(split+'.jsonl'))
 manifest[split]={'file':split+'.jsonl','sha256':sha(out/(split+'.jsonl')),'sessions':sum(family.values()),'assistant_targets':targets,'bytes':(out/(split+'.jsonl')).stat().st_size}
assert not seen['train'][0]&seen['validation'][0] and not seen['train'][1]&seen['validation'][1]
traintext=(out/'train.jsonl').read_text()
for p in [Path('cloud_training/evaluation/conversation-tools-dev.json'),*Path('reports/l4-qualification-v1').glob('instruction-repair-v*/heldout-suite.json')]:
 for session in json.loads(p.read_text())['sessions']:
  for turn in session['turns']:assert turn['user'] not in traintext
receipt={'schema':1,'training_admitted':True,'format_version':VERSION,'tokenizer_sha256':toksha,'jsonl_sha256':[manifest[x]['sha256'] for x in ['train','validation']],'review':'Root authored/reviewed practical task advice; complete mechanical fact, duration, cancellation, exact answer and broker checks; tool replay exact-member verified against prior admission. No general web/noisy shortchat replay.','builder_sha256':sha('cloud_training/build_conversation_repair.py'),'verifier_sha256':sha(__file__),'tool_replay_source_sha256':sha(source),'counts':counts,'limits':['Templates do not establish broad conversational coverage. Open-ended responses require transcript review; exact fact checks alone are insufficient.','Development planning combinations and user sequences excluded from training.']}
(out/'admission.json').write_text(json.dumps(receipt,indent=2)+'\n');manifest['admission']={'receipt':'admission.json','sha256':sha(out/'admission.json')};(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
p=Path('reports/l4-qualification-v1/conversation-repair-v1');(p/'data-review.json').write_text(json.dumps(receipt,indent=2)+'\n');(p/'heldout-suite.json').write_text(json.dumps({'purpose':'development_only_never_train','sessions':suite},indent=2)+'\n');print(json.dumps(counts,indent=2))
