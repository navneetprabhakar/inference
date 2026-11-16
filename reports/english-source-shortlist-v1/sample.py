"""Deterministic bounded discovery sample. Does not admit training data."""
import sys,json,gzip,hashlib,collections
from pathlib import Path
import pyarrow.parquet as pq
ROOT=Path.cwd();sys.path[:0]=[str(ROOT),str(ROOT/'runs/nanochat-source')]
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_chat_format import encode_conversation
P=Path(__file__).parent;R=ROOT/'runs/english-source-shortlist-v1'
tok=RustBPETokenizer.from_directory(str(ROOT/'runs/ownbase-v2-data/tokenizer'))
H=lambda x:hashlib.sha256(x.encode()).hexdigest()
stats=collections.Counter(); pool=[]
def add(source,id,group,messages,metadata):
 stats[source+'_considered']+=1
 if len(messages)%2 or not 6<=len(messages)<=12 or any(m['role']!=('user' if i%2==0 else 'assistant') for i,m in enumerate(messages)):return
 if sum(len(m['content']) for m in messages)>5500:return
 stats[source+'_structure_length_pool']+=1
 pool.append({'source':source,'id':id,'source_group':group,'messages':messages,'metadata':metadata,'selection_hash':H('own-source-review-v1:'+id)})
for batch in pq.ParquetFile(R/'smol.parquet').iter_batches(batch_size=1000):
 for row in batch.to_pylist():
  stats['smol_rows_scanned']+=1
  # Limit discovery to the short conversation component, not task mixtures.
  if row['source']!='smol-magpie-ultra-short':continue
  ms=row['messages']; ident=H(json.dumps(ms,ensure_ascii=False,sort_keys=True))
  add('smol',ident,ident,ms,{'component':row['source'],'train_shard':0,'row_index':stats['smol_rows_scanned']-1})
for line in gzip.open(R/'oasst.gz','rt'):
 tree=json.loads(line);stats['oasst_trees_scanned']+=1
 def walk(node,path):
  if node.get('lang')!='en' or node.get('deleted') or node.get('synthetic') is not False or node.get('review_result') is not True:return
  role='user' if node['role']=='prompter' else node['role']
  if role=='assistant' and node.get('rank')!=0:return
  path=path+[{'role':role,'content':node['text']}]
  if role=='assistant':add('oasst',node['message_id'],tree['message_tree_id'],path,{'leaf_message_id':node['message_id'],'quality_labels':node.get('labels'),'synthetic':False})
  for child in node.get('replies',[]):walk(child,path)
 walk(tree['prompt'],[])
selected=[]
for source in ['smol','oasst']:
 groups=set()
 for row in sorted((x for x in pool if x['source']==source),key=lambda x:x['selection_hash']):
  if row['source_group'] in groups:continue
  try:
   counts=[]
   for enabled in (False,True):
    policies=[{'permit_calls':enabled,'allowed_names':['calculate','convert'] if enabled else []}]*(len(row['messages'])//2)
    enc=encode_conversation(tok,row['messages'],policies=policies,context=2048)
    counts.append({'tools_enabled':enabled,'tokens':len(enc['ids']),'assistant_targets':sum(enc['mask'])})
    for i,m in enumerate(row['messages']):
     if m['role']=='assistant':encode_conversation(tok,row['messages'][:i],policies=policies[:(i+1)//2],for_generation=True,context=2048,reply_budget=128)
   row['encoding']=counts
  except ValueError:stats[source+'_context_rejected_during_selection']+=1;continue
  groups.add(row['source_group']);selected.append(row)
  if len(groups)==12:break
(P/'sample.json').write_text(json.dumps({'scope':'discovery_only_not_training_or_evaluation','selection':'hash-ranked eligible candidates; 12 per source; not representative quality estimate','stats':dict(stats),'rows':selected},ensure_ascii=False,indent=2)+'\n')
with (P/'review-text.txt').open('w') as f:
 for i,r in enumerate(selected):
  f.write(f"\n=== {i} {r['source']} {r['id']} ===\n")
  for m in r['messages']:f.write(m['role']+': '+m['content']+'\n')
print(dict(stats));print('selected',len(selected))
