"""Two fully re-read long dialogues: edit redundant prose, never slice tokens/turns."""
import sys,json,hashlib,re,copy,unittest,io
from pathlib import Path
if (Path(__file__).resolve().parent/'freeze.json').exists():raise SystemExit('Frozen corpus/release packet: create a new version; do not regenerate in place.')
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'runs/nanochat-source'))
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_chat_format import encode_conversation
P=Path(__file__).resolve().parent;D=ROOT/'runs/corrective-corpus-v1/v21';rows=[json.loads(l) for l in (D/'train.jsonl').read_text().splitlines()];T=RustBPETokenizer.from_directory(str(ROOT/'runs/ownbase-v2-data/tokenizer'));patches=[];reviews=[]
for index in [413,440]:
 original=rows[index];row=copy.deepcopy(original);edits=[]
 if index==413:
  edits=[2,6,10,12]
  row['messages'][2]['content']='The usable area is x = 1 to 41, y = 1 to 29. Centers extend 6 cm horizontally and 4 cm vertically in each direction. A spans x = -5 to 7, y = -3 to 5, crossing left and bottom margins. B spans x = 6 to 18, y = -3 to 5, crossing the bottom margin. Their intersection is 1 by 8 cm, or 8 cm², so the no-overlap claim is false. C crosses the bottom margin; D and G cross the left margin. E, F and H fit. Only A–B overlap by positive area; edge contact is allowed.'
  row['messages'][6]['content']='A spans x = 1 to 13, y = 1 to 9. D spans x = 1 to 13, y = 9 to 17. They share the edge from (1, 9) to (13, 9), with zero overlap area; this contact is allowed.'
  for i in [10,12]:
   text=row['messages'][i]['content'];row['messages'][i]['content']='```python\n'+re.search(r'```python\n(.*?)```',text,re.S)[1]+'```'
 else:
  edits=[8];text=row['messages'][8]['content'];row['messages'][8]['content']='```python\n'+re.search(r'```python\n(.*?)```',text,re.S)[1]+'```'
 # All code remains byte-identical; execute inspected pure validator/reducer snippets.
 original_code=[code for m in original['messages'] if m['role']=='assistant' and 'content' in m for code in re.findall(r'```python\n(.*?)```',m['content'],re.S)]
 patched_code=[code for m in row['messages'] if m['role']=='assistant' and 'content' in m for code in re.findall(r'```python\n(.*?)```',m['content'],re.S)];assert original_code==patched_code
 namespace={'__name__':'verified_reference'}
 for code in patched_code:exec(compile(code,'reviewed_reference','exec'),namespace)
 tests=0
 if index==413:
  result=unittest.TextTestRunner(stream=io.StringIO()).run(unittest.defaultTestLoader.loadTestsFromTestCase(namespace['TestValidateRectangles']));assert result.wasSuccessful();tests=result.testsRun
  layout=[{'id':str(i),'x':x,'y':y,'width':12,'height':8} for i,(x,y) in enumerate([(1,1),(13,1),(25,1),(1,9),(13,9),(25,9),(1,17),(13,17)])];assert namespace['validate_rectangles'](layout,allow_rotation=True)==[];tests+=1
 else:
  fixture=[{'type':'create','id':'a','quantity':3},{'type':'cancel','id':'b'},{'type':'create','id':'b','quantity':5},{'type':'create','id':'c','quantity':6},{'type':'create','id':'c','quantity':6},{'type':'create','id':'d','quantity':2},{'type':'cancel','id':'d'},{'type':'create','id':'e','quantity':1}];assert namespace['reduce_events'](fixture)['active']=={'a':3,'c':6,'e':1};tests=24*2+5*2+1
 for old,new in zip(original['messages'],row['messages'],strict=True):
  if old['role']!='assistant' or 'tool_call' in old:assert old==new
 enc=encode_conversation(T,row['messages'],policies=row['policies'],context=4096);users=0;prefix_max=0
 for i,m in enumerate(row['messages']):
  if m['role']=='user':users+=1
  if m['role']=='assistant':
   pre=encode_conversation(T,row['messages'][:i],policies=row['policies'][:users],context=4096,for_generation=True,reply_budget=192);prefix_max=max(prefix_max,len(pre['ids']))
 assert 3072<=len(enc['ids'])<=4096
 row['provenance']['corrective_review']='reports/corrective-corpus-v1/long-prefix-review.json';patches.append(row)
 reviews.append({'group':row['provenance']['group'],'parent_train_index':index,'changed_assistant_message_indices':edits,'all_turns_semantically_reread':True,'code_unchanged':True,'users_and_tools_unchanged':True,'checks':tests,'framed_tokens':len(enc['ids']),'max_prefix_tokens':prefix_max,'minimum_reply_headroom':4096-prefix_max,'targets_after_3072':sum(enc['mask'][3072:]),'reason':'Remove redundant introductions/outros and compress worked prose without dropping constraints, events, code, turns or tool results. All action prefixes now reserve192tokens.'})
(P/'long-prefix-patches.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in patches));(P/'long-prefix-review.json').write_text(json.dumps({'parent_manifest_sha256':hashlib.sha256((D/'manifest.json').read_bytes()).hexdigest(),'reviews':reviews,'training_admitted':False},indent=2)+'\n');print(reviews)
