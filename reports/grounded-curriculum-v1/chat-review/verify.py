"""Independent exhaustive finite-domain candidate verification; CPU only.

No imports from chat builder, renderer, author semantic interpreter, or row helper.
"""
import os
for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'):os.environ[key]='1'
os.environ['TOKENIZERS_PARALLELISM']='false'
import collections,hashlib,json,pathlib,re,resource,shutil,sqlite3,sys,time
HERE=pathlib.Path(__file__).resolve().parent;ROOT=HERE.parents[2];sys.path.insert(0,str(ROOT))
from independent_semantics import fill,interpret,validate_task
from tokenizer import load,EOT
from own_base_chat import policy_text
DATA=ROOT/'data/grounded-chat-candidates-v1'
OBJECTS=('portable loom','ceramic mold','survey instrument','sewing machine','folding easel','display frame','sample carrier','measuring fixture','projection screen','shipping case','woven basket','spare bracket','timing device','wax sculpture','folding platform','printed chart')
SYLLABLES=('ba','de','fi','go','hu','ja','ke','lo','mi','nu','pa','re','si','to','vu','za')
CAPS={'fulfillment':(135000,15000),'facts':(108000,12000),'corrections':(81000,9000),'transformations':(81000,9000),'clarification':(81000,9000),'recall':(54000,6000)}
SEED='forge-grounded-chat-v1-20261108'
def canon(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)
def digest(text):return hashlib.sha256(text.encode()).hexdigest()
def sha(path):
 h=hashlib.sha256()
 with pathlib.Path(path).open('rb') as f:
  for chunk in iter(lambda:f.read(1024**2),b''):h.update(chunk)
 return h.hexdigest()
def read(path):return json.loads(pathlib.Path(path).read_text())
def normalized(text):return re.sub(r'\s+',' ',text.casefold()).strip()
def check(start):
 if time.monotonic()-start>1200:raise RuntimeError('independent verifier wall cap')
 if any(p.exists() for p in (ROOT/'runs/STOP',ROOT/'runs/own-base-foundation-01/STOP',DATA/'STOP')):raise RuntimeError('STOP')
 rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
 if rss>512*1024**2 or shutil.disk_usage(ROOT).free<20*1024**3:raise RuntimeError('resource cap')
def slots_for(surface,index):
 raw=hashlib.sha256(f"{SEED}|{surface['split']}|{surface['id']}|{index}".encode()).digest()
 def name(start):return ''.join(SYLLABLES[raw[i%32]%16] for i in range(start,start+3)).capitalize()
 slots={key:name(start) for key,start in zip(('person','other','thirdperson'),(0,3,6))}
 slots.update({key:name(start)+' facility' for key,start in zip(('place','alternate','third'),(9,12,15))})
 slots['item']=name(18)+' '+OBJECTS[raw[21]%16];slots['thing']=name(22)+' '+OBJECTS[raw[25]%16]
 lower,span=(10001,289999) if surface['split']=='train' else (700001,300000)
 slots['n']=str(lower+int.from_bytes(raw[26:29],'big')%span);slots['m']=str(lower+int.from_bytes(raw[29:32],'big')%span)
 slots['code']=name(1)+' '+name(10)
 for names in (('person','other','thirdperson'),('place','alternate','third'),('item','thing'),('n','m')):
  if len({slots[n] for n in names})!=len(names):raise ValueError('distinctness')
 return slots

def framing(tok,history):
 """Reconstruct the raw framing and current-turn mask without training helpers."""
 raw=[];bodies=[];prefixes=[];metrics=[];exposure=collections.Counter({f'{i}..{i+255}':0 for i in range(0,1024,256)})
 messages=[dict(role='system',text=policy_text())]+history
 for mi,msg in enumerate(messages):
  role=msg['role'];header=tok.encode('['+role+']\n').ids
  body=tok.encode(canon({'text':msg['text']}).replace('<','\\u003c').replace('>','\\u003e')).ids+[EOT]
  if EOT in body[:-1]:raise ValueError('untrusted terminator')
  if role=='assistant':
   prompt=len(raw)+len(header)
   if prompt+256>1024:raise ValueError('framing')
   if len(body)>128 or len(tok.encode(msg['text']).ids)>96:raise ValueError('answer_length')
   inputs=prompt+len(body)-1
   if not 0<inputs<=1024:raise ValueError('framing')
   # Only this current response body/EOT is supervised in this prefix row.
   for pos in range(prompt,prompt+len(body)):
    if pos>=1024:raise ValueError('target position outside frozen context')
    exposure[f'{(pos//256)*256}..{(pos//256)*256+255}']+=1
   metrics.append(dict(inputs=inputs,targets=len(body),prompt=prompt))
  raw+=header+body
 assert len(metrics)==2
 return dict(input_tokens=sum(x['inputs'] for x in metrics),target_tokens=sum(x['targets'] for x in metrics),generation_max=max(x['targets'] for x in metrics),rows=2,position_exposure=dict(exposure))

