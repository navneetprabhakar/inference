"""Prepare a hash-bound, reviewed 4K pilot; never admit model-reviewed-only rows."""
import argparse,collections,hashlib,json,re,sys
from pathlib import Path
sys.path[:0]=[str(Path('.').resolve()),str(Path('runs/nanochat-source').resolve())]
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_chat_format import encode_conversation,VERSION
from cloud_training.nano_sft import load_manifest
from cloud_training.nano_tool_lessons import validate_lesson
ROOT=Path('runs/natural-dialogue-4k-v1');REPORT=Path('reports/l4-qualification-v1/natural-dialogue-4k-v1')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'))
def digest(x):return hashlib.sha256(canonical(x).encode()).hexdigest()
def norm(s):return ' '.join(re.findall(r'\w+',s.casefold()))
def shingles(s):
 w=norm(s).split();return {tuple(w[i:i+5]) for i in range(max(0,len(w)-4))}
def prepare(out,admit=False):
 if out.exists():raise ValueError('Immutable output already exists')
 tokdir=Path('runs/ownbase-v2-data/tokenizer');tok=RustBPETokenizer.from_directory(str(tokdir));toksha=sha(tokdir/'tokenizer.pkl')
 reviews={};reviewfiles=sorted(REPORT.glob('root-review-cohort-*.json'))
 for p in reviewfiles:
  for r in json.loads(p.read_text())['reviews']:
   if r['id'] in reviews:raise ValueError('Duplicate root verdict')
   assert r['full_dialogue_reviewed'] is True
   reviews[r['id']]=r
 external_files=[]
 for folder in ['runs/natural-dialogue-pilot-v1','runs/conversation-data-offline-v1/production','runs/teacher-student-execution-v1/production']:
  external_files.extend(sorted(Path(folder).glob('**/candidates.jsonl')))
 external_files.extend(Path('runs/literal-state-repair-v1/admitted-v1')/f for f in ['train.jsonl','validation.jsonl'])
 external_keys=set();external_hashes={}
 for p in external_files:
  external_hashes[str(p)]=sha(p)
  for row in map(json.loads,p.read_text().splitlines()):
   if 'messages' in row:external_keys.add(digest([norm(m['content']) for m in row['messages'] if m['role']=='user']))
 candidates=[];excluded=[];seen=set();verified_reviews=set()
 for p in sorted(ROOT.glob('cohort-*/candidates.jsonl')):
  for r in map(json.loads,p.read_text().splitlines()):
   v=reviews.get(r['id'])
   if v:
    if v['sha256']!=digest(r):raise ValueError('Root review does not bind current candidate')
    verified_reviews.add(r['id'])
   if not v or not v['pass']:
    excluded.append({'id':r['id'],'reason':'not_root_reviewed' if not v else 'root_reject'});continue
   r=dict(r);r['_source_sha256']=digest({k:v for k,v in r.items() if k!='_source_sha256'})
   keep=v.get('keep_message_count',len(r['messages']))
   assert type(keep) is int and 2<=keep<=len(r['messages']) and keep%2==0
   r['messages']=r['messages'][:keep]
   # A thank-you exchange does not turn a one-answer example into context data.
   # Root review explicitly trims closing-only suffixes before this check.
   if sum(m['role']=='assistant' for m in r['messages'])<2:
    excluded.append({'id':r['id'],'reason':'fewer_than_two_substantive_assistant_turns'});continue
   userkey=digest([norm(m['content']) for m in r['messages'] if m['role']=='user'])
   if userkey in external_keys:excluded.append({'id':r['id'],'reason':'prior_corpus_exact_user_sequence'});continue
   if userkey in seen:excluded.append({'id':r['id'],'reason':'duplicate_user_sequence'});continue
   seen.add(userkey)
   e=encode_conversation(tok,r['messages'],context=4096)
   assert len(e['ids'])<=4096 and sum(e['mask'][1:])>0
   candidates.append((r,e))
 # Document families and paraphrases stay together. This heuristic supplements full review.
 parents={r['group']:r['group'] for r,e in candidates}
 def find(x):
  while parents[x]!=x:x=parents[x]
  return x
 def union(a,b):parents[find(b)]=find(a)
 textsets=[shingles(r['reference_text'] or ' '.join(m['content'] for m in r['messages'] if m['role']=='user')) for r,e in candidates]
 near=[]
 for i,(a,_) in enumerate(candidates):
  for j,(b,_) in enumerate(candidates[:i]):
   aa,bb=textsets[i],textsets[j];score=len(aa&bb)/max(1,len(aa|bb))
   if a['group']==b['group']:continue
   if score>=.65:
    union(a['group'],b['group']);near.append({'a':a['id'],'b':b['id'],'jaccard':score})
 # Reject across-family near duplicates rather than inflating unique volume.
 dropped=set()
 for pair in near:dropped.add(pair['a'])
 candidates=[(r,e) for r,e in candidates if r['id'] not in dropped]
 excluded.extend({'id':x,'reason':'cross_family_near_duplicate'} for x in sorted(dropped))
 groups=sorted({find(r['group']) for r,e in candidates},key=digest)
 # Expanding the corpus must not promote an earlier development family to train.
 # Preserve assignments from every admitted snapshot; development wins if an
 # older snapshot already moved a family between splits. No pilot has trained yet.
 prior_groups={'train':set(),'validation':set()};split_sources={}
 for mp in sorted(ROOT.glob('*/manifest.json')):
  previous=json.loads(mp.read_text())
  if not previous.get('training_admitted'):continue
  load_manifest(mp,toksha,4096)
  split_sources[str(mp)]=sha(mp)
  for split in prior_groups:
   for row in map(json.loads,(mp.parent/previous[split]['file']).read_text().splitlines()):
    if row.get('family')=='natural_dialogue_4k':
     group=row['provenance']['group']
     if group in parents:prior_groups[split].add(find(group))
 dev=prior_groups['validation']&set(groups)
 desired=max(1,len(groups)//5) if len(groups)>1 else 0
 fresh=[g for g in groups if g not in dev and g not in prior_groups['train']]
 dev.update(fresh[:max(0,desired-len(dev))])
 rows={'train':[],'validation':[]};counts={s:collections.Counter() for s in rows};targets={s:0 for s in rows}
 for r,e in candidates:
  split='validation' if find(r['group']) in dev else 'train'
  # Only visible messages are training input. Private briefs, ledgers, probes excluded.
  row={'messages':r['messages'],'family':'natural_dialogue_4k','provenance':{'kind':'interactive_teacher','teacher':r['teacher'],'candidate_id':r['id'],'candidate_sha256':r['_source_sha256'],'kept_message_count':len(r['messages']),'group':find(r['group']),'root_reviewed':True}}
  rows[split].append(row);targets[split]+=sum(e['mask'][1:]);counts[split]['natural_dialogues']+=1
  counts[split]['under_2048' if len(e['ids'])<2048 else '2048_to_3071' if len(e['ids'])<3072 else '3072_to_4096']+=1
 # Preserve tool behaviour using exact members of the existing admitted splits.
 source=Path('runs/literal-state-repair-v1/admitted-v1');source_manifest=load_manifest(source/'manifest.json',toksha)
 for split in rows:
  cap=int(targets[split]*.15);used=0;family_targets=collections.Counter()
  for r in map(json.loads,(source/(split+'.jsonl')).read_text().splitlines()):
   if r['family'] not in {'calculate','convert','tool_correction'}:continue
   e=encode_conversation(tok,r['messages'],policies=r.get('policies'),context=4096);n=sum(e['mask'][1:])
   if used+n>cap or family_targets[r['family']]+n>cap//3:continue
   validate_lesson(r);rows[split].append(r);used+=n;family_targets[r['family']]+=n;counts[split]['tool_replay_dialogues']+=1;counts[split]['tool_'+r['family']]+=1
  targets[split]+=used;counts[split]['tool_replay_assistant_targets']=used
 keys={s:{digest([norm(m['content']) for m in r['messages'] if m['role']=='user']) for r in rr} for s,rr in rows.items()}
 assert not keys['train']&keys['validation'],'Train/dev user-sequence overlap'
 # Known evaluation turns cannot enter training, even inside a longer dialogue.
 evaluation_prompts=set()
 paths=[Path('cloud_training/evaluation/conversation-tools-dev.json'),*Path('reports/l4-qualification-v1').glob('*/heldout-suite.json')]
 for p in paths:
  for s in json.loads(p.read_text()).get('sessions',[]):
   for t in s.get('turns',[]):
    if 'user' in t:evaluation_prompts.add(norm(t['user']))
 for row in rows['train']:
  assert not any(norm(m['content']) in evaluation_prompts for m in row['messages'] if m['role']=='user'),'Known evaluation prompt in training'
 ready=len(verified_reviews)>=50 and bool(rows['train']) and bool(rows['validation']) and len(groups)>=10
 if admit and not ready:raise ValueError('Admission requires50 hash-bound full root reviews and10 independent groups, nonempty train/dev')
 out.mkdir(parents=True)
 manifest={'schema':1,'training_admitted':bool(admit),'format_version':VERSION,'context_tokens':4096,'tokenizer_sha256':toksha}
 for split,rr in rows.items():
  p=out/(split+'.jsonl');p.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rr))
  manifest[split]={'file':p.name,'sha256':sha(p),'bytes':p.stat().st_size,'sessions':len(rr),'assistant_targets':targets[split]}
 report={'training_admitted':bool(admit),'root_reviewed':len(verified_reviews),'root_passed_selected':sum(c['natural_dialogues'] for c in counts.values()),'ready_for_admission':ready,'counts':{s:dict(c) for s,c in counts.items()},'excluded':excluded,'near_duplicates':near,'independent_groups':len(groups),'prior_corpus_exact_screen_sha256':external_hashes,'source_tool_manifest_sha256':sha(source/'manifest.json'),'root_review_files':{str(p):sha(p) for p in reviewfiles},'builder_sha256':sha(__file__),'limitations':['Small pilot, not evidence of model usability.','Lexical near-duplicate screen plus full root review; not embedding-based semantic equivalence detection.','Validation is development data, not a pristine benchmark.','No newly generated long tool dialogues in this version; tool replay is short-context.']}
 report['prior_split_manifest_sha256']=split_sources
 report['prior_cross_split_groups_quarantined_to_development']=sorted(prior_groups['train']&prior_groups['validation'])
 (out/'preparation.json').write_text(json.dumps(report,indent=2)+'\n')
 if admit:
  receipt={**report,'schema':1,'context_tokens':4096,'format_version':VERSION,'tokenizer_sha256':toksha,'jsonl_sha256':[manifest[s]['sha256'] for s in rows]}
  (out/'admission.json').write_text(json.dumps(receipt,indent=2)+'\n');manifest['admission']={'receipt':'admission.json','sha256':sha(out/'admission.json')}
 (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 if admit:load_manifest(out/'manifest.json',toksha,4096)
 print(json.dumps(report,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--admit',action='store_true');a=p.parse_args();prepare(a.out,a.admit)
