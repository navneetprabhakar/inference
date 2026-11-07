"""Exact narrative candidate projection only; no semantic/admission claim."""
import hashlib,json,pathlib,resource,shutil,signal,sqlite3,sys,time,os
ROOT=pathlib.Path(__file__).resolve().parents[2];HERE=pathlib.Path(__file__).resolve().parent;OUT=ROOT/'data/narrative-candidates-v1';OLD=ROOT/'data/language-mixture-v1'
FILES=['data/language-mixture-v1/candidates.sqlite','data/language-mixture-v1/partial-candidate-manifest.json','data/language-mixture-v1/candidate-verification.json','data/language-mixture-v1/custody.json','data/language-mixture-v2/proposed-exclusions.json','data/language-mixture-v2/quality-review.json','reports/language-provenance-recovery-v1/plan.json','reports/language-provenance-recovery-v1/receipt.json','tokenizer.py','data/tokenizer/encoder.json','data/tokenizer/vocab.bpe','reports/narrative-projection-v1/PROTOCOL.md','reports/narrative-projection-v1/build.py','reports/narrative-projection-v1/verify.py']
EXPECTED={'train':{'documents':169204,'tokens':31494305},'validation':{'documents':3340,'tokens':629749}}
def read(p):return json.loads(p.read_bytes())
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,x):
 with p.open('x') as f:json.dump(x,f,indent=2);f.write('\n')
def main():
 os.nice(10);start=time.monotonic()
 def hard(*args):raise TimeoutError('projection wall cap')
 signal.signal(signal.SIGALRM,hard);signal.alarm(1200)
 def check():
  if any(p.exists() for p in [ROOT/'runs/STOP',OLD/'STOP',OUT/'STOP',HERE/'STOP']):raise RuntimeError('STOP')
  if time.monotonic()-start>1200 or resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)>1536*1024**2:raise RuntimeError('wall/RSS cap')
  if shutil.disk_usage(ROOT).free<20*1024**3:raise RuntimeError('disk floor')
  if OUT.exists() and sum(p.stat().st_size for p in OUT.iterdir() if p.is_file())>768*1024**2:raise RuntimeError('output cap')
 check();pins={p:sha(ROOT/p) for p in FILES};manifest=read(OLD/'partial-candidate-manifest.json');legacy=read(OLD/'custody.json');oldproof=read(OLD/'candidate-verification.json');recovery=read(ROOT/'reports/language-provenance-recovery-v1/receipt.json')
 assert manifest['candidate_database_sha256']==legacy['candidate_database_sha256']==oldproof['candidate_database_sha256']==pins['data/language-mixture-v1/candidates.sqlite'];assert oldproof['failures']==[] and legacy['state']=='cleared'
 assert recovery['state']=='PASS_exact_raw_provenance_restored_not_admitted'
 for entry in recovery['restored']:
  p=pathlib.Path(entry['recovered_path']);check();assert p.stat().st_size==entry['bytes'] and sha(p)==entry['sha256'];pins[str(p.relative_to(ROOT))]=entry['sha256']
 recoveryplan=read(ROOT/'reports/language-provenance-recovery-v1/plan.json');archive=pathlib.Path(recoveryplan['archive_destination']);assert sha(archive)==recovery['archive_sha256'];pins[str(archive.relative_to(ROOT))]=recovery['archive_sha256']
 exclusions=set(legacy['excluded_doc_ids'])|{x['doc_id'] for x in read(ROOT/'data/language-mixture-v2/proposed-exclusions.json')}
 OUT.mkdir(exist_ok=False);write(OUT/'policy.json',dict(state='frozen_before_projection',pins=pins,selection='stories minus legacy custody and v2 deferrals; exact rows ordered by doc_id',expected=EXPECTED,source_manifest=str(OLD/'partial-candidate-manifest.json'),source_database=str(OLD/'candidates.sqlite'),new_public_custody='pending original-source supplement; retain IDs',training_admitted=False))
 db=sqlite3.connect(OUT/'candidates.sqlite');original=sqlite3.connect(f'file:{OLD}/candidates.sqlite?mode=ro',uri=True);db.execute(original.execute("select sql from sqlite_master where type='table' and name='documents'").fetchone()[0]);db.execute('pragma cache_size=-2048');counts={k:dict(documents=0,tokens=0) for k in EXPECTED};failure=None
 try:
  for row in original.execute("select * from documents where source='stories' order by doc_id"):
   if row[0] in exclusions:continue
   check();db.execute('insert into documents values('+','.join('?'*11)+')',row);counts[row[5]]['documents']+=1;counts[row[5]]['tokens']+=row[6]
   if sum(x['documents'] for x in counts.values())%1000==0:db.commit()
  db.commit();assert counts==EXPECTED;assert db.execute('pragma integrity_check').fetchone()[0]=='ok';assert all(sha(ROOT/p)==h for p,h in pins.items());check()
 except BaseException as error:db.rollback();failure={'type':type(error).__name__,'reason':str(error)}
 finally:
  actual={s:dict(documents=n,tokens=t) for s,n,t in db.execute('select split,count(*),sum(tokens) from documents group by split')};db.close();original.close();signal.alarm(0)
  receipt=dict(state='partial_projection_not_admitted' if failure else 'candidate_projection_not_admitted',failure=failure,database={'path':str(OUT/'candidates.sqlite'),'sha256':sha(OUT/'candidates.sqlite'),'bytes':(OUT/'candidates.sqlite').stat().st_size},policy_sha256=sha(OUT/'policy.json'),source_manifest_sha256=pins['data/language-mixture-v1/partial-candidate-manifest.json'],source_files=manifest['source_files'],source_licenses={'stories':manifest['source_licenses']['stories']},counts=actual,training_admitted=False,semantics_verified=False,public_custody_applied=False,seconds=time.monotonic()-start)
  write(OUT/'candidate-manifest.json',receipt);print(json.dumps(receipt['counts']))
 if failure:raise RuntimeError(failure)
if __name__=='__main__':main()
