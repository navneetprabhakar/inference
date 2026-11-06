import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
os.environ['TOKENIZERS_PARALLELISM']='false'
import array,collections,hashlib,json,pathlib,resource,shutil,sqlite3,sys,time
R=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(R));D=R/'data/own-base-tool-session-aligned-v1';V=R/'data/own-base-tool-session-extension-v1';Q=R/'data/own-base-tool-review-v1'
from tokenizer import load
from own_base_sft_rows import last_turn_row
from own_base_chat import policy_text
LIMITS=dict(seconds=300,rss_bytes=200*1024**2,output_bytes=50*1024**2,free_bytes=20*1024**3)
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def read(p):return json.loads(p.read_text())
def write(p,x):
 with p.open('x') as f:json.dump(x,f,indent=2);f.write('\n')
def canon(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)
def check(start):
 assert time.time()-start<300,'time cap'
 assert not any(p.exists() for p in (R/'runs/STOP',R/'runs/own-base-foundation-01/STOP',D/'STOP')),'STOP'
 assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)<=LIMITS['rss_bytes'],'RSS cap'
 assert shutil.disk_usage(R).free>=LIMITS['free_bytes'],'disk floor'
 assert sum(p.stat().st_size for p in D.glob('*') if p.is_file())<=LIMITS['output_bytes'],'output cap'
def pins():
 paths=[V/n for n in ('candidates.sqlite','candidate-manifest.json','policy.json','custody.json','symbolic-verification.json','source-records.json','refused.json')]
 paths += [R/n for n in ('own_base_tool_adapter.py','own_base_chat.py','own_base_sft_rows.py','dialogue.py','tokenizer.py','tools/__init__.py','data/tokenizer/encoder.json','data/tokenizer/vocab.bpe')]
 paths += list((R/'reports/own-base-tool-session-extension-v1').glob('*.py'))+list((R/'reports/own-base-tool-session-extension-v1').glob('*.md'))+list(pathlib.Path(__file__).parent.glob('*.py'))+[pathlib.Path(__file__).with_name('PROTOCOL.md')]
 return {str(p.relative_to(R)):sha(p) for p in paths}
def verify_inputs(f):
 assert pins()==f['pins'];m=read(V/'candidate-manifest.json');v=read(V/'symbolic-verification.json');c=read(V/'custody.json')
 assert m['database']['sha256']==sha(V/'candidates.sqlite')==c['pins']['candidates.sqlite']
 assert v['candidate_manifest_sha256']==sha(V/'candidate-manifest.json')==c['pins']['candidate-manifest.json']
 assert all(sha(R/name)==expected for name,expected in read(V/'policy.json')['pins'].items())
 assert sha(V/'policy.json')==m['policy_sha256'] and sha(V/'source-records.json')==m['source_records_sha256'] and sha(V/'refused.json')==m['refused_sha256']
 assert v['state']=='PASS_independent_symbolic_retained_only' and c['state']=='screened_not_admitted'
 assert sha(R/'reports/own-base-tool-session-extension-v1/verify_symbolic.py')==v['verifier_sha256']
def excluded():return set(read(V/'custody.json')['excluded_doc_ids'])
def conn():
 c=sqlite3.connect(f'file:{V}/candidates.sqlite?mode=ro',uri=True);c.row_factory=sqlite3.Row;c.execute('pragma cache_size=-1024');return c
def encode(xs):
 a=array.array('H',(65535 if x==-100 else x for x in xs))
 if sys.byteorder!='little':a.byteswap()
 return a.tobytes()
