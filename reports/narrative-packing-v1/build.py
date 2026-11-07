"""Prospective narrative packing, no training or admission."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):os.environ[key]='1'
os.environ['TOKENIZERS_PARALLELISM']='false'
import argparse,collections,hashlib,json,pathlib,resource,shutil,signal,sqlite3,struct,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[2];HERE=pathlib.Path(__file__).resolve().parent;SOURCE=ROOT/'data/narrative-candidates-v1';DEST=ROOT/'data/narrative-packed-v1';sys.path.insert(0,str(ROOT))
from tokenizer import load,ASSETS
from stratified_language_validation import select_windows
import numpy as np
SEED=20261108
FIXED=['data/narrative-candidates-v1/candidates.sqlite','data/narrative-candidates-v1/candidate-manifest.json','data/narrative-candidates-v1/candidate-verification.json','data/narrative-candidates-v1/public-custody-binding.json','data/narrative-candidates-v1/policy.json','data/language-mixture-v1/custody.json','data/language-mixture-v1/public-development-custody.json','data/language-mixture-v2/proposed-exclusions.json','reports/language-provenance-recovery-v1/receipt.json','reports/narrative-quality-v1/manifest.json','reports/narrative-quality-v1/judgments.json','tokenizer.py','stratified_language_validation.py','data/tokenizer/encoder.json','data/tokenizer/vocab.bpe','reports/narrative-packing-v1/PROTOCOL.md','reports/narrative-packing-v1/build.py','reports/narrative-packing-v1/verify.py']
def read(p):return json.loads(p.read_bytes())
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)
def write(p,x):
 with p.open('x') as f:json.dump(x,f,indent=2);f.write('\n')
def main(decision_path,expected):
 os.nice(10);started=time.monotonic()
 def alarm(*a):raise TimeoutError('packing wallcap')
 signal.signal(signal.SIGALRM,alarm);signal.alarm(1800)
 def guard():
  if any(p.exists() for p in [ROOT/'runs/STOP',SOURCE/'STOP',DEST/'STOP',HERE/'STOP']):raise RuntimeError('STOP')
  if time.monotonic()-started>1800 or resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)>1536*1024**2:raise RuntimeError('wall/RSS cap')
  if shutil.disk_usage(ROOT).free<20*1024**3:raise RuntimeError('disk floor')
  if DEST.exists() and sum(p.stat().st_size for p in DEST.iterdir() if p.is_file())>1024**3:raise RuntimeError('output cap')
 guard();decision_path=pathlib.Path(decision_path);assert decision_path.is_absolute() and sha(decision_path)==expected;decision=read(decision_path)
 assert decision['state']=='approved_for_cpu_packing_only' and decision['training_admitted'] is False
 assert decision['expected']['validation']=={'documents':3340,'tokens':629749}
 for path,expected_pin in decision['pins'].items():assert sha(ROOT/path)==expected_pin,path
 pins={p:sha(ROOT/p) for p in FIXED};pins[str(decision_path.relative_to(ROOT))]=expected
 proof=read(SOURCE/'candidate-verification.json');binding=read(SOURCE/'public-custody-binding.json');manifest=read(SOURCE/'candidate-manifest.json')
 assert proof['state']=='PASS_independent_exact_projection_not_admitted' and proof['failures']==[] and binding['state']=='PASS_projection_root_custody_union_bound_not_admitted' and binding['failures']==[]
 assert proof['database_sha256']==binding['database_sha256']==manifest['database']['sha256']==sha(SOURCE/'candidates.sqlite')
 assert binding['projection_verification_sha256']==sha(SOURCE/'candidate-verification.json') and binding['manifest_sha256']==sha(SOURCE/'candidate-manifest.json')
 assert binding['public_custody_sha256']==sha(ROOT/'data/language-mixture-v1/public-development-custody.json') and binding['legacy_custody_sha256']==sha(ROOT/'data/language-mixture-v1/custody.json') and binding['quality_exclusions_sha256']==sha(ROOT/'data/language-mixture-v2/proposed-exclusions.json')
 excluded=set(decision['excluded_training_ids']);assert len(excluded)==len(decision['excluded_training_ids'])
 conn=sqlite3.connect(f'file:{SOURCE}/candidates.sqlite?mode=ro',uri=True);conn.row_factory=sqlite3.Row;rows=[dict(r) for r in conn.execute('select * from documents')];conn.close();assert excluded<={r['doc_id'] for r in rows if r['split']=='train'}
 DEST.mkdir(exist_ok=False);freeze=dict(state='frozen_before_packing',seed=SEED,pins=pins,training_excluded_doc_ids=sorted(excluded),preserve_all_validation=True,validation_quotas={'short':32,'long':96},limits={'seconds':1800,'rss_bytes':1536*1024**2,'output_bytes':1024**3,'free_disk_bytes':20*1024**3},training_admitted=False);write(DEST/'freeze.json',freeze)
 tok=load();counts={};shards={};valdocs=[];failure=None
 try:
  for split in ['train','validation']:
   chosen=[r for r in rows if r['split']==split and r['doc_id'] not in excluded];chosen.sort(key=lambda r:(hashlib.sha256(canonical(['narrative-pack-v1',SEED,split,r['doc_id']]).encode()).hexdigest(),r['doc_id']))
   offset=0;count=0;short=0;long=0
   with (DEST/f'narrative-{split}.u16').open('xb') as out,(DEST/f'{split}.documents.jsonl').open('x') as index:
    for r in chosen:
     guard();ids=tok.encode(r['text']).ids;assert len(ids)+1==r['tokens'] and all(0<=x<50256 for x in ids);ids.append(50256);body=struct.pack('<'+'H'*len(ids),*ids);digest=hashlib.sha256(body).hexdigest();out.write(body)
     record={k:r[k] for k in ['doc_id','family','split','source','source_file','source_row','raw_sha256','normalized_sha256','canonical_url']};record.update(offset=offset,tokens=len(ids),document_sha256=digest)
     index.write(canonical(record)+'\n')
     if split=='validation':valdocs.append(dict(source='narrative',document_id=r['doc_id'],offset=offset,tokens=len(ids),document_sha256=digest))
     offset+=len(ids);count+=1;short+=32<=len(ids)-1<128;long+=len(ids)-1>=128
   counts[split]=dict(documents=count,tokens=offset,eligible_short_documents=short,eligible_long_documents=long);shards['narrative-'+split]=dict(tokens=offset,docs=count,sha256=sha(DEST/f'narrative-{split}.u16'))
  guard();array=np.memmap(DEST/'narrative-validation.u16',mode='r',dtype='<u2');windows=select_windows({'narrative':array},valdocs,{'narrative':{'tokens':len(array),'sha256':shards['narrative-validation']['sha256']}},seed=SEED,documents_per_source=128,min_targets=32,max_targets=512,per_source_quotas={'narrative':{'short':32,'long':96}});write(DEST/'validation-windows.json',windows);del array
  assert counts['validation']['documents']==3340 and counts['validation']['tokens']==629749
  for split in ('train','validation'):
   assert {k:counts[split][k] for k in ('documents','tokens')}==decision['expected'][split]
  guard();assert all(sha(ROOT/p)==h for p,h in pins.items())
 except BaseException as error:failure={'type':type(error).__name__,'reason':str(error)}
 finally:
  outputs={}
  for p in DEST.iterdir():
   guard()
   if p.is_file() and p.name!='freeze.json':outputs[p.name]={'bytes':p.stat().st_size,'sha256':sha(p)}
  receipt=dict(state='partial_packing_not_admitted' if failure else 'packed_pending_independent_verification',failure=failure,training_admitted=False,shards=shards,counts=counts,outputs=outputs,freeze_sha256=sha(DEST/'freeze.json'),quality_decision_sha256=expected,source_database_sha256=manifest['database']['sha256'],source_files=manifest['source_files'],source_licenses=manifest['source_licenses'],excluded_training_documents=len(excluded),preserved_validation_documents=3340,seconds=time.monotonic()-started,limitations='Whole documents packed once without wraps; validation includes flagged samples. No training budget, semantic certification or admission. Root decision and independent verifier required.')
  write(DEST/'manifest.json',receipt);signal.alarm(0);print(json.dumps({'state':receipt['state'],'counts':counts,'failure':failure}))
 if failure:raise RuntimeError(failure)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--decision',required=True);p.add_argument('--decision-sha256',required=True);a=p.parse_args();main(a.decision,a.decision_sha256)
