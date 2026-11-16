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
 if len(messages)%2 or not 4<=len(messages)<=12 or any(m['role']!=('user' if i%2==0 else 'assistant') for i,m in enumerate(messages)):return
 if sum(len(m['content']) for m in messages)>2200:return
 if not __import__('re').search(r'\b(hello|hi|friend|feeling|write|sentence|polite|email|message|summari|paragraph|weekend|organize|schedule)\w*',messages[0]['content'],__import__('re').I):return
 stats[source+'_structure_length_pool']+=1
 pool.append({'source':source,'id':id,'source_group':group,'messages':messages,'metadata':metadata,'selection_hash':H('own-source-review-v1:'+id)})
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
for source in ['oasst']:
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
  if len(groups)==8:break
(P/'human-focused-sample.json').write_text(json.dumps({'scope':'discovery_only_not_training_or_evaluation','selection':'hash-ranked eligible candidates; 8 human candidates, 2-6 turns and English-task keyword filter; adaptive, not representative','stats':dict(stats),'rows':selected},ensure_ascii=False,indent=2)+'\n')
with (P/'human-focused-review-text.txt').open('w') as f:
 for i,r in enumerate(selected):
  f.write(f"\n=== {i} {r['source']} {r['id']} ===\n")
  for m in r['messages']:f.write(m['role']+': '+m['content']+'\n')
print(dict(stats));print('selected',len(selected))
