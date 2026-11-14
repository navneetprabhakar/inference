"""Re-audit immutable V21; preserve its split and historical review limitations."""
import json,sys,hashlib,collections,math
from pathlib import Path
if (Path(__file__).resolve().parent/'freeze.json').exists():raise SystemExit('Frozen corpus/release packet: create a new version; do not regenerate in place.')
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'runs/nanochat-source'))
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_chat_format import encode_conversation,training_example
from cloud_training.nano_sft import load_manifest
from tools import execute
P=Path(__file__).resolve().parent;D=ROOT/'runs/corrective-corpus-v1/v21';T=RustBPETokenizer.from_directory(str(ROOT/'runs/ownbase-v2-data/tokenizer'));sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();m=load_manifest(D/'manifest.json',sha(ROOT/'runs/ownbase-v2-data/tokenizer/tokenizer.pkl'),4096)
release=json.loads((P/'release-suite.json').read_text());norm=lambda s:' '.join(s.casefold().split());release_users={norm(t['user']) for s in release['sessions'] for t in s['turns']};newrows={k:[json.loads(l) for l in (P/n).read_text().splitlines()] for k,n in [('train','train.jsonl'),('validation','validation.jsonl')]};stats={};reviewfiles={};missing=[];headroom=[];replays=0;prefixes=0;groups={};fingerprints={};collisions=[]
for split in ['train','validation']:
 rows=[json.loads(l) for l in Path(m[split]['_file']).read_text().splitlines()];fam=collections.Counter();targets=collections.Counter();modes=collections.Counter();late=collections.Counter();groups[split]=set();fingerprints[split]=set();fallbacks=collections.Counter()
 for index,r in enumerate(rows):
  enc=encode_conversation(T,r['messages'],policies=r.get('policies'),context=4096);fam[r['family']]+=1;targets[r['family']]+=sum(enc['mask'][1:]);late['targets_after_2048']+=sum(enc['mask'][2048:]);late['targets_after_3072']+=sum(enc['mask'][3072:]);late['sessions_at_least_3072']+=len(enc['ids'])>=3072
  pr=r.get('provenance',{});group=pr.get('group',pr.get('source_group'))
  if group:groups[split].add(group)
  else:fallbacks['missing_source_group']+=1
  fingerprints[split].add(hashlib.sha256(json.dumps(r['messages'],sort_keys=True).encode()).hexdigest())
  path=pr.get('root_review')
  if path:
   f=ROOT/path
   if f.exists():reviewfiles[path]=sha(f)
   else:missing.append({'split':split,'index':index,'path':path})
  elif pr.get('root_reviewed'):fallbacks['legacy_root_reviewed_flag_without_row_receipt']+=1
  else:fallbacks['synthetic_or_no_row_review_receipt']+=1
  users=0;called=False;enabled=False
  for i,msg in enumerate(r['messages']):
   if msg['role']=='user':
    if users:modes[('enabled' if enabled else 'disabled')+('_call' if called else '_no_call')]+=1
    users+=1;called=False;enabled=bool(r.get('policies') and r['policies'][users-1]['permit_calls'])
    if norm(msg['content']) in release_users:collisions.append({'split':split,'index':index,'user':msg['content']})
   if msg['role']=='assistant':
    pre=encode_conversation(T,r['messages'][:i],policies=r['policies'][:users] if r.get('policies') else None,context=4096,for_generation=True,reply_budget=1);assert pre['ids']==enc['ids'][:len(pre['ids'])];prefixes+=1
    if len(pre['ids'])+192>4096:headroom.append({'split':split,'index':index,'group':group,'message_index':i,'prefix_tokens':len(pre['ids']),'max_reply_tokens':4096-len(pre['ids'])})
    if 'tool_call' in msg:
     called=True;call=msg['tool_call'];record=r['messages'][i+1]['record']
     try:value=execute(call['name'],call['arguments'])
     except ValueError as e:assert not record['ok'] and record['error']==str(e)
     else:assert record['ok'] and math.isclose(value,record['data']['result'],rel_tol=1e-12,abs_tol=1e-12)
     replays+=1
  modes[('enabled' if enabled else 'disabled')+('_call' if called else '_no_call')]+=1
 stats[split]={'sessions':len(rows),'family_sessions':dict(fam),'assistant_targets_by_family':dict(targets),'assistant_targets':sum(targets.values()),'policy_action_turns':dict(modes),'late_context':dict(late),'provenance_limitations':dict(fallbacks)}
# Parent content is not silently re-admitted merely because numeric checks pass.
report={'parent_manifest_sha256':m['_sha256'],'statistics':stats,'prefix_checks':prefixes,'tool_replays':replays,'root_review_file_hashes':reviewfiles,'missing_review_files':missing,'cross_split_named_groups':sorted(groups['train']&groups['validation']),'exact_cross_split_message_fingerprints':len(fingerprints['train']&fingerprints['validation']),'release_exact_prompt_collisions':collisions,'prefixes_without192_token_headroom':headroom,'new_training_admitted':False,'note':'Historical reviews preserved, not claimed as newly completed full semantic review. Missing/group-less legacy provenance and late-prefix headroom require resolution before fresh admission.'}
(P/'parent-v21-audit.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='root_review_file_hashes'},indent=2))
