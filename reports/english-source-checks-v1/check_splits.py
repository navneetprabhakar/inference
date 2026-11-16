import json,gzip,hashlib
from pathlib import Path
import pyarrow.parquet as pq
P=Path(__file__).parent;S=Path('reports/english-source-shortlist-v1');rows=json.loads((S/'shortlist.json').read_text())['rows'];h=next(r for r in rows if r['source']=='oasst')
tree=None
for line in gzip.open('runs/english-source-shortlist-v1/oasst.gz','rt'):
 t=json.loads(line)
 if t['message_tree_id']==h['source_group']:tree=t;break
assert tree is not None
nodes=[]
def find(n,anc):
 if n['message_id']==h['id']:return anc+[n]
 for c in n.get('replies',[]):
  found=find(c,anc+[n])
  if found:return found
path=find(tree['prompt'],[]);assert len(path)==len(h['messages'])
for n,m in zip(path,h['messages']):
 assert n['text']==m['content']
 assert n['lang']=='en' and n['synthetic']is False and n['review_result']is True and not n['deleted']
 if n['role']=='assistant':assert n['rank']==0
membership={};group_counts={}
for receipt in json.loads((P/'source-receipts.json').read_text()):
 f=Path(receipt['path'])
 if f.suffix!='.parquet':continue
 split='validation' if 'validation' in f.name else 'train';count=0
 for batch in pq.ParquetFile(f).iter_batches(columns=['message_id','parent_id','message_tree_id']):
  for r in batch.to_pylist():
   if r['message_tree_id']==h['source_group']:
    count+=1;membership.setdefault(r['message_id'],[]).append(split)
 group_counts[split]=count
path_splits=sorted({sp for n in path for sp in membership.get(n['message_id'],[])})
assert all(membership.get(n['message_id']) for n in path)
training_split_ok=path_splits==['train'] and group_counts['validation']==0
smol=[]
for r in rows:
 if r['source']!='smol':continue
 i=r['metadata']['row_index'];table=pq.read_table('runs/english-source-shortlist-v1/smol.parquet');actual=table.slice(i,1).to_pylist()[0];assert actual['messages']==r['messages'] and actual['source']==r['metadata']['component']
 smol.append({'key':r['review_key'],'upstream_split':'train','row_index':i,'exact_source_content_match':True,'synthetic_generator':'Llama-3.1-405B-Instruct per pinned parent card','disposition':'hold_generator_terms','group':'smol-short-editing-template-family'})
result={'oasst':{'key':h['review_key'],'tree_id':h['source_group'],'path_ids':[n['message_id'] for n in path],'upstream_path_splits':path_splits,'training_split_ok':training_split_ok,'disposition':'hold_upstream_validation' if not training_split_ok else 'train_candidate','tree_messages_by_split':group_counts,'source_content_and_flags_verified':True,'policy':'Entire tree and all related variants stay together; exposed upstream validation is not training or pristine release'},'smol':smol,'future_group_registry':[{'key':r['review_key'],'group':h['source_group'] if r['source']=='oasst' else 'smol-short-editing-template-family','partition':'hold_not_train_or_release','training_admitted':False} for r in rows],'no_validation_or_release_created':True}
(P/'source-groups.json').write_text(json.dumps(result,indent=2)+'\n');print(result)
