import json,hashlib,sys,collections,shutil,math
from pathlib import Path
sys.path.insert(0,str(Path('.').resolve()))
sys.path.insert(0,str(Path('runs/nanochat-source').resolve()))
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_chat_format import encode_conversation, VERSION
from cloud_training.nano_tool_lessons import validate_lesson
from fractions import Fraction
root=Path('runs/instruction-repair-v3/candidates-reviewed');out=Path('runs/instruction-repair-v3/admitted-v1');out.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
toksha=sha('runs/ownbase-v2-data/tokenizer/tokenizer.pkl');tok=RustBPETokenizer.from_directory('runs/ownbase-v2-data/tokenizer')
manifest={'schema':1,'training_admitted':True,'format_version':VERSION,'context_tokens':2048,'tokenizer_sha256':toksha}
fingerprints={};counts={};suites=[]
source=Path('runs/ownbase-v2-sft/general-admitted-v1/train.jsonl')
assert sha(source)=='7a5ce088436a2dc93210e8a7eca5c266f05971787034a0d53fe02a5d38cb2c18'
source_keys=set()
for line in source.open():
 r=json.loads(line);source_keys.add(json.dumps({'messages':r['messages'],'policies':r.get('policies')},sort_keys=True))
for split in ['train','validation']:
 seen=set();targets=positions=0;families=collections.Counter();calls=0;rows=[]
 for line in (root/(split+'.jsonl')).read_text().splitlines():
  row=json.loads(line);s=row.get('spec',{});m=row['messages'];f=row['family'];families[f]+=1
  assert not any(x['role']=='system' for x in m)
  keys=json.dumps({'messages':m,'policies':row.get('policies')},sort_keys=True)
  assert keys not in seen;seen.add(keys)
  if f=='general_replay':assert keys in source_keys
  else:calls+=validate_lesson(row)['actual_calls']
  answers=[x['content'] for x in m if x['role']=='assistant' and 'content' in x]
  user=[x['content'] for x in m if x['role']=='user']
  if f=='general_replay':pass
  elif f=='state':assert answers[-2:]==[s['new'],s['old']] and s['new'] in user[1] and s['old'] in user[0]
  elif f=='two_entities':assert answers[-2:]==[str(s['b']),str(s['c'])] and s['other'] in user[2] and s['entity'] in user[3]
  elif f=='literal':assert all(a in u for a,u in zip(answers,user)) and len(answers)==2
  else:
   observed=[x['record']['data']['result'] for x in m if x['role']=='tool']
   if f=='convert':expect=[s['a']*s['factor']]
   else:
    def calc(a,b):return {'add':lambda:a+b,'subtract':lambda:a-b,'multiply':lambda:a*b,'divide':lambda:Fraction(a,b)}[s['op']]()
    expect=[calc(s['a'],s['b'])]+([calc(s['c'],s['b'])] if f=='tool_correction' else [])
   assert len(observed)==len(answers)==len(expect)
   assert all(math.isclose(float(o),float(e),rel_tol=1e-12,abs_tol=1e-9) for o,e in zip(observed,expect))
   assert all(Fraction(a)==Fraction(str(o)) for a,o in zip(answers,observed))
  enc=encode_conversation(tok,m,policies=row.get('policies'));assert len(enc['ids'])<=2048
  targets+=sum(enc['mask'][1:]);positions+=len(enc['ids']);rows.append(row)
  if split=='validation' and families[f]<=2:
   turns=[]
   for msg in m:
    if msg['role']=='user':turns.append({'user':msg['content'],'policy':row['policies'][len(turns)],'expected_calls':[]})
    elif msg['role']=='assistant':
     if 'tool_call' in msg:turns[-1]['expected_calls'].append(msg['tool_call'])
     else:turns[-1]['exact_answers']=[msg['content']]
   suites.append({'id':f+'-'+str(families[f]),'turns':turns})
 fingerprints[split]=seen;counts[split]={'families':dict(families),'actual_calls_replayed':calls,'positions':positions,'assistant_targets':targets}
 shutil.copyfile(root/(split+'.jsonl'),out/(split+'.jsonl'))
 manifest[split]={'file':split+'.jsonl','sha256':sha(out/(split+'.jsonl')),'sessions':len(rows),'assistant_targets':targets,'bytes':(out/(split+'.jsonl')).stat().st_size}
assert not fingerprints['train']&fingerprints['validation']
# All previously exposed quality prompts excluded verbatim from new training.
traintext=(out/'train.jsonl').read_text()
for suite in ['reports/l4-qualification-v1/instruction-repair-v2/heldout-suite.json','reports/l4-qualification-v1/instruction-repair-v1/heldout-suite.json','cloud_training/evaluation/conversation-tools-dev.json','reports/l4-qualification-v1/repair-pilot-v1/heldout-suite.json']:
 for session in json.loads(Path(suite).read_text())['sessions']:
  for turn in session['turns']:assert turn['user'] not in traintext
receipt={'schema':1,'training_admitted':True,'format_version':VERSION,'tokenizer_sha256':toksha,'jsonl_sha256':[manifest[k]['sha256'] for k in ['train','validation']],'review':'Root source review plus independent fraction arithmetic, state-answer, replayed broker, serving-format, length and split checks. This verifies bounded template semantics, not broad natural-language coverage. General replay is an exact subset of previously admitted training data; semantic noise remains possible.','counts':counts,'builder_sha256':sha('cloud_training/build_natural_repair.py'),'base_builder_sha256':sha('cloud_training/build_instruction_repair.py'),'general_replay_source_sha256':sha(source),'verifier_sha256':sha(__file__),'limits':['Development templates and entity pools are disjoint; original development prompts excluded verbatim. No sealed final acceptance accessed.','Synthetic templates, not teacher-generated or proof of general conversation quality.']}
(out/'admission.json').write_text(json.dumps(receipt,indent=2)+'\n');manifest['admission']={'receipt':'admission.json','sha256':sha(out/'admission.json')}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
Path('reports/l4-qualification-v1/instruction-repair-v3/heldout-suite.json').write_text(json.dumps({'purpose':'development_only_never_train','sessions':suites},indent=2)+'\n')
Path('reports/l4-qualification-v1/instruction-repair-v3/data-review.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(counts,indent=2))
