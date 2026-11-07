"""Bounded CHAT candidate preparation only. No custody, admission or final streams."""
import os
for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):os.environ[key]='1'
os.environ['TOKENIZERS_PARALLELISM']='false'
import argparse,collections,hashlib,json,pathlib,re,resource,shutil,sqlite3,sys,time
HERE=pathlib.Path(__file__).resolve().parent;ROOT=HERE.parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(HERE))
from surfaces import FAMILIES
from semantics import SPECS,instantiate
from own_base_chat_rows import build_chat_rows
from tokenizer import load,ASSETS
SEED='forge-grounded-chat-v1-20261108'
DATA=ROOT/'data/grounded-chat-candidates-v1'
GROUPS={'fulfillment':(135000,15000),'facts':(108000,12000),'corrections':(81000,9000),'transformations':(81000,9000),'clarification':(81000,9000),'recall':(54000,6000)}
LIMITS=dict(seconds=1200,rss_bytes=512*1024**2,output_bytes=256*1024**2,min_free_bytes=20*1024**3)
REQUIRED=('surfaces.py','semantics.py','build.py','PROTOCOL.md','VERIFY-CONTRACT.md')
HELPERS=('own_base_chat_rows.py','own_base_sft_rows.py','own_base_chat.py','dialogue.py','tokenizer.py','tools/__init__.py','data/tokenizer/encoder.json','data/tokenizer/vocab.bpe')
OBJECTS=('portable loom','ceramic mold','survey instrument','sewing machine','folding easel','display frame','sample carrier','measuring fixture','projection screen','shipping case','woven basket','spare bracket','timing device','wax sculpture','folding platform','printed chart')
SYLLABLES=('ba','de','fi','go','hu','ja','ke','lo','mi','nu','pa','re','si','to','vu','za')
def canonical(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)
def sh(x):return hashlib.sha256(x.encode()).hexdigest()
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(1024**2),b''):h.update(b)
 return h.hexdigest()
