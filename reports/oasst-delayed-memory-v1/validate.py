"""Read-only provenance/context/freeze checks; no training or release access."""
import json,hashlib,sys
from pathlib import Path
import pyarrow.parquet as pq
ROOT=Path.cwd();P=Path(__file__).parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
receipts=json.loads((ROOT/'reports/english-source-checks-v1/source-receipts.json').read_text())
train={};validation_trees=set();sources={}
for r in receipts:
 p=Path(r['path'])
 if p.suffix!='.parquet':continue
 assert sha(p)==r['sha256'];sources[str(p)]=r['sha256']
 if 'validation' in p.name:
  validation_trees.update(pq.read_table(p,columns=['message_tree_id']).column(0).to_pylist())
 else:
  train={r['message_id']:r for r in pq.read_table(p).to_pylist()}
sys.path[:0]=[str(ROOT),str(ROOT/'runs/nanochat-source')]
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_chat_format import encode_conversation
tok=RustBPETokenizer.from_directory(str(ROOT/'runs/ownbase-v2-data/tokenizer'))
checks=[];seen=set();prefixes=0
for name in ['sample.json','branch-sample.json','focused-sample.json']:
 data=json.loads((P/name).read_text());archive=ROOT/data['source_receipt']['path']
 assert sha(archive)==data['source_receipt']['sha256'];sources[str(archive)]=sha(archive)
 for r in data['rows']:
  assert r['source_group'] not in seen and r['source_group'] not in validation_trees
  seen.add(r['source_group']);ranks=[];parent=None
  for mid,msg in zip(r['path_ids'],r['messages'],strict=True):
   n=train[mid];assert n['message_tree_id']==r['source_group'] and n['parent_id']==parent
   assert n['text']==msg['content'] and ('user' if n['role']=='prompter' else n['role'])==msg['role']
   assert n['lang']=='en' and n['synthetic'] is False and n['review_result'] is True and not n['deleted']
   if msg['role']=='assistant':
    assert isinstance(n['rank'],int) and n['rank']>=0
    if name=='sample.json':assert n['rank']==0
    ranks.append(n['rank'])
   parent=mid
  for enabled in [False,True]:
   policies=[{'permit_calls':enabled,'allowed_names':['calculate','convert'] if enabled else []}]*len(ranks)
   enc=encode_conversation(tok,r['messages'],policies=policies,context=2048)
   for i,m in enumerate(r['messages']):
    if m['role']!='assistant':continue
    pre=encode_conversation(tok,r['messages'][:i],policies=policies[:(i+1)//2],context=2048,for_generation=True,reply_budget=512)
    assert pre['ids']==enc['ids'][:len(pre['ids'])]
    assert len(tok.encode(m['content']))+1<=512
    prefixes+=1
  checks.append({'review_key':r['review_key'],'source_group':r['source_group'],'assistant_source_ranks':ranks,'exact_source_path':True,'both_no_call_modes':True})
frozen={}
for path in ['reports/english-first-v1/packet-freeze.json','reports/corrective-corpus-v1/freeze.json']:
 p=ROOT/path
 for name,digest in json.loads(p.read_text())['files'].items():
  f=p.parent/name;assert sha(f)==digest,str(f);frozen[str(f.relative_to(ROOT))]=digest
assert len(frozen)==41
review=json.loads((P/'review.json').read_text());assert {r['review_key'] for r in review['reviews']}=={r['review_key'] for r in checks}
assert len(checks)==50 and prefixes==300
out={'status':'PASS_source_context_and_freeze_only','conversations':50,'assistant_responses':150,'generation_prefixes_checked':prefixes,'context':2048,'candidate_reply_ceiling':512,'source_files':sources,'checks':checks,'frozen_files':frozen,'retained':0,'admitted':0,'overlap_audit':'Not run: empty shortlist; no contamination clearance claimed.','release_contents_read':False,'cloud_actions':False}
(P/'validation.json').write_text(json.dumps(out,indent=2)+'\n')
print('PASS: 50 exact train paths, 150 responses, 300 prefixes, 41 frozen files; 0 retained/admitted.')
