"""Independent bounded raw-prefix/current-framing verification. No admission or model."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
os.environ['TOKENIZERS_PARALLELISM']='false'
import collections,hashlib,json,pathlib,re,resource,shutil,sqlite3,sys,time,unicodedata
import pyarrow.parquet as pq
R=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(R))
from tokenizer import load,ASSETS
from dialogue import training_row
from own_base_sft_rows import validate_reply_reservations
D=R/'data/sft-readiness-v3';start=time.monotonic();output=D/'candidate-verification.json'
def check():
 assert time.monotonic()-start<600,'time cap'
 assert not(R/'runs/STOP').exists() and not(D/'STOP').exists(),'STOP'
 assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)<3*1024**3,'RSS cap'
 assert shutil.disk_usage(R).free>=20*1024**3,'disk floor'
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b);check()
 return h.hexdigest()
def sh(s):return hashlib.sha256(s.encode()).hexdigest()
def norm(s):return ' '.join(unicodedata.normalize('NFKC',s).casefold().split())
assert not output.exists(),'preserve existing receipt'
result={'state':'failed_not_admitted','training_admitted':False,'phase':'pre_host_policy_pre_custody','verified_rows':0}
try:
 check();mp=D/'partial-candidate-manifest.json';assert sha(mp)=='ca9bc2293c9de3187cab49e148a3f36ffafc4ce2b1016f059add94bd6f039116';m=json.loads(mp.read_text())
 assert sha(D/'candidates.sqlite')==m['database']['sha256']=='37f747a1b5bdd6c3df9545ad7691d7d550c74b65e3e740b785d0d88521c20321'
 assert (D/'candidates.sqlite').stat().st_size==m['database']['bytes']
 for file,key in [('policy.json','policy_sha256'),('source-integrity.json','source_integrity_sha256'),('failure.json','failure_sha256')]:assert sha(D/file)==m[key]
 policy=json.loads((D/'policy.json').read_text());integrity=json.loads((D/'source-integrity.json').read_text())
 assert policy['source_files']==integrity['files']==m['source_files'];assert integrity['policy_sha256']==m['policy_sha256'];assert policy['code_and_policy']==integrity['code_and_policy']==m['code_and_policy'];assert policy['tokenizer']==integrity['tokenizer']==m['tokenizer']==ASSETS
 for path,digest in m['code_and_policy'].items():assert sha(R/path)==digest,path
 for name,digest in ASSETS.items():assert sha(R/'data/tokenizer'/name)==digest
 for f in m['source_files']:
  p=pathlib.Path(f['path']);assert sha(p)==f['sha256'];assert p.stat().st_size==f['bytes'];rp=p.parent/'receipt.json';assert sha(rp)==f['receipt_sha256'];rr=json.loads(rp.read_text());assert rr['sha256']==f['sha256'] and rr['revision']==f['revision']
 runtime_pins={p:sha(R/p) for p in ('own_base_sft_rows.py','tools/__init__.py')};tok=load();con=sqlite3.connect(f'file:{D}/candidates.sqlite?mode=ro',uri=True);con.row_factory=sqlite3.Row
 assert con.execute('PRAGMA quick_check').fetchone()[0]=='ok'
 assert con.execute('select count(*),count(distinct doc_id),count(distinct normalized_sha256) from documents').fetchone()[:]==(46553,46553,46553)
 assert not con.execute('select family from documents group by family having count(distinct split)>1').fetchall()
 aggkeys=('source','split','documents','input_tokens','target_tokens','whole','has_system','multi_pair','generation_max','input_max')
 aggregates=[dict(zip(aggkeys,row)) for row in con.execute('select source,split,count(*),sum(input_tokens),sum(target_tokens),sum(whole),sum(has_system),sum(selected_messages>2),max(generation_max),max(input_tokens) from documents group by source,split')]
 assert aggregates==m['aggregates']
 families=[dict(source=s,split=sp,families=n) for s,sp,n in con.execute('select source,split,count(distinct family) from documents group by source,split')];assert families==m['families']
 for sourcefile in m['source_files']:
  wanted={row['row_index']:dict(row) for row in con.execute('select * from documents where raw_sha256=?',(sourcefile['sha256'],))};source_i=-1;seen=0
  for batch in pq.ParquetFile(sourcefile['path']).iter_batches(batch_size=64,use_threads=False):
   check()
   for raw in batch.to_pylist():
    source_i+=1
    if source_i not in wanted:continue
    d=wanted.pop(source_i);seen+=1;msgs=raw['messages'];hist=json.loads(d['selected_history_json']);system=bool(msgs and msgs[0]['role']=='system');body=msgs[int(system):]
    assert raw['source']==d['source'] and d['source'] in policy['sources'];assert d['doc_id']==sourcefile['sha256']+':'+str(source_i);assert d['raw_path']==sourcefile['path']
    assert 2<=len(body)<=8 and len(body)%2==0;assert all(x['role']==('user' if i%2==0 else 'assistant') for i,x in enumerate(body));assert all(isinstance(x['content'],str) and x['content'].strip() for x in msgs)
    expected=[{'role':x['role'],'text':x['content']} for x in msgs];assert hist==expected[:len(hist)] and 2<=len(hist)-int(system)<=len(body) and (len(hist)-int(system))%2==0
    assert d['has_system']==int(system) and d['whole']==int(len(hist)==len(msgs)) and d['selected_messages']==len(hist)-int(system)
    full='\n'.join(x['role'].capitalize()+': '+x['content'] for x in msgs);assert full==d['text'];assert sh(norm(full))==d['parent_normalized_sha256'];assert sh('\n'.join(x['role']+': '+norm(x['text']) for x in hist))==d['normalized_sha256']
    opening=re.sub(r'\b\d+(?:\.\d+)?\b','<number>',norm(body[0]['content']));opening=re.sub(r'"[^"\n]*"','<quoted>',opening);family=sh(opening);assert family==d['family'];assert d['split']==('validation' if int(sh('forge-language-mixture-v1-20261106'+'dialogue'+family)[:12],16)%50==0 else 'train')
    row=training_row(tok,hist,context=1024);assert len(row.inputs)==d['input_tokens'] and row.target_count==d['target_tokens']
    lengths=validate_reply_reservations(tok,hist,reply_budget=256,context=1024);assert max(x['reply_tokens'] for x in lengths)==d['generation_max'];assert sum(x['reply_tokens'] for x in lengths)==d['target_tokens'];assert all(len(tok.encode(x['text']).ids)<=192 for x in hist if x['role']=='assistant')
    result['verified_rows']+=1
   if not wanted:break
  assert not wanted
 assert result['verified_rows']==46553
 assert sha(D/'candidates.sqlite')==m['database']['sha256'];assert sha(mp)=='ca9bc2293c9de3187cab49e148a3f36ffafc4ce2b1016f059add94bd6f039116'
 result.update(state='PASS_pre_host_policy_not_admitted',manifest_sha256=sha(mp),database_sha256=m['database']['sha256'],runtime_pins=runtime_pins,aggregates=aggregates,checks=['all raw source hashes/receipts and frozen code/policy/tokenizer pins','all selected histories exact complete prefixes of raw parents with system preserved','all stored raw-parent/selected normalization hashes and family/split rules','all current framing input/target counts and fixed256 reservation/max reply checks','all assistant content <=192 tokens','SQL uniqueness, aggregates and no family crossing splits'],limitations=['Pre-host-policy: later policy insertion and current-turn masking require separate revalidation.','No quality or custody admission; no protected cases read.','Does not rerun parent content-filter regexes or prove longest eligible prefix/first duplicate winner.','Posthoc code identity is not execution attestation.'])
except BaseException as e:
 result.update(error_type=type(e).__name__)
 raise
finally:
 result.update(seconds=time.monotonic()-start,verifier_sha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest());output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ('state','verified_rows','seconds')}))
