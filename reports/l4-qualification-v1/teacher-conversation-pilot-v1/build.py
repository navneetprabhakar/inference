import json,hashlib,collections,random,sys
from pathlib import Path
sys.path[:0]=[str(Path('.').resolve()),str(Path('runs/nanochat-source').resolve())]
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_chat_format import encode_conversation,VERSION
from cloud_training.nano_tool_lessons import validate_lesson
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
review=Path('reports/l4-qualification-v1/teacher-pool-review-20261112')
flags={x['id'] for x in json.loads((review/'scan.json').read_text())['flags']}
flags.add('teacher-105230-0-0') # Direct wording request gets advice rather than rewritten handoff.
samples=[json.loads(x) for x in (review/'expanded-reviewed-sample.jsonl').read_text().splitlines()]
report=Path('reports/l4-qualification-v1/teacher-conversation-pilot-v1')
(report/'sample-review.json').write_text(json.dumps({'reviewed_ids':[r['provenance']['seed']['id'] for r in samples],'scope':'14 complete dialogues read by root; 13 useful, one excluded for failing implied rewrite request. Not whole-pool semantic review.','excluded_id':'teacher-105230-0-0','decision':'Bounded experimental admission of mechanically screened non-writing pool with group isolation; all sampled-rejected and stale-value flags excluded. Closed-value limitation offset by exact-member open-value/tool rehearsal, not claimed eliminated.'},indent=2))
tok=RustBPETokenizer.from_directory('runs/ownbase-v2-data/tokenizer');toksha=sha('runs/ownbase-v2-data/tokenizer/tokenizer.pkl')
rows={'train':[],'validation':[]};groups={'train':set(),'validation':set()};excluded=collections.Counter()
for p in sorted(Path('runs/teacher-student-execution-v1/production').glob('cohort-*/batch-*/candidates.jsonl')):
 for line in p.read_text().splitlines():
  r=json.loads(line);s=r['provenance']['seed'];identifier=s['id']
  if s['domain']=='writing' or identifier in flags:excluded['quality_screen']+=1;continue
  m=r['messages'];assert len(m)==12 and all(x['role']==('user' if i%2==0 else 'assistant') for i,x in enumerate(m))
  assert m[-1]['content']==s['expected_final']
  assert s['expected_final']==' | '.join([*s['updates'],s['initial'][2]])
  group=json.dumps([s['domain'],s['initial'],s['updates']],sort_keys=True)
  split='validation' if int(hashlib.sha256(group.encode()).hexdigest()[:8],16)%10==0 else 'train'
  try:encode_conversation(tok,m)
  except ValueError:excluded['encoding']+=1;continue
  r['family']='teacher_'+s['domain'];r['provenance']['training_admitted']=True;r['provenance']['semantic_review']='mechanical_screen_plus_root_sample_review_not_individual'
  rows[split].append(r);groups[split].add(group)
assert not groups['train']&groups['validation']
# Frozen, already-admitted rehearsal preserves open values, acknowledgments and executable tools.
replay=Path('runs/conversation-repair-v1/admitted-v1')
for split in rows:
 rows[split]+=[json.loads(x) for x in (replay/(split+'.jsonl')).read_text().splitlines()]
 random.Random(137).shuffle(rows[split])
# Exclude exact prior evaluation prompts except the replay's own validation set.
trainprompts={m['content'] for r in rows['train'] for m in r['messages'] if m['role']=='user'}
for p in [Path('cloud_training/evaluation/conversation-tools-dev.json'),*Path('reports/l4-qualification-v1').glob('instruction-repair-v*/heldout-suite.json'),Path('reports/l4-qualification-v1/conversation-repair-v1/general-challenge.json')]:
 for session in json.loads(p.read_text())['sessions']:
  for t in session['turns']:assert t['user'] not in trainprompts,(p,t['user'])
out=Path('runs/teacher-conversation-pilot-v1/admitted-v1');out.mkdir(parents=True,exist_ok=False)
manifest={'schema':1,'training_admitted':True,'format_version':VERSION,'context_tokens':2048,'tokenizer_sha256':toksha};counts={};keys={};suite=[]
for split,data in rows.items():
 family=collections.Counter();targets=positions=calls=0;keys[split]=set()
 for r in data:
  m=r['messages'];key=json.dumps(m,sort_keys=True);assert key not in keys[split];keys[split].add(key)
  family[r['family']]+=1;e=encode_conversation(tok,m,policies=r.get('policies'));targets+=sum(e['mask'][1:]);positions+=len(e['ids'])
  if r['family'] in ('calculate','convert','tool_correction'):calls+=validate_lesson(r)['actual_calls']
  if split=='validation' and r['family'].startswith('teacher_') and family[r['family']]==1:
   turns=[]
   for i in range(0,len(m),2):
    t={'user':m[i]['content'],'expected_calls':[]}
    if i==10:t['exact_answers']=[m[i+1]['content']]
    else:t['rubric']='Answer the actual request coherently, preserve latest corrections, no invented actions. Reference: '+m[i+1]['content']
    turns.append(t)
   suite.append({'id':r['family'],'turns':turns})
 path=out/(split+'.jsonl');path.write_text(''.join(json.dumps(r)+'\n' for r in data))
 manifest[split]={'file':path.name,'sha256':sha(path),'sessions':len(data),'assistant_targets':targets,'bytes':path.stat().st_size}
 counts[split]={'families':dict(family),'assistant_targets':targets,'positions':positions,'tool_calls_replayed':calls}
assert not keys['train']&keys['validation']
receipt={'schema':1,'training_admitted':True,'format_version':VERSION,'tokenizer_sha256':toksha,'jsonl_sha256':[manifest[x]['sha256'] for x in rows],'review':'Experimental non-writing teacher subset: every row mechanical format/final-state/length checks; 14 additional whole-dialogue root reviews, not individual review of entire pool. Excluded all stale flags and sampled rewrite failure. Entire underlying fact combinations grouped apart, exact prior eval prompts excluded. Prior admitted rehearsal exact copied and calls replayed.','counts':counts,'excluded':dict(excluded),'replay_source_sha256':sha(replay/'train.jsonl'),'builder_sha256':sha(__file__),'limits':['Only 3-4 teacher field values; not broad factual coverage.','First pilot admission does not imply semantic certification of every row.','Manual prose and protected-tool gates required before promotion.']}
(out/'admission.json').write_text(json.dumps(receipt,indent=2)+'\n');manifest['admission']={'receipt':'admission.json','sha256':sha(out/'admission.json')};(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
(report/'data-review.json').write_text(json.dumps(receipt,indent=2)+'\n');(report/'heldout-suite.json').write_text(json.dumps({'purpose':'development_only_never_train','sessions':suite},indent=2)+'\n');print(json.dumps(counts,indent=2))
