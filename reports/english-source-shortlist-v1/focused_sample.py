"""Second, explicitly targeted discovery pass after broad scope screening."""
exec(open('reports/english-source-shortlist-v1/sample.py').read().split('for batch in pq.ParquetFile')[0])
import re
for batch in pq.ParquetFile(R/'smol.parquet').iter_batches(batch_size=1000):
 for row in batch.to_pylist():
  ms=row['messages'];stats['scanned']+=1
  if row['source']!='smol-magpie-ultra-short' or not 6<=len(ms)<=12:continue
  if not re.search(r'\b(rewrite|apolog|polite|email|message|summari|paragraph|sentence|weekend|feeling|friend|organize|schedule)\w*',ms[0]['content'],re.I):continue
  if any(len(m['content'])>850 for m in ms) or sum(len(m['content']) for m in ms)>3000:continue
  ident=H(json.dumps(ms,ensure_ascii=False,sort_keys=True))
  add('smol',ident,ident,ms,{'component':row['source'],'train_shard':0,'row_index':stats['scanned']-1})
selected=[]
for row in sorted(pool,key=lambda x:x['selection_hash']):
 counts=[]
 try:
  for enabled in (False,True):
   policies=[{'permit_calls':enabled,'allowed_names':['calculate','convert'] if enabled else []}]*(len(row['messages'])//2)
   e=encode_conversation(tok,row['messages'],policies=policies,context=2048)
   counts.append({'tools_enabled':enabled,'tokens':len(e['ids']),'assistant_targets':sum(e['mask'])})
   for i,m in enumerate(row['messages']):
    if m['role']=='assistant':encode_conversation(tok,row['messages'][:i],policies=policies[:(i+1)//2],for_generation=True,context=2048,reply_budget=128)
 except ValueError:continue
 row['encoding']=counts;selected.append(row)
 if len(selected)==12:break
(P/'focused-sample.json').write_text(json.dumps({'scope':'targeted discovery, not representative; no admission','selection':'short English-task keyword filter then hash order; adaptive second pass','stats':dict(stats),'rows':selected},ensure_ascii=False,indent=2)+'\n')
for i,r in enumerate(selected):
 print('\n=== F',i,'===')
 for m in r['messages']:print(m['role']+': '+m['content'])
