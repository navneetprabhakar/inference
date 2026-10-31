"""Prepare data only. V2 remains immutable. Never launches training/evaluation."""
import collections,json,hashlib,shutil
from pathlib import Path
import numpy as np
import pyarrow.parquet as pq
from tokenizers import Tokenizer
from sft_v3 import *
from prepare_continuation import Near,fingerprint
DATA=ROOT/'data/sft-v3';REPORT=ROOT/'reports/sft-v3'
CITY={'train':['Ahmedabad','Visakhapatnam','Thane','Vadodara','Coimbatore','Vijayawada','Jodhpur','Raipur','Gwalior','Kozhikode'],'dev':['Dehradun','Udaipur','Mangalore','Salem','Tirupati'],'test':['Aizawl','Itanagar','Gangtok','Kohima','Imphal']}
TOPIC={'train':['garden planting','roof repair','school pickup','music lesson','delivery reminder','research meeting','insurance renewal','weekly groceries','car servicing','fundraiser'],'dev':['swimming class','visa appointment','wedding arrangements','tax preparation','office move'],'test':['photography exhibition','camping supplies','dance rehearsal','water filter','cycling route']}
ALIASES={'train':['calc_value','length_convert','city_conditions','product_record','note_find'],'dev':['arithmetic_fn','length_scale','weather_read','inventory_fetch','notes_lookup'],'test':['operate_numbers','translate_length','read_conditions','fetch_product','retrieve_note']}
FAMILY_WORDS={'train':['Follow these instructions: ','Please help with this request: ','Use the appropriate tool: ','I need the following done: '],'dev':['Handle this request: ','Here is the task: '],'test':['Complete the following: ','Act on this instruction: ']}
def assigned(family):
 v=int(h(family)[:8],16)%100
 return 'train' if v<80 else 'dev' if v<90 else 'test'
