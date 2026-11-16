"""Select pinned upstream TRAIN trees before semantic review; no admission."""
import json,gzip,hashlib,re,sys,collections
from pathlib import Path
import pyarrow.parquet as pq
ROOT=Path.cwd();P=Path(__file__).parent;S=ROOT/'reports/english-source-shortlist-v1'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
receipts=json.loads((ROOT/'reports/english-source-checks-v1/source-receipts.json').read_text());membership={};groups=collections.defaultdict(set)
for r in receipts:
 p=Path(r['path'])
 if p.suffix!='.parquet':continue
 assert sha(p)==r['sha256'];split='validation' if 'validation' in p.name else 'train'
 for row in pq.read_table(p,columns=['message_id','message_tree_id']).to_pylist():membership[row['message_id']]=split;groups[row['message_tree_id']].add(split)
old=set()
for name in ['sample.json','focused-sample.json','human-focused-sample.json']:
 for r in json.loads((S/name).read_text())['rows']:
  if r['source']=='oasst':old.add(r['source_group'])
archive=ROOT/'runs/english-source-shortlist-v1/oasst.gz';expected=next(x for x in json.loads((S/'downloads.json').read_text()) if x['key']=='oasst');assert sha(archive)==expected['sha256']
pool=[];stats=collections.Counter()
for line in gzip.open(archive,'rt'):
 t=json.loads(line);group=t['message_tree_id'];stats['trees']+=1
 if groups[group]!={'train'}:stats['non_train_trees_excluded']+=1;continue
 if group in old:stats['previously_exposed_trees_excluded']+=1;continue
 def walk(n,path,ids):
  if membership.get(n['message_id'])!='train' or n.get('lang')!='en' or n.get('synthetic')is not False or n.get('review_result')is not True or n.get('deleted'):return
  role='user' if n['role']=='prompter' else n['role']
  if role=='assistant' and n.get('rank')!=0:return
  path=path+[{'role':role,'content':n['text']}];ids=ids+[n['message_id']]
  if role=='assistant' and 4<=len(path)<=8 and sum(len(m['content']) for m in path)<=2400 and all(len(m['content'])<=1300 for m in path):
   if re.search(r'\b(hello|hi|friend|feeling|write|sentence|polite|email|message|summari|paragraph|weekend|organize|schedule|plan|explain|help)\w*',path[0]['content'],re.I):
    pool.append({'id':n['message_id'],'source_group':group,'messages':path,'path_ids':ids,'upstream_split':'train','all_nodes_reviewed_english_nonsynthetic':True,'assistant_rank':0,'selection_hash':hashlib.sha256(('oasst-train-v1:'+n['message_id']).encode()).hexdigest()})
  for c in n.get('replies',[]):walk(c,path,ids)
 walk(t['prompt'],[],[])
sys.path[:0]=[str(ROOT),str(ROOT/'runs/nanochat-source')]
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_chat_format import encode_conversation
tok=RustBPETokenizer.from_directory(str(ROOT/'runs/ownbase-v2-data/tokenizer'));selected=[];seen=set()
for row in sorted(pool,key=lambda r:r['selection_hash']):
 if row['source_group'] in seen:continue
 try:
  counts=[]
  for enabled in (False,True):
   ps=[{'permit_calls':enabled,'allowed_names':['calculate','convert'] if enabled else []}]*(len(row['messages'])//2)
   e=encode_conversation(tok,row['messages'],policies=ps,context=2048)
   for i,m in enumerate(row['messages']):
    if m['role']=='assistant':
     pre=encode_conversation(tok,row['messages'][:i],policies=ps[:(i+1)//2],context=2048,for_generation=True,reply_budget=384)
     assert pre['ids']==e['ids'][:len(pre['ids'])]
     if len(tok.encode(m['content']))+1>384:raise ValueError('reply budget')
   counts.append({'tools_enabled':enabled,'tokens':len(e['ids']),'targets':sum(e['mask'])})
  row['encoding']=counts
 except ValueError:stats['context_rejected']+=1;continue
 row['review_key']='T'+str(len(selected));row['training_admitted']=False;selected.append(row);seen.add(row['source_group'])
 if len(selected)==48:break
(P/'sample.json').write_text(json.dumps({'source_revision':expected['revision'],'source_receipt':expected,'selection':'hash-ranked train-only new trees, short English-task keyword filter; nonrepresentative discovery','pool_paths':len(pool),'stats':dict(stats),'rows':selected},ensure_ascii=False,indent=2)+'\n')
with (P/'review-text.txt').open('w') as f:
 for r in selected:
  f.write('\n=== '+r['review_key']+' ===\n')
  for m in r['messages']:f.write(m['role']+': '+m['content']+'\n')
print(dict(stats),'pool',len(pool),'sample',len(selected))
