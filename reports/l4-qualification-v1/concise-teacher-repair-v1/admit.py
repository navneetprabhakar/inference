import json,hashlib,random,collections,re,sys
from pathlib import Path
sys.path[:0]=[str(Path('.').resolve()),str(Path('runs/nanochat-source').resolve())]
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_chat_format import encode_conversation,VERSION
from cloud_training.nano_tool_lessons import validate_lesson
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
root=Path('runs/concise-teacher-repair-v1');report=Path('reports/l4-qualification-v1/concise-teacher-repair-v1');out=root/'admitted-v1'
assert json.loads((root/'production/progress.json').read_text())['status']=='complete_pending_semantic_review'
review=json.loads((report/'semantic-review.json').read_text());assert review['complete_sample_review'] is True
excluded=set(review['excluded_ids']);tok=RustBPETokenizer.from_directory('runs/ownbase-v2-data/tokenizer');toksha=sha('runs/ownbase-v2-data/tokenizer/tokenizer.pkl');candidates=[];seen=set();flags=[]
for p in sorted(root.glob('*/batch-*/candidates.jsonl')):
 for r in map(json.loads,p.read_text().splitlines()):
  s=r['provenance']['seed'];m=r['messages'];identifier=s['id']
  if identifier in excluded:continue
  key=json.dumps([x['content'] for x in m if x['role']=='user'])
  if key in seen:continue
  seen.add(key)
  try:
   for j,c in enumerate(s['checks']):
    text=m[2*j+1]['content'];assert m[2*j]['content']==s['users'][j] and len(text.split())<=45
    if 'exact' in c:assert text==c['exact']
    assert all(v.casefold() in text.casefold() for v in c.get('contains',[])) and all(v.casefold() not in text.casefold() for v in c.get('forbid',[]))
    if c.get('question'):assert '?' in text
    if c.get('sentences'):assert len(re.findall(r'[.!?](?:\s|$)',text))==c['sentences']
   if r['family']=='cancellation':
    for j in range(3):
     budget=int(re.search(r'(\d+) minutes',s['users'][0 if j<2 else 2])[1]);numbers=list(map(int,re.findall(r'\d+',m[2*j+1]['content'])))
     # Conservatively flag over-budget numeric plans; an explicit total may be repeated before allocations.
     if sum(numbers)>budget and budget in numbers:numbers.remove(budget)
     assert sum(numbers)<=budget,'time allocations require manual review'
   encode_conversation(tok,m)
  except (AssertionError,ValueError) as e:flags.append({'id':identifier,'reason':str(e) or 'constraint_check'});continue
  r['family']='concise_'+r['family'];r['provenance']['training_admitted']=True;r['provenance']['semantic_review']='root_sample_review_plus_all_row_mechanical_checks';r['_group']=json.dumps(s['checks'],sort_keys=True);candidates.append(r)