def make_case(split,kind,i,variant=0):
 family=f'v3-{kind}-{i}';rng=np.random.default_rng(int(h(family)[:12],16));names=list(SCHEMAS)
 n=names[i%5];alias_forward=dict(zip(names,ALIASES[split])) if int(rng.integers(0,5))==0 else {};aliases={v:k for k,v in alias_forward.items()}
 def call(name,args):return {'name':alias_forward.get(name,name),'arguments':args}
 a=int(rng.integers(-999,1000));b=int(rng.integers(11,999));a=round(a/100,2) if i%3==0 else a;b=b+variant
 op=str(rng.choice(['add','subtract','multiply','divide']));u,v=rng.choice(['m','cm','km'],2,replace=False).tolist();city=str(rng.choice(CITY[split]));topic=str(rng.choice(TOPIC[split]));sku='SKU-'+str(int(rng.integers(10000,99999)))
 args={'calculate':{'op':op,'a':a,'b':b},'convert':{'value':a,'from_unit':u,'to_unit':v},'get_weather':{'city':city},'lookup_item':{'item_id':sku},'search_notes':{'query':topic}}[n]
 c=call(n,args);prefix=str(rng.choice(FAMILY_WORDS[split]));calls=[];results=[];accepted=None;extra={}
 def resolve(c):return execute({'name':aliases.get(c['name'],c['name']),'arguments':c['arguments']})
 question={'calculate':f'Apply {op} to first operand {a} and second operand {b}.','convert':f'Convert the length {a} {u} into {v}.','get_weather':f'Get the weather for {city}.','lookup_item':f'Look up price and stock for product {sku}.','search_notes':f'Search the saved notes for "{topic}".'}[n]
 required=[n]
 if kind in ['single','result']:
  calls=[c];r=resolve(c)
  # External fixture results are independent draws, not a learnable hash of the ID.
  if n=='get_weather':r={'city':city,'temperature_c':int(rng.integers(-15,45))+variant,'condition':str(rng.choice(['sunny','cloudy','rainy'])),'fixture':True}
  if n=='lookup_item':r={'item_id':sku,'price':int(rng.integers(10,900))+variant*7,'stock':int(rng.integers(0,75))+variant,'fixture':True}
  if n=='search_notes':r={'query':topic,'note':f'The {topic} appointment is at {int(rng.integers(1,12))+variant}:30.','fixture':True}
  results=[r]
 elif kind=='chain':
  route=i%4;required=['calculate','convert']
  if route==0:
   c1=call('convert',{'value':a,'from_unit':u,'to_unit':v});r1=resolve(c1);c2=call('calculate',{'op':op,'a':r1['result'],'b':b});question=f'Convert {a} {u} to {v}; then {op} that result and {b}, in that order.'
  elif route==1:
   c1=call('calculate',{'op':op,'a':a,'b':b});r1=resolve(c1);c2=call('convert',{'value':r1['result'],'from_unit':u,'to_unit':v});question=f'First {op} {a} and {b}. Treat the result as {u} and convert it to {v}.'
  elif route==2:
   c1=call('calculate',{'op':op,'a':a,'b':b});r1=resolve(c1);c2=call('calculate',{'op':'add','a':r1['result'],'b':17});question=f'First {op} {a} and {b}, then add 17 to that result.'
  else:
   c1=call('lookup_item',{'item_id':sku});r1={'item_id':sku,'price':int(rng.integers(10,900)),'stock':int(rng.integers(1,50)),'fixture':True};c2=call('calculate',{'op':'multiply','a':r1['price'],'b':b});question=f'Find the price of {sku}, then multiply that price by {b}.';required=['lookup_item','calculate']
  calls=[c1,c2];results=[r1,resolve(c2)];extra['route']=route
 elif kind=='clarify':
  choices={'calculate':['a','b','op'],'convert':['value','from_unit','to_unit'],'get_weather':['city'],'lookup_item':['item_id'],'search_notes':['query']};slot=choices[n][(i//5)%len(choices[n])]
  questions={'a':f'{op.capitalize()} an unspecified first number and {b}.','b':f'{op.capitalize()} {a} and an unspecified second number.','op':f'Use the calculator with {a} and {b}; I have not chosen the operation.','value':f'Convert a length from {u} to {v}; I have not supplied its value.','from_unit':f'Convert a length of {a} to {v}; the original unit is missing.','to_unit':f'Convert {a} {u}; I have not supplied the destination unit.','city':'Check the weather for my trip; I have not named the city.','item_id':'Check the inventory for a product; I have not supplied its ID.','query':'Search my notes; I have not supplied the search topic.'}
  question=questions[slot];accepted=SLOT_ANSWERS[slot];answer=accepted[i%len(accepted)];extra['missing_slot']=slot
  # Irrelevant context is shared across splits, never a split-specific reference ID.
  if i%3==0:question='Please keep the reply brief. '+question
 elif kind=='error':
  err=list(ERROR_ANSWERS)[i%5];n={'division by zero':'calculate','not found':'lookup_item','timeout':'get_weather','empty result':'search_notes','invalid unit':'convert'}[err];required=[n]
  args={'calculate':{'op':'divide','a':a,'b':0},'lookup_item':{'item_id':sku},'get_weather':{'city':city},'search_notes':{'query':topic},'convert':{'value':a,'from_unit':'m','to_unit':'yard'}}[n];c=call(n,args);extra.update(error_kind=err,provided_result={'error':err},provided_call=c);question=f'I requested {alias_forward.get(n,n)} with {json.dumps(args,separators=(",",":"))}. Explain the tool response and the next step.';answer=ERROR_ANSWERS[err]
 elif kind=='none':
  question={'calculate':'Explain what addition means; do not calculate specific numbers.','convert':'Explain why people convert measurement units; no conversion is needed.','get_weather':'Explain what a weather forecast is; I do not need current weather.','lookup_item':'Explain what stock quantity means; do not look up a product.','search_notes':'Explain what a search query is; do not search my notes.'}[n]
  answer={'calculate':'Addition combines numbers to find their total.','convert':'Unit conversion expresses the same measurement using a different unit.','get_weather':'A weather forecast predicts future atmospheric conditions.','lookup_item':'Stock quantity is the number of units available for an item.','search_notes':'A search query describes the information you want to find.'}[n]
 else:raise ValueError(kind)
 extras=[x for x in rng.permutation(names).tolist() if x not in required];offered=required+extras[:max(0,3-len(required))];rng.shuffle(offered)
 rec={'id':family+f'-v{variant}','family':family,'split':split,'kind':kind,'source':'tool','objective':'final_assistant_only' if kind in ['result','error'] else 'assistant_only','aliases':aliases,'available_tools':[alias_forward.get(x,x) for x in offered],**extra}
 messages=[msg('system',schema_prompt(alias_forward,offered)),msg('user',prefix+question)]
 if kind=='error':messages += [msg('assistant',call_text(c)),msg('tool',json.dumps(extra['provided_result'],separators=(',',':')))]
 if calls:
  answer=answer_for(rec,calls[-1],results[-1])
  if kind=='result':
   messages += [msg('assistant',call_text(calls[0])),msg('tool',json.dumps(results[0],separators=(',',':')))];rec.update(provided_call=calls[0],provided_result=results[0]);calls=[];results=[]
 rec.update(messages=messages,calls=calls,results=results,expected_answer=answer,accepted_answers=accepted or [answer])
 episode=list(messages)
 for c,r in zip(calls,results):episode += [msg('assistant',call_text(c)),msg('tool',json.dumps(r,separators=(',',':')))]
 rec['episode']=episode+[msg('assistant',answer)]
 return rec

def grounded(split,i):
 family=f'v3-grounded-{i}';rng=np.random.default_rng(int(h(family)[:12],16));name=str(rng.choice(['Mira','Kabir','Zoya','Arun','Tara','Isha']));old=str(rng.choice(CITY[split]));new=str(rng.choice([c for c in CITY[split] if c!=old]));job=str(rng.choice(['dentist','farmer','pilot','plumber','writer']));unknown=i%4==0;answer='The context does not say.' if unknown else new
 first=f'{name} works as a {job} and used to live in {old}. {name} now lives in {new}.';question=f'How old is {name}?' if unknown else f'Where does {name} live now?'
 if i%2:messages=[msg('system','Use only the context; if missing, answer "The context does not say."'),msg('user',first+' '+question)]
 else:messages=[msg('system','Use only the conversation facts; if missing, answer "The context does not say."'),msg('user',f'{name} lives in {old}.'),msg('assistant',f'{name} lives in {old}.'),msg('user',f'Update: {name} moved to {new}. '+question)]
 return {'id':family,'family':family,'split':split,'kind':'grounded','source':'grounded','objective':'assistant_only','messages':messages,'expected_answer':answer,'accepted_answers':[answer],'episode':messages+[msg('assistant',answer)]}

def main():
 assert not (DATA/'manifest.json').exists(),'Frozen data exists; version instead of overwriting'
 tok=Tokenizer.from_file(str(ROOT/'data/sft-v2/tokenizer.json'));shutil.copyfile(ROOT/'data/sft-v2/tokenizer.json',DATA/'tokenizer.json')
 records={x:[] for x in ['train','dev','test']};counts=collections.Counter();seen=set();families={};near=Near();old_families=set();old_episodes=set()
 for split in records:
  for line in (ROOT/f'data/sft-v2/{split}.jsonl').read_text().splitlines():
   r=json.loads(line);old_episodes.add(h(render(r['episode'])))
   if r['source']=='chat':
    old_families.add(r['family']);near.add(fingerprint(next(m['content'] for m in r['episode'] if m['role']=='user')))
 # Explicitly reuse only old TRAIN chat records; old dev/test are never trained.
 oldtrain=[json.loads(x) for x in (ROOT/'data/sft-v2/train.jsonl').read_text().splitlines()]
 for r in oldtrain:
  if r['source']!='chat':continue
  text=render(r['episode']).lower()
  if any(w in text for w in ['roleplay','role-play','movie star','you will be a','pretend','character now']):continue
  r={**r,'objective':'assistant_only','provenance':'sft-v2 train only; upstream pinned smol-smoltalk'};records['train'].append(r)
  if len(records['train'])>=5000:break
 # Fresh public chat families, excluded against all v2 chat and near duplicates.
 for batch in pq.ParquetFile(DATA/'raw/smol-smoltalk-1.parquet').iter_batches(batch_size=256):
  for row in batch.to_pylist():
   if row['source'] not in ['smol-magpie-ultra-short','everyday-conversations','smol-contraints']:continue
   ms=row['messages'];users=[m['content'] for m in ms if m['role']=='user']
   if not users:continue
   family=h(' '.join(users[0].casefold().split()))
   if family in old_families or family in families or near.contains(fingerprint(users[0])):continue
   split='dev' if int(family[:8],16)%2==0 else 'test'
   if counts['chat-'+split]>=100:continue
   chosen=[]
   for m in ms:
    if m['role'] not in ['system','user','assistant']:break
    if m['role']=='assistant' and encode_episode(tok,chosen+[m]) is None:break
    chosen.append(m)
   while chosen and chosen[-1]['role']!='assistant':chosen.pop()
   if len(chosen)<2:continue
   text=render(chosen)
   if any(w in text.lower() for w in ['```','roleplay','role-play','movie star','you will be a','pretend','character now','sexual']):continue
   letters=[c for c in text if c.isalpha()]
   if not letters or sum(c.isascii() for c in letters)/len(letters)<.98:continue
   if any(len(m['content'].split())>100 for m in chosen if m['role']=='assistant'):continue
   if encode_episode(tok,chosen) is None or len(tok.encode(render(chosen[:-1],True)).ids)>416:continue
   families[family]=split;near.add(fingerprint(users[0]));counts['chat-'+split]+=1
   records[split].append({'id':'fresh-chat-'+family,'family':family,'split':split,'kind':'chat','source':'chat','objective':'assistant_only','messages':chosen[:-1],'expected_answer':chosen[-1]['content'],'episode':chosen,'upstream_source':row['source'],'provenance':'unused local pinned smol-smoltalk shard; automated filtering, not human rated'})
  if counts['chat-dev']==100 and counts['chat-test']==100:break
 assert counts['chat-dev']==100 and counts['chat-test']==100,counts
 print('chat prepared',dict(counts),flush=True)
 quotas={'train':{'single':3000,'result':2500,'chain':2500,'clarify':1500,'error':500,'none':500,'grounded':2000},'dev':{'single':100,'result':75,'chain':75,'clarify':75,'error':50,'none':25,'grounded':50},'test':{'single':200,'result':150,'chain':150,'clarify':150,'error':100,'none':50,'grounded':100}}
 local={s:set() for s in records};filter_counts=collections.Counter()
 for split in records:
  for kind,n in quotas[split].items():
   kept=0;i=0
   while kept<n:
    family=f'v3-{kind}-{i}'
    if assigned(family)!=split:i+=1;continue
    variants=[0,1] if kind in ['single','result'] else [0]
    for variant in variants:
     r=grounded(split,i) if kind=='grounded' else make_case(split,kind,i,variant)
     encoded=encode_record(tok,r);text=render(r['episode']);key=h(text)
     if encoded is None or len(tok.encode(render(r['messages'],True)).ids)>416:filter_counts[split+'-length']+=1;continue
     if key in local[split] or key in old_episodes:filter_counts[split+'-duplicate']+=1;continue
     # IDs are not exposed to the model. Paired contrastive/counterfactual cases stay together.
     local[split].add(key);records[split].append(r);kept+=1
     if kept==n:break
    i+=1
    assert i<200000,(split,kind,kept)
   print(split,kind,kept,flush=True)
 # Replay comes only from old TRAIN streams. Preserve existing tokenizer IDs and full-LM mask.
 for source in ['fineweb','tinystories']:
  path=ROOT/f'data/pilot-v1/{source}-train.bin';arr=np.memmap(path,dtype=np.uint16,mode='r');rng=np.random.default_rng(7831 if source=='fineweb' else 7832)
  for j,block in enumerate(rng.choice((len(arr)-1)//512,1500,replace=False)):
   tokens=np.asarray(arr[int(block)*512:int(block)*512+513],dtype=np.int32).tolist();records['train'].append({'id':f'replay-{source}-{block}','family':f'replay-{source}-{block}','split':'train','source':'replay','kind':'replay','objective':'causal_lm','tokens':tokens,'provenance':{'path':str(path),'block':int(block),'previous_split':'train'}})
 arrays={};source_ids={'chat':0,'tool':1,'grounded':2,'replay':3}
 for split,rr in records.items():
  (DATA/f'{split}.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rr));enc=[encode_record(tok,r) for r in rr]
  for suffix,value in [('ids',np.stack([x[0] for x in enc])),('mask',np.stack([x[1] for x in enc])),('length',np.array([x[2] for x in enc])),('source',np.array([source_ids[r['source']] for r in rr]))]:arrays[split+'_'+suffix]=value
 np.savez(DATA/'episodes.npz',**arrays)
 # Balance by real input tokens, not padded rows. Pair adjacent lengths inside small windows.
 rng=np.random.default_rng(77123);pools={s:rng.permutation(np.flatnonzero(arrays['train_source']==s)).tolist() for s in range(4)};positions={s:0 for s in pools};exposure={s:0 for s in pools};weights={0:.25,1:.5,2:.1,3:.15};order=[]
 for _ in range(50000):
  source=min(exposure,key=lambda s:exposure[s]/weights[s]);pool=pools[source]
  if positions[source]==len(pool):rng.shuffle(pool);positions[source]=0
  ix=pool[positions[source]];positions[source]+=1;order.append(ix);exposure[source]+=int(arrays['train_length'][ix])-1
 order=[i for k in range(0,len(order),100) for i in sorted(order[k:k+100],key=lambda i:int(arrays['train_length'][i]))];np.save(DATA/'order.npy',np.array(order,np.int32))
 manifest={'version':'sft-v3','status':'prepared_not_authorized_for_training','sources':source_ids,'counts':{s:dict(collections.Counter(r['kind'] for r in rr)) for s,rr in records.items()},'mix_by_nonpadding_input_tokens':{'chat':.25,'tool':.5,'grounded':.1,'replay':.15},'format':'independent episodes, dynamic pair trimming; assistant-only loss; final-answer-only for provided result/error histories; full-LM replay','filter_counts':dict(filter_counts),'upstream_receipts':[json.loads((ROOT/'data/sft-v2/raw/receipt.json').read_text()),json.loads((DATA/'raw/receipt.json').read_text())],'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in DATA.iterdir() if p.is_file()},'seed':77123,'fresh_test_status':'1000 cases; no model scored on this set','limitations':['Synthetic tools remain local fixtures, not real external services.','Fresh chat is automatically filtered public data, not human quality-rated.','Existing v2 TRAIN chat is intentionally reused; held-out chat families are excluded.','Family hashes keep counterfactual variants together; template-correlated examples are not independent natural tasks.','Full-LM replay uses old training streams; it is intentional repetition.','Existing v2 runner stays pinned to v2. A future v3 trainer configuration is required; nothing starts automatically.']}
 (DATA/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');shutil.copyfile(DATA/'manifest.json',REPORT/'data-manifest.json');print('Prepared',manifest['counts'],flush=True)
if __name__=='__main__':main()
