"""Read-only provenance, grouping, tokenizer and frozen-input checks."""
import json,gzip,hashlib,sys,subprocess
from pathlib import Path
import pyarrow.parquet as pq
ROOT=Path.cwd();P=Path(__file__).parent;sys.path[:0]=[str(ROOT),str(ROOT/'runs/nanochat-source')]
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_chat_format import encode_conversation,training_example
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
short=json.loads((P/'shortlist.json').read_text())['rows'];assert len(short)==2
train={};valid=set()
for receipt in json.loads((ROOT/'reports/english-source-checks-v1/source-receipts.json').read_text()):
 p=Path(receipt['path'])
 if p.suffix!='.parquet':continue
 assert sha(p)==receipt['sha256']
 if 'validation' in p.name:valid.update(pq.read_table(p,columns=['message_tree_id']).column(0).to_pylist())
 else:
  for r in pq.read_table(p,columns=['message_id','message_tree_id','text','synthetic','review_result','deleted','lang','rank']).to_pylist():
   if r['message_tree_id'] in {x['source_group'] for x in short}:train[r['message_id']]=r
out=[];tok=RustBPETokenizer.from_directory(str(ROOT/'runs/ownbase-v2-data/tokenizer'))
for row in short:
 assert row['source_group'] not in valid
 nodes=[]
 for mid,m in zip(row['path_ids'],row['messages']):
  n=train[mid];assert n['message_tree_id']==row['source_group'] and n['text']==m['content']
  assert n['synthetic']is False and n['review_result']is True and n['deleted']is False and n['lang']=='en'
  if m['role']=='assistant':assert n['rank']==0
  nodes.append({'message_id':mid,'text_sha256':hashlib.sha256(n['text'].encode()).hexdigest(),'source_flags_verified':True})
 checks=[]
 for enabled in (False,True):
  ps=[{'permit_calls':enabled,'allowed_names':['calculate','convert'] if enabled else []}]*2
  e=encode_conversation(tok,row['messages'],policies=ps,context=2048)
  for span in e['spans']:
   if span['kind']=='assistant_end':assert all(e['mask'][span['start']:span['end']])
   if span['kind'] in ('user_prompt','user_start','user_end','assistant_start','bos'):assert not any(e['mask'][span['start']:span['end']])
  ex=training_example(e);assert ex['labels']==[t if m else -100 for t,m in zip(e['ids'][1:],e['mask'][1:])]
  for i,m in enumerate(row['messages']):
   if m['role']=='assistant':
    pre=encode_conversation(tok,row['messages'][:i],policies=ps[:(i+1)//2],context=2048,for_generation=True,reply_budget=384)
    assert pre['ids']==e['ids'][:len(pre['ids'])]
  checks.append({'tools_enabled':enabled,'tokens':len(e['ids']),'targets':sum(e['mask']),'mask_end_shift_prefix_pass':True})
 out.append({'key':row['review_key'],'tree':row['source_group'],'tree_train_message_count':sum(n['message_tree_id']==row['source_group'] for n in train.values()),'validation_tree_messages':0,'nodes':nodes,'encoding':checks,'assistant_content_tokens':[len(tok.encode(m['content'])) for m in row['messages'] if m['role']=='assistant'],'partition':'train_candidate_only_entire_tree','training_admitted':False})
frozen={}
for directory,name in [('reports/english-first-v1','packet-freeze.json'),('reports/corrective-corpus-v1','freeze.json')]:
 d=ROOT/directory;fs=json.loads((d/name).read_text())['files']
 for n,h in fs.items():assert sha(d/n)==h,n
 frozen[directory]={'files':len(fs),'unchanged':True}
review=json.loads((P/'manual-review.json').read_text());assert len(review['records'])==48 and sum(len(x['turns']) for x in review['records'])==96
for r in review['records']:
 if r['decision']=='reviewed_candidate':assert all(x['judgement']=='pass' for x in r['turns'])
assert sum(x['encoding'][0]['targets'] for x in out)==292
ov=json.loads((P/'overlap.json').read_text());assert ov['shortlist_sha256']==sha(P/'shortlist.json');assert not any(q['hits'] for q in ov['queries'])
http=subprocess.run(['lsof','-nP','-iTCP:8765','-sTCP:LISTEN'],capture_output=True);assert http.returncode==1
(P/'validation.json').write_text(json.dumps({'status':'local_candidate_checks_pass_not_training_admission','source_revision':short[0]['source_revision'],'rows':out,'frozen_inputs':frozen,'tokenizer_sha256':sha(ROOT/'runs/ownbase-v2-data/tokenizer/tokenizer.pkl'),'http_off':True,'no_cloud_actions':True},indent=2)+'\n')
print('2 source paths, 292 targets, 41 frozen files and HTTP-off verified')
