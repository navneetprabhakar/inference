"""Prepare a frozen, small chat/tool diagnostic experiment, not a release corpus."""
import collections,hashlib,json,re,shutil
from pathlib import Path
import numpy as np
import pyarrow.parquet as pq
from tokenizers import Tokenizer
from sft_common import *
from prepare_continuation import Near,fingerprint
DATA=ROOT/'data/sft-v1';REPORT=ROOT/'reports/sft-v1'
def digest(x):return hashlib.sha256(x.encode()).hexdigest()
def msg(role,content):return {'role':role,'content':content}
# Templates 0..7 train; 8..9 dev; 10..11 test. Entities/numbers also separated.
TEMPLATES={
'calculate':['Please {op} {a} and {b}.','Use the calculator to {op} {a} and {b}.','I need you to {op} {a} and {b}.','Could you {op} {a} and {b}?','Calculate this: {op} {a} and {b}.','Help me {op} {a} and {b}.','Find the result when you {op} {a} and {b}.','With the tool, {op} {a} and {b}.','Work out {op} with operands {a}, {b}.','The operation is {op}; inputs are {a} and {b}.','For two values, {a} then {b}, perform {op}.','Apply {op} to the pair ({a}, {b}) and report the outcome.'],
'convert':['Convert {value} {from_unit} to {to_unit}.','What is {value} {from_unit} in {to_unit}?','Please change {value} {from_unit} into {to_unit}.','Use conversion for {value} {from_unit} to {to_unit}.','I need {value} {from_unit} expressed in {to_unit}.','How many {to_unit} are {value} {from_unit}?','Turn {value} {from_unit} into {to_unit}.','Calculate {value} {from_unit} in {to_unit}.','Express a length of {value} {from_unit} using {to_unit}.','My measurement is {value} {from_unit}; the desired unit is {to_unit}.','The original unit is {from_unit}, quantity {value}; give the equivalent in {to_unit}.','Switch the scale from {from_unit} to {to_unit} for a measurement of {value}.'],
'get_weather':['What is the weather in {city}?','Check weather for {city}.','Please get the temperature in {city}.','Tell me the weather for {city}.','Use the weather tool for {city}.','How is the weather in {city}?','Find the conditions in {city}.','Show me weather in {city}.','I am travelling to {city}; check its weather.','Look up the current conditions for the city of {city}.','For my destination, {city}, obtain the temperature and conditions.','Retrieve the weather reading associated with {city}.'],
'lookup_item':['Look up item {item_id}.','Check the price of {item_id}.','How much stock is there for {item_id}?','Find item {item_id} in the catalog.','Please get details for {item_id}.','Show me catalog item {item_id}.','What is the price and stock of {item_id}?','Use the catalog for {item_id}.','Retrieve the inventory record keyed by {item_id}.','I need pricing information for product code {item_id}.','The identifier on my product is {item_id}; fetch its inventory entry.','For catalog reference {item_id}, obtain the available quantity and cost.'],
'search_notes':['Search my notes for {query}.','Find notes about {query}.','Look up {query} in notes.','Please search notes for {query}.','What do my notes say about {query}?','Get the note on {query}.','Find the meeting note for {query}.','Use note search for {query}.','Locate the note matching the keyword {query}.','Retrieve my saved note concerning {query}.','Within the notes collection, seek the entry mentioning {query}.','Consult the stored meeting notes using {query} as the search term.']}
PREFIX={'train':'A','dev':'D','test':'T'}
def tool_record(split,i,kind='single'):
 rng=np.random.default_rng(871+i+{'train':0,'dev':100000,'test':200000}[split]);names=list(SCHEMAS);name=names[i%5];offset={'train':0,'dev':100,'test':200}[split];t=(i//5)%8 if split=='train' else (8 if split=='dev' else 10)+(i//5)%2
 a=int(rng.integers(1+offset,90+offset));b=int(rng.integers(1+offset,90+offset));entity=PREFIX[split]+str(int(rng.integers(1,10000)))
 args={'calculate':{'op':['add','subtract','multiply','divide'][i%4],'a':a,'b':b},'convert':{'value':a,'from_unit':['m','km','cm'][i%3],'to_unit':['cm','m','km'][i%3]},'get_weather':{'city':['Pune','Delhi','Patna','Jaipur','Kochi'][i%5]+' '+entity},'lookup_item':{'item_id':'SKU-'+entity},'search_notes':{'query':['budget','travel','launch','design','review'][i%5]+' '+entity}}[name]
 call={'name':name,'arguments':args};q=TEMPLATES[name][t].format(**args);messages=[msg('system',system()),msg('user',q)]
 record={'id':f'{split}-tool-{kind}-{i}','source':'tool','kind':kind,'split':split,'family':f'{name}-template-{t}','messages':messages}
 if kind=='clarify':
  field={'calculate':'b','convert':'to_unit','get_weather':'city','lookup_item':'item_id','search_notes':'query'}[name]
  questions={'calculate':f'Please add {a} to another number.','convert':f'Convert {a} m.','get_weather':'Please check the weather.','lookup_item':'Please look up an item.','search_notes':'Please search my notes.'}
  variants={'train':'Request reference '+entity+'. ','dev':'For request '+entity+', I need help. ','test':'The tracking reference is '+entity+'. Can you assist? '};messages[-1]['content']=variants[split]+questions[name]
  answer={'calculate':'What is the second number?','convert':'Which target unit should I use?','get_weather':'Which city should I check?','lookup_item':'What is the item ID?','search_notes':'What query should I search for?'}[name]
  record.update(expected_words={'calculate':['number'],'convert':['unit'],'get_weather':['city'],'lookup_item':['item'],'search_notes':['query','search']}[name],expected_answer=answer)
 elif kind=='none':
  texts=[('Hello!','Hello! How can I help you?'),('Thank you for your help.','You are welcome!'),('Tell me what a calculator does.','A calculator performs arithmetic operations such as addition and multiplication.'),('What is a weather forecast?','A weather forecast predicts conditions such as temperature and rain.'),('Explain what a catalog is.','A catalog lists items and information about them.')]
  q,answer=texts[i%len(texts)];q=({'train':'','dev':'Quick question: ','test':'Please respond without taking any action: '}[split])+q;messages[-1]['content']=q;record.update(expected_answer=answer)
 elif kind=='error':
  call={'name':'calculate','arguments':{'op':'divide','a':a,'b':0}};result=execute(call)
  messages=[msg('system',system(['calculate'])),msg('user',f'Divide {a} by zero.'),msg('assistant',call_text(call)),msg('tool',json.dumps(result))];record['messages']=messages;answer=result_answer(call,result);record.update(expected_words=['zero','nonzero'],expected_answer=answer)
 elif kind=='chain':
  c1={'name':'convert','arguments':{'value':a,'from_unit':'km','to_unit':'m'}};r1=execute(c1);c2={'name':'calculate','arguments':{'op':'add','a':r1['result'],'b':b}};r2=execute(c2)
  q=(f'Convert {a} km to m, then add {b}.' if split=='train' else f'First express {a} kilometres in metres. Increase that result by {b}.' if split=='dev' else f'I have {a} km plus {b} metres. Convert the kilometres using the tool, then calculate their sum in metres.')
  messages=[msg('system',system(['convert','calculate'])),msg('user',q)];answer=result_answer(c2,r2);record.update(messages=messages,calls=[c1,c2],expected_answer=answer)
 else:
  result=execute(call);answer=result_answer(call,result);record.update(calls=[call],expected_answer=answer)
 episode=list(record['messages'])
 for c in record.get('calls',[]):episode += [msg('assistant',call_text(c)),msg('tool',json.dumps(execute(c),separators=(',',':')))]
 episode += [msg('assistant',record['expected_answer'])];record['episode']=episode
 return record

def grounded_record(split,i):
 offset={'train':0,'dev':10000,'test':20000}[split];n=offset+i;rng=np.random.default_rng(9017+n);name=['Asha','Ravi','Leena','Omar','Nina','Dev'][i%6]+' '+str(n);city=str(rng.choice(['Pune','Delhi','Jaipur','Kochi','Patna','Agra']));job=str(rng.choice(['teacher','nurse','engineer','baker','artist','driver']))
 contexts=[f'{name} lives in {city} and works as a {job}.',f'The resident named {name} works as a {job}. Their home is in {city}.',f'{city} is home to {name}, whose occupation is {job}.']
 context=contexts[{'train':0,'dev':1,'test':2}[split]];unknown=i%5==0;answer='The context does not say.' if unknown else (city if i%2 else job)
 question=f'What is {name}\'s age?' if unknown else (f'Where does {name} live?' if i%2 else f'What is {name}\'s job?')
 messages=[msg('system','Answer using only the given context. If the answer is missing, say that the context does not say.'),msg('user','Context: '+context+'\nQuestion: '+question)]
 if i%4==0 and not unknown:
  messages += [msg('assistant',answer),msg('user','Please repeat only the answer, without explanation.')]
 return {'id':f'{split}-grounded-{i}','source':'grounded','kind':'grounded','split':split,'family':f'context-{split}','messages':messages,'expected_answer':answer,'episode':messages+[msg('assistant',answer)]}

def main():
 DATA.mkdir(exist_ok=True);REPORT.mkdir(exist_ok=True)
 if (DATA/'manifest.json').exists():raise RuntimeError('Data already frozen')
 tok=Tokenizer.from_file(str(ROOT/'data/pilot-v1/tokenizer.json'));shutil.copyfile(ROOT/'data/pilot-v1/tokenizer.json',DATA/'tokenizer.json')
 groups={};near=Near();records={'train':[],'dev':[],'test':[]};stats=collections.Counter();seen=set();counts=collections.Counter()
 for b in pq.ParquetFile(DATA/'raw/smol-smoltalk.parquet').iter_batches(batch_size=256):
  for row in b.to_pylist():
   if row['source'] not in ['smol-magpie-ultra-short','everyday-conversations','smol-contraints']:continue
   ms=row['messages'];users=[x['content'] for x in ms if x['role']=='user']
   if not users:continue
   key=digest(' '.join(users[0].casefold().split()));split='dev' if int(key[:8],16)%100==0 else 'test' if int(key[:8],16)%100 in [1,2] else 'train'
   if counts[split]>={'train':10000,'dev':100,'test':200}[split]:continue
   if key in groups:continue
   groupfp=fingerprint(users[0])
   if near.contains(groupfp):continue
   # Keep complete leading turns only; never cut an assistant response.
   chosen=[]
   for m in ms:
    if m['role'] not in ['system','user','assistant']:break
    if m['role']=='assistant':
     trial=chosen+[m]
     if encode_episode(tok,trial) is None:break
    chosen.append(m)
   while chosen and chosen[-1]['role']!='assistant':chosen.pop()
   if not chosen or len(chosen)<2:continue
   text=' '.join(x['content'] for x in chosen)
   if len(text)<80 or any(w in text.lower() for w in ['```','roleplay','role-play','as an ai language model','monodromy','sexual']):continue
   letters=[c for c in text if c.isalpha()]
   if not letters or sum(c.isascii() for c in letters)/len(letters)<.97:continue
   if any(len(x['content'].split())>120 for x in chosen if x['role']=='assistant'):continue
   ep=encode_episode(tok,chosen)
   prompt=chosen[:-1]
   if ep is None or len(tok.encode(render(prompt,True)).ids)>416:continue
   h=digest(render(chosen))
   if h in seen:continue
   groups[key]=split;near.add(groupfp);seen.add(h);counts[split]+=1
   records[split].append({'id':'chat-'+key,'source':'chat','kind':'chat','split':split,'family':key,'upstream_source':row['source'],'messages':prompt,'expected_answer':chosen[-1]['content'],'episode':chosen})
  if all(counts[x]>={'train':10000,'dev':100,'test':200}[x] for x in counts) and len(counts)==3:break
 print('chat counts',dict(counts),flush=True)
 assert counts['train']>=3000 and counts['dev']>=40 and counts['test']>=80,counts
 for split in records:
  for i in range({'train':5000,'dev':50,'test':100}[split]):records[split].append(grounded_record(split,i))
  # Real unrelated chat prompts with tool schemas provide diverse no-tool cases.
  no_count=0
  for c in list(records[split]):
   if c['source']!='chat':continue
   question=c['messages'][-1]['content']
   if len(question.split())>35 or any(w in question.lower() for w in ['weather','calculate','convert','catalog','notes','search','stock','price']):continue
   ep=[msg('system',system()),msg('user',question),msg('assistant',c['expected_answer'])]
   if encode_episode(tok,ep) is None or len(tok.encode(render(ep[:-1],True)).ids)>416:continue
   records[split].append({'id':c['id']+'-no-tool','source':'tool','kind':'none','split':split,'family':c['family'],'messages':ep[:-1],'expected_answer':c['expected_answer'],'episode':ep});no_count+=1
   if no_count>={'train':1000,'dev':50,'test':100}[split]:break
  categories=({'single':5000,'chain':1000,'clarify':1000,'none':0,'error':1000} if split=='train' else {'single':100,'chain':50,'clarify':50,'none':0,'error':25} if split=='dev' else {'single':200,'chain':100,'clarify':100,'none':0,'error':50})
  for kind,n in categories.items():
   for i in range(n):records[split].append(tool_record(split,i,kind))
 arrays={};manifest={'counts':{},'source_receipt':json.loads((DATA/'raw/receipt.json').read_text()),'format':'existing role tokens; assistant-only targets including tool-call marker and EOS; one padded episode per 512-input row','limits':['Short diagnostic conversations, not all three-turn; no broad conversational accuracy claim.','Synthetic tool families use held-out wording and disjoint argument ranges/entities; clarify/no-tool linguistic diversity is small.','Tool outputs are local deterministic fixtures, never real weather or catalog data.','No human blind ratings yet; report proxy metrics separately.'],'seed':3901,'input_token_cap_per_arm':5000000,'mix_by_padded_input_tokens':{'chat':.4,'tool':.4,'grounded':.2}}
 hashes={};groupsplit={}
 for split,rr in records.items():
  kept=[];local=set()
  for rec in rr:
   encoded=encode_episode(tok,rec['episode'])
   if encoded is None or len(tok.encode(render(rec['messages'],True)).ids)>416:stats[split+'_too_long']+=1;continue
   # Common clarifications/no-tool messages are not counted as thousands of independent rows.
   h=digest(render(rec['episode']))
   if h in local:stats[split+'_duplicates']+=1;continue
   if h in hashes and hashes[h]!=split:raise AssertionError('Cross-split exact episode')
   local.add(h);hashes[h]=split;kept.append(rec)
  (DATA/f'{split}.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in kept))
  manifest['counts'][split]=dict(collections.Counter(r['source'] for r in kept));print(split,manifest['counts'][split],flush=True)
  encoded=[encode_episode(tok,r['episode']) for r in kept];arrays[split+'_ids']=np.stack([x[0] for x in encoded]);arrays[split+'_mask']=np.stack([x[1] for x in encoded]);arrays[split+'_length']=np.array([x[2] for x in encoded]);arrays[split+'_source']=np.array([['chat','tool','grounded'].index(r['source']) for r in kept])
 np.savez(DATA/'episodes.npz',**arrays)
 # Exact reproducible source-balanced stream, shared by all four runs.
 rng=np.random.default_rng(3901);pools={s:rng.permutation(np.flatnonzero(arrays['train_source']==s)).tolist() for s in range(3)};cursor={s:0 for s in pools};order=[]
 for i in range(10000):
  s=[0,1,0,1,2][i%5]
  if cursor[s]==len(pools[s]):pools[s]=rng.permutation(np.flatnonzero(arrays['train_source']==s)).tolist();cursor[s]=0
  order.append(pools[s][cursor[s]]);cursor[s]+=1
 np.save(DATA/'order.npy',np.array(order,np.int32))
 manifest.update(filter_counts=dict(stats),files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in DATA.iterdir() if p.is_file()},unique_scheduled_examples=len(set(order)),scheduled_rows=len(order),scheduled_source_counts=dict(collections.Counter(int(arrays['train_source'][i]) for i in order)))
 (DATA/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');shutil.copyfile(DATA/'manifest.json',REPORT/'data-manifest.json')
if __name__=='__main__':main()
