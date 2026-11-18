"""Fail-closed verification of the versioned selection; never edits corpus text."""
import argparse, collections, hashlib, json, pathlib, sys, unicodedata
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from selection_cli_integrity import cli_artifact, verify_review_input, verify_revision_history
from selection_memory_integrity import verify_memory
ROOT=pathlib.Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'runs/nanochat-source')]
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_chat_format import encode_conversation

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def digest(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def messages(c):return [{'role':r,'content':t[r]} for t in c['turns'] for r in ('user','assistant')]
def norm(s):return ' '.join(unicodedata.normalize('NFKC',s).casefold().split())
def verify_new(row):
 g=row['generation'];assert g['interface']=='codex exec' and g['requested_model']=='gpt-6.1-terra'
 raw=ROOT/g['raw_artifact'];assert sha(raw)==g['raw_sha256']
 cli_artifact(str(raw),str(ROOT),g['raw_sha256'])
 matches=[c for c in json.loads(raw.read_text())['conversations'] if c['group']==row['group']]
 assert len(matches)==1 and messages(matches[0])==row['messages']
 assert matches[0]['family']==row['family']
 assert row.get('training_admitted') is False
 reviews=[]
 for ref in row['review_receipts']:
  p=ROOT/ref['path'];assert sha(p)==ref['sha256']
  data=json.loads(p.read_text())
  if isinstance(data,list) or (isinstance(data,dict) and 'entries' in data and 'reviews' not in data):
   entries=data if isinstance(data,list) else data['entries']
   adjudications=[x for x in entries if x['group']==row['group']]
   assert len(adjudications)==1 and adjudications[0]['messages_sha256']==digest(row['messages'])
   assert adjudications[0]['reviewed_turn_numbers']==list(range(1,len(row['messages'])//2+1))
   assert adjudications[0]['decision']=='pass' and adjudications[0]['assistant_turns_reviewed']==len(row['messages'])//2 and adjudications[0]['rationale'].strip()
  else:
   verify_review_input(p,ROOT,ref['sha256'],row)
   reviews.extend(x for x in data['reviews'] if x['group']==row['group'])
 assert reviews
 n=sum(m['role']=='assistant' for m in row['messages'])
 for r in reviews:
  assert r.get('content_sha256',r.get('messages_sha256'))==digest(row['messages'])
  assert r['decision'] in ('accept','pass')
  assert r.get('memory_annotation_valid',True) and r.get('distinct_scenario',True)
  if 'recall' in r:assert r['recall']['valid']
  indices=sorted(t['turn'] for t in r['turn_reviews'])
  # Early reviewer used flat-message indices. Accept only the complete exact even sequence.
  assert indices in (list(range(1,n+1)),list(range(2,2*n+1,2)))
  assert all(t.get('decision',t.get('verdict'))=='pass' and t['rationale'].strip() for t in r['turn_reviews'])
 plan=row['plan_receipt'];assert sha(ROOT/plan['path'])==plan['sha256']
 planned=json.loads((ROOT/plan['path']).read_text())
 if isinstance(planned,dict):planned=planned.get('plans',planned.get('scenarios'))
 selected=[p for p in planned if p['group']==row['group']]
 assert len(selected)==1
 if selected[0]['turns']!=n:
  variance=row['plan_variance'];assert variance['kind']=='turn_count' and variance['planned']==selected[0]['turns'] and variance['actual']==n and 4<=n<=8
  ref=variance['receipt'];p=ROOT/ref['path'];assert sha(p)==ref['sha256'];audit=json.loads(p.read_text())
  assert audit['group']==row['group'] and audit['messages_sha256']==digest(row['messages'])
  assert audit['kind']=='turn_count' and audit['planned']==selected[0]['turns'] and audit['actual']==n and audit['scenario_preserved'] and audit['reason'].strip()
 return n

def verify_full_content(row):
 ref=row['full_content_review_receipt'];p=ROOT/ref['path'];assert sha(p)==ref['sha256']
 data=json.loads(p.read_text());entries=data['entries'] if isinstance(data,dict) else data
 found=[e for e in entries if e['group']==row['group']];assert len(found)==1
 entry=found[0];n=len(row['messages'])//2
 assert entry['decision']=='pass' and entry['messages_sha256']==digest(row['messages'])
 assert entry['assistant_turns_reviewed']==n and entry['reviewed_turn_numbers']==list(range(1,n+1))
 assert entry['rationale'].strip()
 verify_revision_history(row,ROOT)
 return n

def verify_legacy(row,receipt):
 entries=receipt['entries']
 hits=[e for e in entries if e['group']==row['group']]
 assert len(hits)==1
 e=hits[0];assert e['decision']=='accept' and e['messages_sha256']==digest(row['messages'])
 n=sum(m['role']=='assistant' for m in row['messages']);assert e['assistant_turn_count']==n
 p=ROOT/e['review_path'];assert sha(p)==e['review_sha256']
 raw=[r for r in json.loads(p.read_text())['reviews'] if r['group']==row['group']]
 assert len(raw)==1 and raw[0]['messages_hash']==digest(row['messages'])
 assert sorted(t['turn'] for t in raw[0]['assistant_turns'])==list(range(1,n+1))
 assert all(t['rationale'].strip() for t in raw[0]['assistant_turns'])
 if raw[0]['overall']!='accept':assert e['adjudication_reason'].strip()
 return n

def native(rows):
 tok=RustBPETokenizer.from_directory(str(ROOT/'runs/ownbase-v2-data/tokenizer'))
 totals=collections.Counter();byfamily=collections.Counter();maxprompt=0;maxreply=0;maxfull=0
 for row in rows:
  ms=row['messages'];assert len(ms)%2==0 and all(m['role']==('user' if i%2==0 else 'assistant') for i,m in enumerate(ms))
  n=len(ms)//2
  for enabled in (False,True):
   policies=[{'permit_calls':enabled,'allowed_names':['calculate','convert'] if enabled else []}]*n
   e=encode_conversation(tok,ms,policies=policies,context=2048)
   a=[s['end']-s['start'] for s in e['spans'] if s['kind']=='assistant_text'];b=[s['end']-s['start'] for s in e['spans'] if s['kind']=='assistant_end']
   assert len(a)==len(b)==n
   maxreply=max(maxreply,max(x+y for x,y in zip(a,b)));assert maxreply<=256
   maxfull=max(maxfull,len(e['ids']))
   for i in range(0,len(ms),2):
    p=encode_conversation(tok,ms[:i+1],policies=policies[:i//2+1],for_generation=True,context=2048,reply_budget=256)
    assert e['ids'][:len(p['ids'])]==p['ids'];maxprompt=max(maxprompt,len(p['ids']))
   if not enabled:totals['assistant_targets']+=sum(e['mask']);byfamily[row['family']]+=sum(e['mask'])
  totals['sessions']+=1;totals['assistant_turns']+=n
 return dict(totals, family_target_mass=dict(byfamily),max_prompt=maxprompt,max_prompt_with_reserve=maxprompt+256,max_reply_targets=maxreply,max_complete_context=maxfull)

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('selection');parser.add_argument('--minimum',type=int,default=1000);args=parser.parse_args()
 rows=[json.loads(l) for l in pathlib.Path(args.selection).read_text().splitlines()];assert len(rows)>=args.minimum
 assert len({r['group'] for r in rows})==len(rows)
 hashes=[digest(r['messages']) for r in rows];assert len(set(hashes))==len(rows)
 baseline=ROOT/'runs/ganesh-english-sourcing-v1/reviewed-candidates.jsonl'
 saved=json.loads((pathlib.Path(__file__).parent/'baseline-310.json').read_text())
 # Baseline hash key is explicit in capture; never substitute a new current hash.
 expected=saved.get('payload_sha256',saved.get('sha256'));assert expected and sha(baseline)==expected
 old={r['group']:r for r in map(json.loads,baseline.read_text().splitlines())}
 for row in rows:
  if row['group'] in old:
   assert row['messages']==old[row['group']]['messages']
   for key in ('source','provenance','generation','upstream_split'):assert row.get(key)==old[row['group']].get(key),'Legacy provenance changed: '+key
   ref=row['fresh_selection_receipt'];assert sha(ROOT/ref['path'])==ref['sha256']
   verify_legacy(row,json.loads((ROOT/ref['path']).read_text()))
  else:
   verify_new(row)
   verify_full_content(row)
  verify_memory(row,ROOT)
 stats=native(rows);stats.update(selection_sha256=sha(pathlib.Path(args.selection)),exact_duplicate_sessions=0,training_admitted=False,model_quality_evaluated=False)
 print(json.dumps(stats,indent=2))
