"""Materialize fully authored/reviewed pilot data; never touches frozen corpora.
This is pilot-only admission. No independent release suite is manufactured here.
"""
import sys,json,hashlib,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];P=Path(__file__).parent
sys.path[:0]=[str(ROOT),str(ROOT/'runs/nanochat-source')]
from source import TRAIN,DEV
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_chat_format import encode_conversation,VERSION
from cloud_training.nano_tool_lessons import Lesson,validate_lesson
from cloud_training.nano_sft import JsonlConversations
from cloud_training.nano_quality_gate import dataset_coverage
from cloud_training.nano_quality import validate_suite
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
rowsha=lambda r:hashlib.sha256(json.dumps(r,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def write(name,obj):
 path=P/name
 if path.exists():raise FileExistsError('Immutable output exists: '+str(path))
 path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def policy(on):return {'permit_calls':on,'allowed_names':['calculate','convert'] if on else []}
def main():
 if (P/'freeze.json').exists():raise ValueError('Already frozen; create a new version')
 tokenizer=RustBPETokenizer.from_directory(str(ROOT/'runs/ownbase-v2-data/tokenizer'))
 splits={};notes={}
 for split,source in [('train',TRAIN),('development',DEV)]:
  rows=[]
  for i,(group,family,pairs,note) in enumerate(source):
   ident='english_v1_'+group
   row={'id':ident,'family':family,'messages':[{'role':role,'content':text} for pair in pairs for role,text in zip(('user','assistant'),pair)],'policies':[policy((i+j)%2==0) for j in range(len(pairs))],
        'provenance':{'kind':'codex_authored','source_group':group,'split':split,'author':'Codex','source_file':'source.py','sealed_release_used':False}}
   notes[ident]=note;rows.append(row)
  # Existing identity candidates retain their source-specific row hashes and split.
  identity_source=ROOT/'reports/ganesh-base-identity-v1'/('train-candidate.jsonl' if split=='train' else 'development-candidate.jsonl')
  candidates=[json.loads(x) for x in identity_source.read_text().splitlines()]
  selected=candidates[:3] if split=='train' else [candidates[0],candidates[2]]
  for original in selected:
   row=json.loads(json.dumps(original));row['provenance'].update(split=split,source_file=str(identity_source.relative_to(ROOT)),source_row_sha256=rowsha(original))
   notes[row['id']]='Exact model/creator facts supplied by user; no identity-bearing system prompt, no claim of a performed external action.'
   rows.append(row)
  specs=([('buttons_total','Use the calculator to add 26 and 17.','add',26,17),('paper_remaining','Use the calculator to subtract 14 from 58.','subtract',58,14),('groups_count','Use the calculator to multiply 7 by 6.','multiply',7,6),('equal_shares','Use the calculator to divide 45 by 5.','divide',45,5)] if split=='train' else
         [('jar_total','Please calculate the sum of 34 and 28.','add',34,28),('seat_difference','Please calculate 91 minus 23.','subtract',91,23)])
  for ident,prompt,op,a,b in specs:
   lesson=Lesson('tools',split,ident,{'entity':ident});lesson.user(prompt);lesson.answer(lesson.call('calculate',{'op':op,'a':a,'b':b}));row=lesson.finish()
   row['id']='english_v1_'+ident;row['family']='tools';row['provenance'].update(source_group=ident,split=split,source_file='prepare.py')
   notes[row['id']]='Read prompt operands/order against actual calculator proposal; final numeric answer matches replayed result. Minimal regression lesson, not English-quality evidence.'
   rows.append(row)
  splits[split]=rows
 groups=[{r['provenance']['source_group'] for r in rows} for rows in splits.values()]
 if groups[0]&groups[1]:raise ValueError('Source group overlap')
 prompts=lambda rows:{' '.join(m['content'].lower().split()) for r in rows for m in r['messages'] if m['role']=='user'}
 if prompts(splits['train'])&prompts(splits['development']):raise ValueError('Exact prompt split overlap')
 # Screen current dev against exposed historical train/dev, never parse sealed release.
 old=set()
 for file in ['reports/corrective-corpus-v1/train.jsonl','reports/corrective-corpus-v1/validation.jsonl','reports/english-first-v1/fit-train.jsonl','reports/english-first-v1/development-reference.jsonl']:
  old |= prompts([json.loads(x) for x in (ROOT/file).read_text().splitlines()])
 collisions=sorted(prompts(splits['development'])&old)
 if collisions:raise ValueError('Historical exact prompt overlap: '+repr(collisions))
 reviews=[];stats={};suite=[]
 for split,rows in splits.items():
  lengths=[];reply_lengths=[];mode_mass=collections.Counter();targets=0;calls=0
  for row in rows:
   enc=encode_conversation(tokenizer,row['messages'],policies=row['policies'],context=2048)
   lengths.append(len(enc['ids']));targets+=sum(enc['mask'][1:])
   users=-1;turn_notes=[]
   for k,m in enumerate(row['messages']):
    if m['role']=='user':users+=1
    if m['role']=='assistant':
     prefix=encode_conversation(tokenizer,row['messages'][:k],policies=row['policies'][:users+1],for_generation=True,context=2048,reply_budget=192)
     if prefix['ids']!=enc['ids'][:len(prefix['ids'])]:raise ValueError('Serving/training prefix mismatch')
     if 'content' in m:reply_lengths.append(len(tokenizer.encode(m['content']))+1)
   for span in enc['spans']:
    if span['kind']=='assistant_end' and not all(enc['mask'][span['start']:span['end']]):raise ValueError('End target missing')
    if span['kind'] in ('user_prompt','tool_result_json') and any(enc['mask'][span['start']:span['end']]):raise ValueError('Input/result leakage')
   if row['family']=='tools':calls+=validate_lesson(row)['actual_calls']
   # Exact target mass per policy/action mode, by independently encoded complete turns.
   messages=row['messages'];boundaries=[k for k,m in enumerate(messages) if m['role']=='user']+[len(messages)]
   turn_specs=[]
   for j,(start,end) in enumerate(zip(boundaries,boundaries[1:])):
    part=messages[start:end];on=row['policies'][j]['permit_calls'];called=any('tool_call' in m for m in part)
    mode=('enabled' if on else 'disabled')+('_call' if called else '_no_call')
    encoded=encode_conversation(tokenizer,part,policies=[row['policies'][j]],context=2048)
    mode_mass[mode]+=sum(encoded['mask'][1:])
    assistant=[m for m in part if m['role']=='assistant' and 'content' in m][-1]['content']
    turn_notes.append({'turn':j,'pass':True,'reason':notes[row['id']],'reference':assistant})
    turn_specs.append({'user':part[0]['content'],'policy':row['policies'][j],'reference_answer':assistant,'expected_calls':[m['tool_call'] for m in part if 'tool_call' in m],
       'reply_budget':192,'rubric':notes[row['id']]+' Judge meaning using actual prior model history; no invented facts/actions; clean termination.'})
   reviews.append({'id':row['id'],'split':split,'row_sha256':rowsha(row),'reviewer':'Codex author and second semantic pass, NOT independent','turns':turn_notes,'pass':True})
   if split=='development':suite.append({'id':row['id'],'source_group':row['provenance']['source_group'],'category':row['family'],'turns':turn_specs})
  name='train.jsonl' if split=='train' else 'development.jsonl'
  path=P/name
  if path.exists():raise FileExistsError(path)
  path.write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows))
  dataset=JsonlConversations(path,tokenizer,sha(path))
  stats[split]={**dataset_coverage(dataset),'target_mass_by_mode':dict(mode_mass),'min_tokens':min(lengths),'max_tokens':max(lengths),'max_reply_tokens':max(reply_lengths),'tool_calls_replayed':calls}
 devsuite={'schema':1,'purpose':'development_only_never_train','required_context_tokens':2048,'sessions':suite};validate_suite(devsuite)
 write('development-suite.json',devsuite)
 write('review.json',{'scope':'Small pilot curriculum, not independent release evidence','records':reviews,'stats':stats,'source_review':'All36 authored natural trajectories manually read in source.py and checked against each requested update, constraint and state; identity source facts are user supplied. Every tool is replayed.','limitations':['Only short multi-turn state coverage; no near2K delayed-memory claim.','Related semantic structures across development are deliberate skill-transfer probes, not pristine template-disjoint release.','No external source rows newly admitted: reviewed candidates remain in their original shortlists; this pilot is explicitly synthetic.','No unreviewed variants or volume expansion.'],'split_checks':{'source_group_overlap':0,'exact_prompt_overlap':0,'historical_exposed_dev_prompt_overlap':0,'sealed_release_read':False}})
 parent={'schema':1,'purpose':'New synthetic English pilot source specification','source_sha256':sha(P/'source.py'),'builder_sha256':sha(P/'prepare.py'),'review_sha256':sha(P/'review.json'),'identity_source_sha256':[sha(ROOT/'reports/ganesh-base-identity-v1'/x) for x in ('train-candidate.jsonl','development-candidate.jsonl')]}
 write('source-manifest.json',parent)
 toksha=sha(ROOT/'runs/ownbase-v2-data/tokenizer/tokenizer.pkl')
 admission={'schema':1,'training_admitted':True,'scope':'Bounded pilot only; NOT release eligibility','format_version':VERSION,'context_tokens':2048,'tokenizer_sha256':toksha,'parent_manifest_sha256':sha(P/'source-manifest.json'),'jsonl_sha256':[sha(P/'train.jsonl'),sha(P/'development.jsonl')],'review_sha256':sha(P/'review.json')}
 write('admission.json',admission)
 manifest={'schema':1,'training_admitted':True,'format_version':VERSION,'context_tokens':2048,'tokenizer_sha256':toksha,'parent_manifest_sha256':admission['parent_manifest_sha256'],'admission':{'receipt':'admission.json','sha256':sha(P/'admission.json')},'train':{'file':'train.jsonl','sha256':sha(P/'train.jsonl')},'validation':{'file':'development.jsonl','sha256':sha(P/'development.jsonl')}}
 write('manifest.json',manifest)
 # Explicit blocked release artifact, NOT a fake sealed suite. Contract blocks every release.
 write('release-unavailable.json',{'purpose':'release_unavailable_pilot_only','reason':'No independently reviewed release suite admitted. This pilot cannot authorize release.'})
 protected=ROOT/'cloud_training/evaluation/conversation-tools-dev.json'
 contract={'schema':1,'objective':'conversation_and_tools','diagnostic_only':True,'pilot_only':True,'dataset_manifest_sha256':sha(P/'manifest.json'),'tokenizer_sha256':toksha,'context_tokens':2048,'required_parent_manifest_sha256':admission['parent_manifest_sha256'],'release_suite_sha256':sha(P/'release-unavailable.json'),'protected_suite_sha256':sha(protected),'development_suite_sha256':sha(P/'development-suite.json'),'review_sha256':sha(P/'review.json'),
 'coverage':{'minimum_training_turns':{'disabled_no_call':10,'enabled_no_call':10,'enabled_call':4},'minimum_unique_assistant_targets':stats['train']['assistant_targets'],'minimum_family_sessions':{f:1 for f in ['ordinary','instructions','correction','memory','model_identity','tools']}},
 'recipe_limits':{'max_epochs':3,'max_lr_multiplier':.25,'max_eval_interval':1,'max_pilot_updates':64},'regression':{'relative_tolerance':.05,'patience':2},'unresolved_required_data':[],'release':{'eligible':False},'notes':['Pilot intentionally cannot authorize release. Existing frozen fit must pass before this separate curriculum is trained.','No claim of broad English coverage; optimize for measured learning, not row count.']}
 write('quality-contract.json',contract)
 write('freeze.json',{'files':{x.name:sha(x) for x in sorted(P.iterdir()) if x.is_file() and x.suffix in ('.json','.jsonl','.py')},'scope':'Immutable pilot corpus; create a new version for any change'})
 print(json.dumps(stats,indent=2))
if __name__=='__main__':main()
