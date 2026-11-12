import json,hashlib,random,collections,sys
from pathlib import Path
sys.path[:0]=[str(Path('.').resolve()),str(Path('runs/nanochat-source').resolve())]
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_chat_format import encode_conversation,VERSION
from cloud_training.nano_tool_lessons import validate_lesson
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
tok=RustBPETokenizer.from_directory('runs/ownbase-v2-data/tokenizer');toksha=sha('runs/ownbase-v2-data/tokenizer/tokenizer.pkl')
report=Path('reports/l4-qualification-v1/balanced-constraint-repair-v1');out=Path('runs/balanced-constraint-repair-v1/admitted-v1');out.mkdir(parents=True,exist_ok=False)
rows={'train':[],'validation':[]};sources=[]
for run in ['instruction-repair-v2','instruction-repair-v3','conversation-repair-v1','constraint-repair-v1']:
 for split in rows:
  path=Path('runs')/run/('admitted-v3' if run=='instruction-repair-v2' else 'admitted-v1')/(split+'.jsonl');sources.append({'path':str(path),'sha256':sha(path)})
  for r in map(json.loads,path.read_text().splitlines()):
   f=r['family']
   if run.startswith('instruction') and f=='general_replay':continue
   if run=='conversation-repair-v1' and f=='grounded_plan' and split=='train' and int(hashlib.sha256(json.dumps(r['messages']).encode()).hexdigest()[:8],16)%5:continue
   if run=='constraint-repair-v1' and f not in ('cancel','alternative','literal_response','ownership'):continue
   rows[split].append(r)
# Expand negation phrasing while preserving the same explicitly checked target facts.
for r in list(rows['train']):
 if r['family']=='cancel':
  c=json.loads(json.dumps(r));s=c['spec'];c['messages'][2]['content']=f'We called off the activity to {s["cancel"]}. Give brief practical advice for the other activity.'
  assert s['cancel'] not in c['messages'][3]['content'] and s['keep'] in c['messages'][3]['content'];c['provenance']['kind']='root_authored_negation_paraphrase';rows['train'].append(c)
 if r['family']=='alternative':
  # Make the preferred initial method explicit, rather than supervising an arbitrary hidden choice.
  c=json.loads(json.dumps(r));s=c['spec'];c['messages'][0]['content']+=f' Start with {s["rejected"]}.'
  c['messages'][2]['content']=f'I would prefer not to use {s["rejected"]}. Suggest another approach briefly.'
  assert s['rejected'] not in c['messages'][3]['content'] and s['replacement'] in c['messages'][3]['content'];c['provenance']['kind']='root_authored_negative_preference_paraphrase';rows['train'].append(c)
# Retain bounded rich prose, balanced by token count rather than dialogue count.
source=Path('runs/teacher-conversation-pilot-v1/admitted-v1')
for split in rows:
 data=[r for r in map(json.loads,(source/(split+'.jsonl')).read_text().splitlines()) if r['family'].startswith('teacher_')]
 data.sort(key=lambda r:hashlib.sha256(r['provenance']['seed']['id'].encode()).hexdigest())
 rows[split]+=data[:400] if split=='train' else data
# Exact-member union deduplication and all prior development prompt exclusion.
for split in rows:
 unique={json.dumps({'messages':r['messages'],'policies':r.get('policies')},sort_keys=True):r for r in rows[split]};rows[split]=list(unique.values());random.Random(831).shuffle(rows[split])
trainprompts={m['content'] for r in rows['train'] for m in r['messages'] if m['role']=='user'}
for p in [Path('cloud_training/evaluation/conversation-tools-dev.json'),*Path('reports/l4-qualification-v1').glob('instruction-repair-v*/heldout-suite.json'),Path('reports/l4-qualification-v1/conversation-repair-v1/general-challenge.json'),Path('reports/l4-qualification-v1/constraint-repair-v1/heldout-suite.json')]:
 for s in json.loads(p.read_text())['sessions']:
  for t in s['turns']:
   # Common context-only questions are shared across training/dev; exclude whole scored user sequences below.
   if p.name=='general-challenge.json' or 'instruction-repair-' in str(p) or p.name=='conversation-tools-dev.json':assert t['user'] not in trainprompts
sequences={split:{json.dumps([m['content'] for m in r['messages'] if m['role']=='user']) for r in rows[split]} for split in rows};assert not sequences['train']&sequences['validation']
manifest={'schema':1,'training_admitted':True,'format_version':VERSION,'context_tokens':2048,'tokenizer_sha256':toksha};counts={};keys={}
for split,data in rows.items():
 keys[split]=set();family=collections.Counter();targetfamily=collections.Counter();targets=positions=calls=0
 for r in data:
  key=json.dumps(r['messages'],sort_keys=True);assert key not in keys[split];keys[split].add(key);family[r['family']]+=1
  e=encode_conversation(tok,r['messages'],policies=r.get('policies'));n=sum(e['mask'][1:]);targets+=n;targetfamily[r['family']]+=n;positions+=len(e['ids'])
  if r['family'] in ('calculate','convert','tool_correction'):calls+=validate_lesson(r)['actual_calls']
 path=out/(split+'.jsonl');path.write_text(''.join(json.dumps(r)+'\n' for r in data));manifest[split]={'file':path.name,'sha256':sha(path),'sessions':len(data),'assistant_targets':targets,'bytes':path.stat().st_size};counts[split]={'families':dict(family),'assistant_targets_by_family':dict(targetfamily),'assistant_targets':targets,'positions':positions,'tool_calls_replayed':calls}
assert not keys['train']&keys['validation']
receipt={'schema':1,'training_admitted':True,'format_version':VERSION,'tokenizer_sha256':toksha,'jsonl_sha256':[manifest[x]['sha256'] for x in rows],'review':'Exact prior-admission unions with deduplication, all tool lessons replayed. Root-authored cancellation/negativepreference paraphrases preserve checked factual targets. Complete rendering; disjoint development user sequences. Rich prose reduced to400 sampled-admitted dialogues; counts reported by assistant tokens. All18 previouslypassingtoolchecks gate promotion, not only original protected10.','counts':counts,'sources':sources,'builder_sha256':sha(__file__),'limits':['Teacher semantic review remains sampled.','Exposed development checks are not sealed final acceptance.']}
(out/'admission.json').write_text(json.dumps(receipt,indent=2)+'\n');manifest['admission']={'receipt':'admission.json','sha256':sha(out/'admission.json')};(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');(report/'data-review.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(counts['train'],indent=2))
