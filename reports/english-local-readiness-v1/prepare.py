"""Read frozen inputs, derive exposed fit probes, verify real serialization/packing."""
import collections,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/'runs/nanochat-source')]
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_chat_format import encode_conversation,training_example
from cloud_training.nano_sft import JsonlConversations,FiniteEpochDataset,BestFitConversations,collect_update,load_manifest
from cloud_training.nano_fit_contract import validate_review_file
from cloud_training.nano_eval import verify_upstream
P=Path(__file__).parent;D=ROOT/'reports/english-first-v1'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def write(name,value):
 p=P/name
 if p.exists():raise FileExistsError(p)
 p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
freeze={}
for folder,name in [(D,'packet-freeze.json'),(ROOT/'reports/corrective-corpus-v1','freeze.json')]:
 bindings=json.loads((folder/name).read_text())['files']
 for n,h in bindings.items():
  if sha(folder/n)!=h:raise ValueError('Frozen input changed: '+n)
 freeze[str(folder.relative_to(ROOT))]={'files':len(bindings),'sha256':sha(folder/name),'unchanged':True}
contract=json.loads((D/'diagnostic-contract.json').read_text());admission=json.loads((D/'diagnostic-admission.json').read_text());validate_review_file(D/'diagnostic-manifest.json',admission,contract)
verify_upstream(ROOT/'runs/nanochat-source')
if sha(ROOT/'runs/ownbase-v2-data/tokenizer/tokenizer.pkl')!=contract['tokenizer_sha256']:raise ValueError('Tokenizer mismatch')
tok=RustBPETokenizer.from_directory(str(ROOT/'runs/ownbase-v2-data/tokenizer'))
rows=[json.loads(x) for x in (D/'fit-train.jsonl').read_text().splitlines()];sessions=[];checks=[]
for r in rows:
 enc=encode_conversation(tok,r['messages'],policies=r['policies'],context=2048)
 example=training_example(enc);users=0;turns=[]
 for k,m in enumerate(r['messages']):
  if m['role']=='user':users+=1;continue
  if m['role']=='system':continue
  if m['role']!='assistant' or 'content' not in m:raise ValueError('Fit suite requires reviewed no-call text')
  prefix=encode_conversation(tok,r['messages'][:k],policies=r['policies'][:users],for_generation=True,context=2048,reply_budget=128)
  if prefix['ids']!=enc['ids'][:len(prefix['ids'])]:raise ValueError('Train/serve prefix mismatch')
  turns.append({'user':r['messages'][k-1]['content'],'policy':r['policies'][users-1],'reference_answer':m['content'],'expected_calls':[],'reply_budget':128,'rubric':'Semantic equivalents allowed. Relevant natural English, exact current facts and requested constraints, clean end; no tools. Judge followups against actual earlier model replies. Reference wording is not mandatory.'})
 for span in enc['spans']:
  if span['kind'] in ('user_prompt','user_start','user_end','assistant_start','bos') and any(enc['mask'][span['start']:span['end']]):raise ValueError('Prompt supervision')
  if span['kind']=='assistant_end' and not all(enc['mask'][span['start']:span['end']]):raise ValueError('Missing end supervision')
 if example['labels']!=[t if m else -100 for t,m in zip(enc['ids'][1:],enc['mask'][1:])]:raise ValueError('Shifted-label mismatch')
 sessions.append({'id':r['id'],'category':r['family'],'source_group':r['provenance']['source_group'],'turns':turns,**({'system':r['messages'][0]['content']} if r['messages'][0]['role']=='system' else {})})
 checks.append({'id':r['id'],'turns':users,'targets':sum(enc['mask'][1:]),'tokens':len(enc['ids']),'prefix_mask_end_shift_pass':True})
# Explicit system-message parity in both no-call modes, without altering frozen rows.
for enabled in (False,True):
 policy={'permit_calls':enabled,'allowed_names':['calculate','convert'] if enabled else []};messages=[{'role':'system','content':'Answer briefly.'},{'role':'user','content':'Say hello.'},{'role':'assistant','content':'Hello.'}]
 full=encode_conversation(tok,messages,policies=[policy]);prefix=encode_conversation(tok,messages[:-1],policies=[policy],for_generation=True,reply_budget=128)
 if full['ids'][:len(prefix['ids'])]!=prefix['ids']:raise ValueError('System prefix mismatch')
manifest=load_manifest(D/'diagnostic-manifest.json',contract['tokenizer_sha256'])
base=JsonlConversations(D/'fit-train.jsonl',tok,manifest['train']['sha256']);data=FiniteEpochDataset(base,64,seed=103,diagnostic_only=True);packing=BestFitConversations(data,buffer_size=1)
updates=[];seen=set();mass=collections.Counter()
while True:
 before=packing.consumed;batches,count=collect_update(packing,1,4)
 if not batches:break
 ids=data.order[before:packing.consumed]
 for index in ids:mass[rows[index]['family']]+=base.target_counts[index];seen.add(index)
 updates.append({'update':len(updates)+1,'targets':count,'replay_sessions':len(ids),'cumulative_unique_sessions':len(seen),'family_replay_targets':dict(mass)})
 # Invalid labels are only native ignore or actual next token; padding must be ignore.
 for xs,ys in batches:
  for x,y in zip(xs,ys):
   if len(x)!=2048 or len(y)!=2048 or any(v < -1 for v in y):raise ValueError('Packed labels invalid')
write('fit-suite.json',{'schema':1,'purpose':'training_fit_exposed_never_release','required_context_tokens':2048,'source_sha256':sha(D/'fit-train.jsonl'),'sessions':sessions})
write('data-checks.json',{'status':'pass','frozen_inputs':freeze,'rows':checks,'sessions':len(rows),'turns':sum(x['turns'] for x in checks),'unique_assistant_targets':sum(base.target_counts),'system_prefix_checks':2,'full_epochs':64,'full_updates':len(updates),'full_packed_rows':packing.rows,'full_replay_targets':sum(x['targets'] for x in updates),'cap64_replay_targets':sum(x['targets'] for x in updates[:64]),'updates':updates,'release_exposed':False})
print('Fit suite and data checks saved:',len(sessions),'sessions',len(updates),'full updates')
