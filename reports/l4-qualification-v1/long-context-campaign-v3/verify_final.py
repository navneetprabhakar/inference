"""Independent verification of immutable v3 and complete accepted source lineage."""
import hashlib,json,sys
from pathlib import Path
sys.path[:0]=[str(Path('.').resolve()),str(Path('runs/nanochat-source').resolve())]
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_chat_format import encode_conversation
from cloud_training.nano_sft import load_manifest
from tools import FixtureSession
base=Path('runs/long-context-corpus-v2');out=Path('runs/long-context-corpus-v3')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def digest(s):return hashlib.sha256(json.dumps(s,sort_keys=True,separators=(',',':')).encode()).hexdigest()
m=json.loads((out/'manifest.json').read_text());load_manifest(out/'manifest.json',m['tokenizer_sha256'],4096)
a=json.loads((out/'admission.json').read_text());assert a['parent_manifest_sha256']==sha(base/'manifest.json')
tok=RustBPETokenizer.from_directory('runs/ownbase-v2-data/tokenizer');ids=[];calls=0;latecalls=[];totals={2048:0,3072:0}
for split in ['train','validation']:
 old=(base/f'{split}.jsonl').read_bytes();new=(out/f'{split}.jsonl').read_bytes()
 assert new.startswith(old)
 if split=='validation':assert new==old
 for line in new[len(old):].decode().splitlines():
  row=json.loads(line);p=row['provenance'];ids.append(p['candidate_id'])
  source=next(s for s in map(json.loads,Path(p['source']).read_text().splitlines()) if s['id']==p['candidate_id'])
  assert digest(source)==p['candidate_sha256'];assert source['messages']==row['messages'] and source['policies']==row['policies']
  review_path=Path(p['root_review']);assert sha(review_path)==a['root_review_sha256'][str(review_path)]
  review=next(r for r in json.loads(review_path.read_text())['reviews'] if r['id']==p['candidate_id'])
  assert review['sha256']==digest(source) and review['content_pass'] and review['full_dialogue_reviewed'] and review['selected_for_supplement']
  broker=FixtureSession();policy=iter(row['policies']);pending=None
  for msg in row['messages']:
   if msg['role']=='user':broker.start_turn(**next(policy))
   elif 'tool_call' in msg:
    pending=broker.propose(json.dumps(msg['tool_call']),assistant_call_boundary=True);pending.pop('timestamp',None);assert pending['call_id']==msg['call_id']
   elif msg['role']=='tool':assert pending==msg['record'];pending=None
  assert pending is None and next(policy,None) is None;calls+=broker.session_calls
  e=encode_conversation(tok,row['messages'],policies=row['policies'],context=4096)
  for k in totals:totals[k]+=sum(e['mask'][k:])
  latecalls.extend({'id':p['candidate_id'],'token_start':s['start']} for s in e['spans'] if s['kind']=='tool_call_json' and s['start']>=3072)
assert len(ids)==len(set(ids))==len(a['selected'])
assert calls==sum(r['replayed_tool_calls'] for r in a['selected'])
assert totals[3072]==sum(r['assistant_targets_after_3072'] for r in a['selected'])
report={'result':'pass','manifest_sha256':sha(out/'manifest.json'),'new_sessions':len(ids),'new_assistant_targets_after_2048':totals[2048],'new_assistant_targets_after_3072':totals[3072],'replayed_tool_calls':calls,'tool_calls_starting_after_3072':latecalls,'development_byte_identical':True,'prior_training_byte_prefix_identical':True,'source_and_review_hashes_verified':True,'actual_trained_targets':0}
(out/'independent-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