def positions(labels):
 c=collections.Counter()
 for i,x in enumerate(labels):
  if x!=-100:
   lo=((i+1)//256)*256;c[f'{lo}..{lo+255}']+=1
 return dict(c)
def freeze():
 D.mkdir(exist_ok=True);assert not any(D.iterdir());start=time.time();check(start);assert encode([0,50256,-100])==b'\x00\x00P\xc4\xff\xff';write(D/'freeze.json',dict(started=start,pins=pins(),limits=LIMITS,state='frozen_before_execution'))
def build():
 f=read(D/'freeze.json');start=f['started'];check(start);verify_inputs(f);tok=load();ex=excluded();c=conn();counts=collections.defaultdict(collections.Counter);offsets=collections.Counter();exposure=collections.Counter();families={};streams={}
 for split in ('train','exposed-development'):streams[split]=[(D/f'{split}.{suffix}').open('xb' if suffix.endswith('u16') else 'x') for suffix in ('inputs.u16','labels.u16','index.jsonl')]
 refused=(D/'refused.jsonl').open('x')
 try:
  for index,d in enumerate(c.execute('select * from documents order by doc_id')):
   if index%20==0:check(start)
   if d['doc_id'] in ex:continue
   split=d['split'];co=counts['own-base-tool-session-extension:'+split];co['before_histories']+=1;co['before_original_targets']+=d['target_tokens'];original=json.loads(d['original_lesson_json']);lessonhash=hashlib.sha256(canon(original).encode()).hexdigest();assert lessonhash==d['doc_id'];assert families.setdefault(d['family'],split)==split
   try:
    adapted=json.loads(d['adapted_json']);metadata=json.loads(d['row_metadata_json']);rows=[]
    for turn,t in enumerate(adapted):
     assert t['turn_index']==turn and t['policy']==original['policy'][turn];assert t['history'][0]==dict(role='system',text=policy_text(t['policy']['permit_calls'],t['policy'].get('allowed_names')))
     row=last_turn_row(tok,t['history'],reply_budget=256,context=1024);assert len(row.inputs)==metadata[turn]['input_tokens'] and row.target_count==metadata[turn]['assistant_targets'];rows.append(row)
    assert len(rows)==d['rows'] and sum(r.target_count for r in rows)==d['target_tokens']
   except (ValueError,TypeError,AssertionError) as error:
    co['refused_histories']+=1;co['refused_original_targets']+=d['target_tokens'];refused.write(json.dumps(dict(doc_id=d['doc_id'],split=split,source='own-base-tool-session-extension',reason=type(error).__name__))+'\n');continue
   co['accepted_histories']+=1;co['accepted_original_targets']+=d['target_tokens']
   historyhash=hashlib.sha256(canon(original['history']).encode()).hexdigest()
   for turn,row in enumerate(rows):
    pos=positions(row.labels);item=dict(source='own-base-tool-session-extension',doc_id=d['doc_id'],turn=turn,family=d['family'],split=split,offset=offsets[split],length=len(row.inputs),target_count=row.target_count,original_history_sha256=historyhash,original_lesson_sha256=lessonhash,position_exposure=pos);streams[split][0].write(encode(row.inputs));streams[split][1].write(encode(row.labels));streams[split][2].write(json.dumps(item,separators=(',',':'))+'\n');offsets[split]+=len(row.inputs);co['rows']+=1;co['aligned_targets']+=row.target_count;exposure.update(pos)
 finally:
  refused.close()
  for handles in streams.values():
   for h in handles:h.close()
 assert counts['own-base-tool-session-extension:train']['before_histories']==29 and counts['own-base-tool-session-extension:exposed-development']['before_histories']==8
 assert counts['own-base-tool-session-extension:train']['before_original_targets']==6073 and counts['own-base-tool-session-extension:exposed-development']['before_original_targets']==1678
 check(start);verify_inputs(f);write(D/'receipt.json',dict(state='prepared_for_diagnostic_pending_independent_verification',training_admitted=False,counts=dict(counts),position_exposure=dict(exposure),stream_tokens=dict(offsets),freeze_sha256=sha(D/'freeze.json'),outputs={p.name:dict(sha256=sha(p),bytes=p.stat().st_size) for p in D.iterdir() if p.name!='freeze.json'},seconds=time.time()-start));print(json.dumps(dict(counts)))
if __name__=='__main__':
 os.nice(10)
 if sys.argv[1]=='freeze':freeze()
 elif sys.argv[1]=='build':build()
