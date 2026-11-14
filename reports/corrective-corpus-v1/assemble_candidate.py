"""Assemble a non-admitted4K candidate from reviewed V21 dialogue plus corrective core.
Drops legacy one-template arithmetic families from BOTH splits, preserving their
GCS originals. No held-out test is used for selection or added to SFT files.
"""
import sys,json,hashlib,collections,copy
from pathlib import Path
if (Path(__file__).resolve().parent/'freeze.json').exists():raise SystemExit('Frozen corpus/release packet: create a new version; do not regenerate in place.')
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'runs/nanochat-source'))
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_chat_format import encode_conversation,VERSION
P=Path(__file__).resolve().parent;D=ROOT/'runs/corrective-corpus-v1/v21';OUT=P/'candidate-4k';OUT.mkdir(exist_ok=True);T=RustBPETokenizer.from_directory(str(ROOT/'runs/ownbase-v2-data/tokenizer'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();digest=lambda x:hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest();natural_reviews={};raw_natural={}
for f in (ROOT/'reports/l4-qualification-v1/natural-dialogue-4k-v1').glob('root-review-cohort-*.json'):
 for r in json.loads(f.read_text())['reviews']:natural_reviews[r['sha256']]=(r,f)
for f in (ROOT/'runs/natural-dialogue-4k-v1').glob('cohort-*/candidates.jsonl'):
 for r in map(json.loads,f.read_text().splitlines()):raw_natural[digest(r)]=(r,f)
patches={r['provenance']['group']:r for r in map(json.loads,(P/'long-prefix-patches.jsonl').read_text().splitlines())};excluded=[];inherited=[];used_receipts={};combined={};stats={};groups={};fingerprints={};release=json.loads((P/'release-suite.json').read_text());release_users={' '.join(t['user'].casefold().split()) for s in release['sessions'] for t in s['turns']}
for split,newfile in [('train','train.jsonl'),('validation','validation.jsonl')]:
 rows=[]
 for index,row in enumerate(map(json.loads,(D/newfile).read_text().splitlines())):
  if row['family'] in ['calculate','convert','tool_correction']:
   excluded.append({'split':split,'index':index,'family':row['family'],'reason':'Legacy narrow synthetic templates share family scaffolds across old splits. Keep immutable originals; exclude from new mixed-curriculum candidate rather than silently call their dev split independent.'});continue
  pr=row['provenance'];cs=pr['candidate_sha256']
  if row['family']=='natural_dialogue_4k':
   review,rf=natural_reviews[cs];raw,sf=raw_natural[cs];assert review['full_dialogue_reviewed'] and review['pass'];assert row['messages']==raw['messages'][:pr['kept_message_count']]
  else:
   rf=ROOT/pr['root_review'];sf=ROOT/pr['source'];reviews=json.loads(rf.read_text())['reviews'];review=next(r for r in reviews if r['sha256']==cs);raw=next(r for r in map(json.loads,sf.read_text().splitlines()) if digest(r)==cs)
   assert review['full_dialogue_reviewed'] and review.get('content_pass',review.get('pass',False));assert row['messages']==raw['messages'] and row['policies']==raw['policies']
  used_receipts[str(rf.relative_to(ROOT))]=sha(rf)
  inherited.append({'split':split,'parent_index':index,'group':pr['group'],'candidate_sha256':cs,'review_file':str(rf.relative_to(ROOT)),'source_file':str(sf.relative_to(ROOT)),'source_file_sha256':sha(sf),'historical_full_review_verified':True,'new_full_review':pr['group'] in patches})
  if pr['group'] in patches:row=patches[pr['group']]
  rows.append(copy.deepcopy(row))
 rows += list(map(json.loads,(P/newfile).read_text().splitlines()))
 counts=collections.Counter();targets=collections.Counter();modes=collections.Counter();late=collections.Counter();maxlen=0;prefixmax=0;groups[split]=set();fingerprints[split]=set()
 for row in rows:
  pr=row['provenance'];group=pr.get('group',pr.get('source_group'));assert group;groups[split].add(group)
  enc=encode_conversation(T,row['messages'],policies=row.get('policies'),context=4096);counts[row['family']]+=1;targets[row['family']]+=sum(enc['mask'][1:]);maxlen=max(maxlen,len(enc['ids']));late['targets_after_2048']+=sum(enc['mask'][2048:]);late['targets_after_3072']+=sum(enc['mask'][3072:]);late['sessions_at_least3072']+=len(enc['ids'])>=3072
  fp=digest(row['messages']);assert fp not in fingerprints[split];fingerprints[split].add(fp);users=0;called=False;enabled=False
  for i,msg in enumerate(row['messages']):
   if msg['role']=='user':
    assert ' '.join(msg['content'].casefold().split()) not in release_users
    if users:modes[('enabled' if enabled else 'disabled')+('_call' if called else '_no_call')]+=1
    users+=1;called=False;enabled=bool(row.get('policies') and row['policies'][users-1]['permit_calls'])
   if msg['role']=='assistant':
    prefix=encode_conversation(T,row['messages'][:i],policies=row['policies'][:users] if row.get('policies') else None,context=4096,for_generation=True,reply_budget=192);assert prefix['ids']==enc['ids'][:len(prefix['ids'])];prefixmax=max(prefixmax,len(prefix['ids']));called|='tool_call' in msg
  modes[('enabled' if enabled else 'disabled')+('_call' if called else '_no_call')]+=1
 p=OUT/newfile;p.write_text(''.join(json.dumps(r,sort_keys=True,ensure_ascii=False)+'\n' for r in rows));combined[split]={'file':newfile,'sha256':sha(p),'sessions':len(rows),'assistant_targets':sum(targets.values())};stats[split]={'families':dict(counts),'targets_by_family':dict(targets),'policy_action_turns':dict(modes),'late_context':dict(late),'max_context':maxlen,'minimum_reply_headroom':4096-prefixmax}
assert not groups['train']&groups['validation'];assert not fingerprints['train']&fingerprints['validation']
report={'parent_manifest_sha256':sha(D/'manifest.json'),'selection':'Keep prior reviewed natural/long-dialogue rows in original splits; replace two fully reviewed long prose variants; add new corrective core; exclude all legacy narrow calculate/convert/tool_correction template rows from both splits.','historical_review_bindings':inherited,'review_receipt_hashes':used_receipts,'excluded':excluded,'statistics':stats,'cross_split_source_groups':0,'exact_cross_split_conversations':0,'release_prompt_collisions':0,'new_training_admitted':False,'review_scope':'Full new178-scenario review separately recorded. Inherited215dialogues retain exact historical full-review/source hash evidence; they are not falsely described as all freshly re-read. Two inherited patches were freshly read in full.'}
(OUT/'assembly-audit.json').write_text(json.dumps(report,indent=2)+'\n');manifest={'schema':1,'training_admitted':False,'format_version':VERSION,'context_tokens':4096,'tokenizer_sha256':sha(ROOT/'runs/ownbase-v2-data/tokenizer/tokenizer.pkl'),'parent_manifest_sha256':sha(D/'manifest.json'),**combined,'blockers':['Fresh corpus admission/recipe contract and semantic near-duplicate review not yet completed.','GPU4K qualification and fault drill not run; no new budget assigned.'],'audit_sha256':sha(OUT/'assembly-audit.json')};(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps({'splits':combined,'statistics':stats,'inherited_review_bindings':len(inherited),'excluded_legacy_templates':len(excluded)},indent=2))
