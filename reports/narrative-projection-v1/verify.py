"""Separately implemented exact-row/raw-provenance/token verifier, no builder import.
No semantic-quality or admission claim. Verifies original projection exhaustively.
"""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):os.environ[key]='1'
os.environ['TOKENIZERS_PARALLELISM']='false'
import collections,gc,hashlib,json,pathlib,resource,shutil,signal,sqlite3,sys,time,unicodedata
ROOT=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));from tokenizer import load,ASSETS
D=ROOT/'data/narrative-candidates-v1';OLD=ROOT/'data/language-mixture-v1'
def read(p):return json.loads(p.read_bytes())
def digest(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def must(value,why):
 if not value:raise ValueError(why)
def main():
 os.nice(10);started=time.monotonic()
 def deadline(*args):raise TimeoutError('independent verification wall')
 signal.signal(signal.SIGALRM,deadline);signal.alarm(1200)
 def guard():
  must(not any(p.exists() for p in [ROOT/'runs/STOP',D/'STOP',OLD/'STOP',pathlib.Path(__file__).parent/'STOP']),'STOP');must(shutil.disk_usage(ROOT).free>=20*1024**3,'disk floor');must(time.monotonic()-started<1200,'wall');must(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)<=1536*1024**2,'RSS')
 guard();policy=read(D/'policy.json');manifest=read(D/'candidate-manifest.json');source=read(OLD/'partial-candidate-manifest.json');originalproof=read(OLD/'candidate-verification.json');legacy=read(OLD/'custody.json');quality=read(ROOT/'data/language-mixture-v2/proposed-exclusions.json');recovery=read(ROOT/'reports/language-provenance-recovery-v1/receipt.json')
 must(manifest['state']=='candidate_projection_not_admitted' and manifest['failure'] is None and manifest['training_admitted'] is False,'complete unadmitted projection');must(digest(D/'candidates.sqlite')==manifest['database']['sha256'],'new database hash');must(digest(D/'policy.json')==manifest['policy_sha256'],'policy hash')
 for p,h in policy['pins'].items():guard();must(digest(ROOT/p)==h,'pinned dependency '+p)
 must(digest(OLD/'candidates.sqlite')==source['candidate_database_sha256']==originalproof['candidate_database_sha256']==legacy['candidate_database_sha256'],'original DB identity');must(originalproof['failures']==[] and originalproof['candidate_manifest_sha256']==digest(OLD/'partial-candidate-manifest.json'),'original independent proof');must(legacy['state']=='cleared' and legacy['candidate_manifest_sha256']==digest(OLD/'partial-candidate-manifest.json'),'legacy custody source')
 must(recovery['state']=='PASS_exact_raw_provenance_restored_not_admitted' and recovery['candidate_database_unchanged'],'raw recovery');relocation={x['original_path']:x for x in recovery['restored']}
 excluded=set(legacy['excluded_doc_ids'])|{x['doc_id'] for x in quality};before=collections.Counter();counts=collections.defaultdict(lambda:dict(documents=0,tokens=0));families={};hashes=set();raw_counts=collections.Counter()
 old=sqlite3.connect(f'file:{OLD}/candidates.sqlite?mode=ro',uri=True);new=sqlite3.connect(f'file:{D}/candidates.sqlite?mode=ro',uri=True)
 must(new.execute('pragma integrity_check').fetchone()[0]=='ok','new integrity');must(new.execute('pragma table_info(documents)').fetchall()==old.execute('pragma table_info(documents)').fetchall(),'same schema');must(new.execute("select name from sqlite_master where type='table'").fetchall()==[('documents',)],'table inventory')
 tok=load();cursor=iter(new.execute('select * from documents order by doc_id'));verified=0
 for original in old.execute("select * from documents where source='stories' order by doc_id"):
  before[original[5]+'_documents']+=1;before[original[5]+'_tokens']+=original[6]
  if original[0] in excluded:continue
  guard();row=next(cursor,None);must(row==original,'exact eligible original row/provenance/split/text mismatch');did,src,source_index,source_row,family,split,n,norm,raw,url,text=row
  must(src=='stories' and split in ['train','validation'],'source/split');must(families.setdefault(family,split)==split,'family split');must(norm not in hashes,'duplicate normalized document');hashes.add(norm)
  must(hashlib.sha256(text.encode()).hexdigest()==raw,'raw text digest');normalized=' '.join(unicodedata.normalize('NFKC',text).casefold().split());must(hashlib.sha256(normalized.encode()).hexdigest()==norm,'normalized digest')
  ids=tok.encode(text).ids;must(len(ids)>0 and len(ids)+1==n and all(0<=i<50256 for i in ids),'GPT2 count/unique terminal EOT contract');counts[split]['documents']+=1;counts[split]['tokens']+=len(ids)+1;raw_counts[source_index]+=1;verified+=1
 must(next(cursor,None) is None,'extra projection rows');must(dict(counts)==policy['expected']==manifest['counts'],'all projected counts');must(verified==172544,'complete eligible inventory')
 must(manifest['source_files']==source['source_files'] and manifest['source_licenses']=={'stories':source['source_licenses']['stories']},'original source metadata')
 # Independently bind every retained story directly to its recovered raw JSON row.
 checked_raw=0
 for index,count in raw_counts.items():
  guard();entry=source['source_files'][index];r=relocation[entry['path']];p=pathlib.Path(r['recovered_path']);must(p.is_relative_to(ROOT/'data/language-source-recovery-v1'),'explicit fresh cache only');must(r['sha256']==entry['sha256'] and r['bytes']==entry['bytes'] and digest(p)==entry['sha256'],'source member identity')
  rows=read(p)
  for did,position,text in new.execute('select doc_id,source_row,text from documents where source_file=?',(index,)):
   guard();must(0<=position<len(rows) and rows[position]['story']==text,'retained source row text');must(did==p.name+':'+str(position),'source row document ID');checked_raw+=1
  del rows;gc.collect()
 must(checked_raw==verified,'complete raw source correspondence');must(digest(D/'candidates.sqlite')==manifest['database']['sha256'],'new database unchanged');must(digest(OLD/'candidates.sqlite')==source['candidate_database_sha256'],'original database unchanged')
 old.close();new.close();signal.alarm(0)
 result=dict(state='PASS_independent_exact_projection_not_admitted',scope='Separately implemented exhaustive exact original-row comparison, recovered raw-row correspondence, text hashes and retokenization; not independent semantic quality assessment.',database_sha256=digest(D/'candidates.sqlite'),manifest_sha256=digest(D/'candidate-manifest.json'),policy_sha256=digest(D/'policy.json'),source_database_sha256=source['candidate_database_sha256'],verified_rows=verified,verified_raw_rows=checked_raw,failures=[],counts=dict(counts),original_story_counts=dict(before),original_legacy_custody_sha256=digest(OLD/'custody.json'),v2_exclusions_sha256=digest(ROOT/'data/language-mixture-v2/proposed-exclusions.json'),recovery_receipt_sha256=digest(ROOT/'reports/language-provenance-recovery-v1/receipt.json'),verifier_sha256=digest(pathlib.Path(__file__)),tokenizer=ASSETS,seconds=time.monotonic()-started,training_admitted=False,semantics_verified=False,public_custody_applied=False,pending=['Root public-development supplement exclusion union','Root narrative quality review','Separate deterministic packing/admission/training allocation'])
 with (D/'candidate-verification.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
 print(json.dumps({k:result[k] for k in ['state','verified_rows','counts','seconds']}))
if __name__=='__main__':main()