def verify():
 start=time.monotonic();check(start);review=read(HERE/'reviewed-registry.json');policy=read(DATA/'policy.json');manifest=read(DATA/'partial-candidate-manifest.json')
 assert manifest['state']=='candidate_only_not_admitted' and manifest['failure'] is None and manifest['semantics_verified'] is False and manifest['training_admitted'] is False
 assert policy['seed']==SEED and policy['families']==review['surfaces']
 assert policy['group_target_caps']=={k:list(v) for k,v in CAPS.items()}
 assert policy['proposals_per_surface']=={'train':512,'validation':128}
 assert policy['train_target_cap']==540000 and policy['validation_target_cap']==60000
 for path,expected in policy['code_and_protocol'].items():assert sha(ROOT/path)==expected,path
 for filename,expected in review['source_pins'].items():assert sha(HERE.parent/'chat'/filename)==expected
 assert manifest['code_and_protocol']==policy['code_and_protocol'] and manifest['policy_sha256']==sha(DATA/'policy.json')
 assert manifest['surface_inventory_sha256']==sha(DATA/'surface-inventory.md')
 dbpath=DATA/'candidates.sqlite';dbsha=sha(dbpath);assert manifest['database']['sha256']==dbsha and manifest['database']['bytes']==dbpath.stat().st_size
 sourcepath=DATA/'source-records.jsonl';rawsha=sha(sourcepath)
 assert manifest['source_files']==[dict(path=str(sourcepath),sha256=rawsha,bytes=sourcepath.stat().st_size)]
 assert manifest['refusals']['sha256']==sha(DATA/'refused.jsonl')
 con=sqlite3.connect(f'file:{dbpath}?mode=ro',uri=True);con.row_factory=sqlite3.Row;con.execute('PRAGMA cache_size=-2048')
 assert con.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
 total=con.execute('SELECT count(*) FROM documents').fetchone()[0]
 assert total==con.execute('SELECT count(*) FROM tasks').fetchone()[0]==manifest['verified_rows']
 assert con.execute('SELECT count(*) FROM tasks LEFT JOIN documents USING(doc_id) WHERE documents.doc_id IS NULL').fetchone()[0]==0
 refusals={}
 for line in (DATA/'refused.jsonl').read_text().splitlines():
  record=json.loads(line);key=(record['family'],record['index']);assert key not in refusals;refusals[key]=record
 tok=load();seen_norm=set();seen_ids=set();expected_refusals=set();totals=collections.Counter();aggregate=collections.defaultdict(collections.Counter);global_exposure=collections.Counter();bysurface={};family_splits={};surface_seen=set();forms_seen=set();lengths=[];phrases=collections.Counter();samples={};row_index=0
 with sourcepath.open() as raw:
  for surface in review['surfaces']:
   sp=surface['split'];group=surface['group'];cf=surface['canonical_family'];family_splits.setdefault(cf,set()).add(sp)
   peers=[s for s in review['surfaces'] if s['group']==group and s['split']==sp]
   cap=(CAPS[group][sp=='validation']//len({s['canonical_family'] for s in peers}))//sum(s['canonical_family']==cf for s in peers)
   used=0;c=collections.Counter();bysurface[surface['id']]=c
   queue=sorted(range(512 if sp=='train' else 128),key=lambda i:digest(f"{SEED}|{surface['id']}|{i}"))
   for index in queue:
    if (row_index+c['attempted'])%32==0:check(start)
    c['attempted']+=1;key=(surface['id'],index)
    try:slots=slots_for(surface,index)
    except ValueError:
     expected_refusals.add(key);c['refused']+=1;continue
    form=index%len(surface['first_user_forms']);history=[]
    for turn in range(2):
     history.append(dict(role='user',text=fill(surface['first_user_forms'][form] if turn==0 else surface['turns'][turn]['user'],slots)))
     history.append(dict(role='assistant',text=fill(surface['turns'][turn]['assistant'],slots)))
    try:metrics=framing(tok,history)
    except ValueError:
     expected_refusals.add(key);c['refused']+=1;continue
    if used+metrics['target_tokens']>cap:c['stopped_at_target_cap']=1;break
    norm=digest('\n'.join(m['role']+': '+normalized(m['text']) for m in history))
    if norm in seen_norm:expected_refusals.add(key);c['refused']+=1;continue
    program=fill(review['programs'][surface['id']],slots)
    expected=dict(schema=1,family=cf,surface_id=surface['id'],first_user_form=form,semantic_state=dict(program=program,snapshots=interpret(program)),group=group,split=sp,construction=surface['state_kind'],instance=index,state=slots,requirements=surface['requirements'],history=history)
    line=raw.readline();assert line,'missing raw source history'
    task=json.loads(line);assert task==expected,'independent expected task mismatch'
    assert line==canon(task)+'\n';did=digest(canon(task));assert did not in seen_ids
    validate_task(task,surface,review['programs'][surface['id']])
    doc=con.execute('SELECT * FROM documents WHERE doc_id=?',(did,)).fetchone();assert doc is not None
    stored=con.execute('SELECT task_json FROM tasks WHERE doc_id=?',(did,)).fetchone()[0];assert stored==canon(task)
    full='\n'.join(m['role'].capitalize()+': '+m['text'] for m in history)
    expected_doc=dict(doc_id=did,text=full,selected_history_json=canon(history),source='grounded_chat/'+group,raw_sha256=rawsha,raw_path=str(sourcepath),row_index=row_index,family=cf,split=sp,input_tokens=metrics['input_tokens'],target_tokens=metrics['target_tokens'],generation_max=metrics['generation_max'],normalized_sha256=norm,parent_normalized_sha256=digest(normalized(full)),whole=1,has_system=0,selected_messages=4)
    assert dict(doc)==expected_doc,'document/index/source mismatch'
    seen_ids.add(did);seen_norm.add(norm);surface_seen.add(surface['id']);forms_seen.add((surface['id'],form));row_index+=1
    used+=metrics['target_tokens'];c['accepted']+=1;c['targets']+=metrics['target_tokens'];c['input_tokens']+=metrics['input_tokens'];c['rows']+=2
    global_exposure.update(metrics['position_exposure']);totals[sp+'_targets']+=metrics['target_tokens']
    ag=aggregate[('grounded_chat/'+group,sp)];ag['histories']+=1;ag['rows']+=2;ag['input_tokens']+=metrics['input_tokens'];ag['target_tokens']+=metrics['target_tokens']
    for message in history[1::2]:lengths.append(len(tok.encode(message['text']).ids));phrases[' '.join(message['text'].casefold().split()[:4])]+=1
    samplekey=(surface['id'],form)
    sample=dict(doc_id=did,surface_id=surface['id'],first_user_form=form,split=sp,history=history)
    if samplekey not in samples or digest(did)<digest(samples[samplekey]['doc_id']):samples[samplekey]=sample
   c['cap']=cap
  assert not raw.readline(),'unexpected unselected raw histories'
 assert expected_refusals==set(refusals)
 for surface,index in expected_refusals:
  assert refusals[(surface,index)]['split']==next(s['split'] for s in review['surfaces'] if s['id']==surface)
 assert row_index==total and len(seen_ids)==total and dict(totals)==manifest['counts']
 assert {k:dict(v) for k,v in bysurface.items()}==manifest['by_surface']
 assert dict(global_exposure)==manifest['position_exposure']
 assert totals['train_targets']<=540000 and totals['validation_targets']<=60000
 assert len(surface_seen)==66 and len(forms_seen)==108
 assert all(len(splits)==1 for splits in family_splits.values())
 assert {sp:sum(splits=={sp} for splits in family_splits.values()) for sp in ('train','validation')}==review['canonical_counts']
 for expected in manifest['aggregates']:
  actual=aggregate[(expected['source'],expected['split'])]
  assert all(actual[k]==expected[k] for k in actual)
  families=con.execute('SELECT count(distinct family) FROM documents WHERE source=? AND split=?',(expected['source'],expected['split'])).fetchone()[0]
  assert families==expected['families']
 assert len(aggregate)==len(manifest['aggregates'])==12
 for path,expected in policy['code_and_protocol'].items():assert sha(ROOT/path)==expected
 assert sha(dbpath)==dbsha;check(start)
 samplepath=HERE/'generated-stratified-samples.jsonl'
 with samplepath.open('x') as f:
  for key in sorted(samples):f.write(canon(samples[key])+'\n')
 detail=dict(state='PASS_finite_domain_instance_checks_pending_sample_review',histories=total,targets=dict(totals),canonical_counts=review['canonical_counts'],surfaces=66,first_user_forms=108,refused=len(refusals),target_position_exposure=dict(global_exposure),answer_lengths=dict(min=min(lengths),max=max(lengths),median=sorted(lengths)[len(lengths)//2]),top_four_word_prefixes=phrases.most_common(20),samples_sha256=sha(samplepath),seconds=time.monotonic()-start,limitations=review['limitations'])
 with (HERE/'exhaustive-result.json').open('x') as f:json.dump(detail,f,indent=2);f.write('\n')
 # Deliberately no custody-compatible PASS until reviewer finishes the fixed sample.
 print(json.dumps(detail,indent=2))
if __name__=='__main__':
 os.nice(10)
 try:verify()
 except Exception as error:
  with (HERE/'verification-failure.json').open('x') as f:json.dump(dict(state='FAIL',error_type=type(error).__name__,error=str(error)),f,indent=2)
  raise