groups=collections.defaultdict(set)
for r in candidates:groups[r['family']].add(r['_group'])
devgroups=set()
for family,g in groups.items():
 ordered=sorted(g,key=lambda x:hashlib.sha256(x.encode()).hexdigest());devgroups.update(ordered[:max(1,len(ordered)//5)])
rows={'train':[],'validation':[]}
for r in candidates:split='validation' if r.pop('_group') in devgroups else 'train';rows[split].append(r)
suite=[];counts=collections.Counter()
for r in rows['validation']:
 family=r['family']
 if counts[family]>=2:continue
 counts[family]+=1;s=r['provenance']['seed'];turns=[]
 for i in range(4):
  t={'user':s['users'][i],'expected_calls':[],'checks':s['checks'][i]}
  if 'exact' in s['checks'][i]:t['exact_answers']=[s['checks'][i]['exact']]
  else:t['rubric']='Follow latest corrections, practical concise advice, no false actions. Reference: '+r['messages'][2*i+1]['content']
  turns.append(t)
 suite.append({'id':family+'-'+str(counts[family]),'turns':turns})
# Fixed small exact-member replay; unique data volume stays separate from explicit epochs.
source=Path('runs/literal-state-repair-v1/admitted-v1');limits={'calculate':100,'convert':100,'tool_correction':100,'state':75,'two_entities':75,'natural_context':75,'update_state':75,'wide_copy':100,'literal':100}
used=collections.Counter()
for r in map(json.loads,(source/'train.jsonl').read_text().splitlines()):
 if used[r['family']]<limits.get(r['family'],0):rows['train'].append(r);used[r['family']]+=1
# Common reply-only surface, broad texts; never an exact old evaluation user prompt.
evalprompts=set()
for p in [Path('cloud_training/evaluation/conversation-tools-dev.json'),*Path('reports/l4-qualification-v1').glob('instruction-repair-v*/heldout-suite.json'),Path('reports/l4-qualification-v1/conversation-repair-v1/general-challenge.json')]:
 for session in json.loads(p.read_text())['sessions']:
  evalprompts.update(t['user'] for t in session['turns'])
copyrows=[r for r in map(json.loads,(source/'train.jsonl').read_text().splitlines()) if r['family']=='wide_copy']
for i,r in enumerate(copyrows[:300]):
 answer=r['messages'][1]['content'];u=[f'Reply only: {answer}',f'Do not use tools. Reply only: {answer}',f'Text reference {i}. Reply only: {answer}'][i%3]
 if u in evalprompts:continue
 rows['train'].append({'messages':[{'role':'user','content':u},{'role':'assistant','content':answer}],'family':'literal_reply','provenance':{'kind':'root_verified_exact_copy_surface','training_admitted':True}})
for r in rows['train']:
 for m in r['messages']:
  if m['role']=='user':assert m['content'] not in evalprompts
sequences={s:{json.dumps([m['content'] for m in r['messages'] if m['role']=='user']) for r in rows[s]} for s in rows};assert not sequences['train']&sequences['validation']
out.mkdir(parents=True,exist_ok=False);manifest={'schema':1,'training_admitted':True,'format_version':VERSION,'context_tokens':2048,'tokenizer_sha256':toksha};totals={};keys={}
for split,data in rows.items():
 random.Random(1971).shuffle(data);keys[split]=set();family=collections.Counter();targets=positions=calls=0
 for r in data:
  key=json.dumps(r['messages'],sort_keys=True);assert key not in keys[split];keys[split].add(key);family[r['family']]+=1
  e=encode_conversation(tok,r['messages'],policies=r.get('policies'));targets+=sum(e['mask'][1:]);positions+=len(e['ids'])
  if r['family'] in ('calculate','convert','tool_correction'):calls+=validate_lesson(r)['actual_calls']
 path=out/(split+'.jsonl');path.write_text(''.join(json.dumps(r)+'\n' for r in data));manifest[split]={'file':path.name,'sha256':sha(path),'sessions':len(data),'assistant_targets':targets,'bytes':path.stat().st_size};totals[split]={'families':dict(family),'assistant_targets_per_pass':targets,'positions_per_pass':positions,'tool_calls_replayed':calls}
assert not keys['train']&keys['validation']
receipt={'schema':1,'training_admitted':True,'format_version':VERSION,'tokenizer_sha256':toksha,'jsonl_sha256':[manifest[x]['sha256'] for x in rows],'review':'Root full pilot and two production dialogues per batch; all-row state/format/length and conservative time-allocation screen. Candidate fact combinations grouped apart; exact user sequences isolated; exact old eval user prompts excluded. Prior tool/context replay exact-membership selected and replayed. Copy surface targets checked verbatim.','counts':totals,'semantic_review_sha256':sha(report/'semantic-review.json'),'flags_excluded':flags,'builder_sha256':sha(__file__),'limits':['Teacher review sampled, not individual certification of all rows.','Four planned epochs are repeated exposure, not four times as much unique data.','Manual prose and full18tool gates remain required.']}
(out/'admission.json').write_text(json.dumps(receipt,indent=2)+'\n');manifest['admission']={'receipt':'admission.json','sha256':sha(out/'admission.json')};(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');(report/'data-review.json').write_text(json.dumps(receipt,indent=2)+'\n');(report/'heldout-suite.json').write_text(json.dumps({'purpose':'development_only_never_train','sessions':suite},indent=2)+'\n');print(json.dumps(totals,indent=2))