def write(path,x):
 with path.open('x') as f:f.write(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def normalize(x):return re.sub(r'\s+',' ',x.casefold()).strip()
def pins():return {str(p.relative_to(ROOT)):sha(p) for p in [*(HERE/x for x in REQUIRED),*(ROOT/x for x in HELPERS)]}
def freeze():
 DATA.mkdir(exist_ok=False)
 policy=dict(schema=1,state='prospectively_frozen_before_instances',seed=SEED,families=FAMILIES,semantic_programs=SPECS,group_target_caps=GROUPS,train_target_cap=540000,validation_target_cap=60000,proposals_per_surface=dict(train=512,validation=128),selection='Each group/split cap is divided by distinct canonical families in that group/split, then by surfaces of that canonical family in that group/split (floor at both stages). Stable SHA256(seed|surface_id|index) order. Whole histories only; stop a surface at first non-fitting target-cap row. No adaptive refill, cycling or post-custody regeneration.',typed_state_schema={'person':'fresh synthesized name','other':'distinct fresh synthesized name','thirdperson':'distinct fresh synthesized name','place':'fresh named facility','alternate':'distinct fresh named facility','third':'distinct fresh named facility','item':'fresh named object','thing':'distinct fresh named object','n':'lookup identifier, train10001..299999, validation700001..999999','m':'distinct lookup identifier in same split range','code':'fresh phrase, not an authentication credential'},limits=LIMITS,code_and_protocol=pins(),tokenizer=ASSETS,training_admitted=False,private_cases_read=False)
 write(DATA/'policy.json',policy)
 lines=['# Frozen chat construction and surface inventory','',f'Seed: `{SEED}`. 54 training surfaces in 37 canonical families; 12 new-development surfaces in 12 canonical families. No instances existed at freeze.','']
 for f in FAMILIES:
  lines += [f"## {f['id']} ({f['split']})",'',f"Canonical family: `{f['canonical_family']}`. Typed task: `{f['state_kind']}`. Requirements: "+'; '.join(f['requirements']), '']
  for alternate in f['first_user_forms'][1:]:lines += [f'Alternative first user: {alternate}', '']
  for i,t in enumerate(f['turns']):lines += [f"User {i+1}: {t['user']}",f"Assistant {i+1}: {t['assistant']}",'']
 (DATA/'surface-inventory.md').write_text('\n'.join(lines)+'\n')
 print(canonical({'state':policy['state'],'policy_sha256':sha(DATA/'policy.json'),'families':len(FAMILIES)}))
def state(f,index):
 # Seed/split/family identity are included before all value generation. No corpus read.
 digest=hashlib.sha256(f"{SEED}|{f['split']}|{f['id']}|{index}".encode()).digest()
 def name(offset):return ''.join(SYLLABLES[digest[(offset+i)%32]%len(SYLLABLES)] for i in range(3)).capitalize()
 people=[name(i) for i in (0,3,6)];places=[name(i)+' facility' for i in (9,12,15)]
 objects=[name(18)+' '+OBJECTS[digest[21]%len(OBJECTS)],name(22)+' '+OBJECTS[digest[25]%len(OBJECTS)]]
 lo,span=(10001,289999) if f['split']=='train' else (700001,300000)
 n=lo+int.from_bytes(digest[26:29],'big')%span;m=lo+int.from_bytes(digest[29:32],'big')%span
 result=dict(zip(('person','other','thirdperson'),people))|dict(zip(('place','alternate','third'),places))|dict(zip(('item','thing'),objects))|dict(n=str(n),m=str(m),code=name(1)+' '+name(10))
 if len(set(people))<3 or len(set(places))<3 or objects[0]==objects[1] or n==m:raise ValueError('non-distinct state values')
 return result

def main():
 os.nice(10);started=time.monotonic();policy=json.loads((DATA/'policy.json').read_text())
 if policy['code_and_protocol']!=pins() or policy['families']!=FAMILIES or policy['semantic_programs']!=SPECS or policy['seed']!=SEED:raise ValueError('prospective identity changed')
 if (DATA/'candidates.sqlite').exists():raise FileExistsError('no overwrite/retry')
 def check():
  if time.monotonic()-started>LIMITS['seconds']:raise RuntimeError('wall cap')
  if any(p.exists() for p in (ROOT/'runs/STOP',ROOT/'runs/own-base-foundation-01/STOP',DATA/'STOP')):raise RuntimeError('STOP')
  rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
  if rss>LIMITS['rss_bytes'] or shutil.disk_usage(ROOT).free<LIMITS['min_free_bytes']:raise RuntimeError('resource cap')
  if sum(p.stat().st_size for p in DATA.iterdir() if p.is_file())>LIMITS['output_bytes']:raise RuntimeError('output cap')
 check();tok=load();db=sqlite3.connect(DATA/'candidates.sqlite');db.execute('pragma synchronous=FULL');db.execute('pragma journal_mode=DELETE');db.execute('pragma cache_size=-2048')
 db.execute('CREATE TABLE documents(doc_id TEXT PRIMARY KEY,text TEXT NOT NULL,selected_history_json TEXT NOT NULL,source TEXT NOT NULL,raw_sha256 TEXT NOT NULL,raw_path TEXT NOT NULL,row_index INTEGER NOT NULL,family TEXT NOT NULL,split TEXT NOT NULL,input_tokens INTEGER NOT NULL,target_tokens INTEGER NOT NULL,generation_max INTEGER NOT NULL,normalized_sha256 TEXT NOT NULL UNIQUE,parent_normalized_sha256 TEXT NOT NULL,whole INTEGER NOT NULL,has_system INTEGER NOT NULL,selected_messages INTEGER NOT NULL)')
 db.execute('CREATE TABLE tasks(doc_id TEXT PRIMARY KEY,task_json TEXT NOT NULL,FOREIGN KEY(doc_id) REFERENCES documents(doc_id))')
 counts=collections.Counter();bysurface={};exposure=collections.Counter();sourcepath=DATA/'source-records.jsonl';refused=DATA/'refused.jsonl';rowindex=0
 failure=None
 try:
  with sourcepath.open('x') as raw,refused.open('x') as refusals:
   for f in FAMILIES:
    check();sp=f['split'];group=f['group'];peers=[x for x in FAMILIES if x['split']==sp and x['group']==group];nf=len({x['canonical_family'] for x in peers});ns=sum(x['canonical_family']==f['canonical_family'] for x in peers);cap=(GROUPS[group][sp=='validation']//nf)//ns;used=0;c=collections.Counter();bysurface[f['id']]=c
    indices=sorted(range(policy['proposals_per_surface'][sp]),key=lambda i:sh(f"{SEED}|{f['id']}|{i}"))
    for index in indices:
     check();c['attempted']+=1
     try:
      slots=state(f,index);history=[]
      form=index%len(f['first_user_forms'])
      for turn,t in enumerate(f['turns']):history.extend([dict(role='user',text=(f['first_user_forms'][form] if turn==0 else t['user']).format(**slots)),dict(role='assistant',text=t['assistant'].format(**slots))])
      if any(len(tok.encode(t['text']).ids)>96 for t in history if t['role']=='assistant'):raise ValueError('prose answer exceeds96tokens')
      aligned=build_chat_rows(tok,history);targets=sum(r.target_count for r in aligned['rows']);inputs=sum(len(r.inputs) for r in aligned['rows']);generation_max=max(r.target_count for r in aligned['rows'])
      if generation_max>128:raise ValueError('assistant frame exceeds128tokens')
      if used+targets>cap:c['stopped_at_target_cap']=1;break
      task=dict(schema=1,family=f['canonical_family'],surface_id=f['id'],first_user_form=form,semantic_state=instantiate(f['id'],slots),group=group,split=sp,construction=f['state_kind'],instance=index,state=slots,requirements=f['requirements'],history=history)
      line=canonical(task);did=sh(line);full='\n'.join(m['role'].capitalize()+': '+m['text'] for m in history);norm=sh('\n'.join(m['role']+': '+normalize(m['text']) for m in history));parentnorm=sh(normalize(full))
      db.execute('INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(did,full,canonical(history),'grounded_chat/'+group,'pending',str(sourcepath),rowindex,f['canonical_family'],sp,inputs,targets,generation_max,norm,parentnorm,1,0,len(history)))
      db.execute('INSERT INTO tasks VALUES (?,?)',(did,line));raw.write(line+'\n');rowindex+=1;used+=targets;c['accepted']+=1;c['targets']+=targets;c['input_tokens']+=inputs;c['rows']+=len(aligned['rows']);exposure.update(aligned['position_exposure'])
     except (ValueError,sqlite3.IntegrityError) as error:
      c['refused']+=1;refusals.write(canonical(dict(family=f['id'],split=sp,index=index,reason=str(error)))+'\n')
     if rowindex%32==0:db.commit()
    c['cap']=cap;counts[sp+'_targets']+=used
   db.commit()
  check();rawsha=sha(sourcepath);db.execute('UPDATE documents SET raw_sha256=?',(rawsha,));db.commit()
  assert db.execute('pragma integrity_check').fetchone()[0]=='ok'
  assert db.execute('select count(*) from (select family from documents group by family having count(distinct split)>1)').fetchone()[0]==0
  assert counts['train_targets']<=540000 and counts['validation_targets']<=60000
  assert policy['code_and_protocol']==pins()
 except BaseException as e:
  db.rollback();failure={'type':type(e).__name__,'reason':str(e)}
 finally:
  aggregates=[dict(zip(('source','split','histories','rows','input_tokens','target_tokens','families'),r)) for r in db.execute('select source,split,count(*),sum(selected_messages/2),sum(input_tokens),sum(target_tokens),count(distinct family) from documents group by source,split')]
  db.close()
  manifest=dict(schema=1,state='candidate_only_not_admitted' if failure is None else 'partial_candidate_not_admitted',failure=failure,database=dict(path=str(DATA/'candidates.sqlite'),sha256=sha(DATA/'candidates.sqlite'),bytes=(DATA/'candidates.sqlite').stat().st_size),policy_sha256=sha(DATA/'policy.json'),surface_inventory_sha256=sha(DATA/'surface-inventory.md'),source_files=[dict(path=str(sourcepath),sha256=sha(sourcepath),bytes=sourcepath.stat().st_size)],refusals=dict(path=str(refused),sha256=sha(refused)),code_and_protocol=policy['code_and_protocol'],tokenizer=ASSETS,aggregates=aggregates,by_surface=bysurface,position_exposure=dict(exposure),counts=dict(counts),verified_rows=rowindex,seconds=time.monotonic()-started,semantics_verified=False,independent_verification='pending',training_admitted=False,limitations=['Authored construction families with lexical/numeric expansion; not proof of semantic generalization.','Builder framing/selfchecks are not independent semantic verification.','New complete histories only; input_tokens counts sum all aligned turn-prefix row lengths.','Raw source records retain typed states and original/selected histories exactly; no pretraining/private/evaluation corpus is read.','Root legacy plus new exposed-development custody, independent verifier and final alignment admission remain required.'])
  write(DATA/'partial-candidate-manifest.json',manifest)
  print(canonical({k:manifest[k] for k in ('state','failure','counts','aggregates','verified_rows','seconds')}))
 if failure:raise RuntimeError('partial candidate preserved; no automatic retry')
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('mode',choices=('freeze','build'));a=parser.parse_args();freeze() if a.mode=='freeze' else main()
