"""Finite retained-body inventory and bounded streaming adapters; no extraction."""
import json,pathlib,sqlite3,gc
BASE=pathlib.Path(__file__).resolve().parents[1];ROOT=BASE/'m2-intake'
TEXT_EXT={'.txt','.utf8','.xml','.cnxml','.html','.raw'}
JSONL_NAMES={'candidates.jsonl','chapters.jsonl','extracted.jsonl','source-records.jsonl','discovery-sample.jsonl','wikipedia-discovery-sample.jsonl','records.jsonl'}
EXCLUDE_NAMES={'detector-input.txt','changed8-detector-input.txt','retained-texts-for-manual-review.txt'}
def discover():
 entries=[];metadata=[]
 for p in sorted(ROOT.rglob('*')):
  if not p.is_file() or p.is_symlink() or any(p.is_relative_to(ROOT/name) for name in ['gutenberg-four-current-custody-v1','gutenberg-four-current-custody-v2','gutenberg-four-current-custody-v3','wikibooks-three-renewed-custody-v1']):continue
  rel=str(p.relative_to(ROOT))
  if p.relative_to(ROOT).parts[0].startswith('gutenberg-post1900-'):continue # Live/raw discovery only, not current candidate/training/evaluation corpus
  if p.suffix in TEXT_EXT and p.name not in EXCLUDE_NAMES:entries.append({'path':str(p.resolve()),'adapter':'native_or_plain_UTF8_file','scope':'Literal native markup is not rendered; decoded independent source-text aliases are separately included when retained.'})
  elif p.name in JSONL_NAMES:
   adapter='jsonl_external_text_manifest' if p.name=='chapters.jsonl' and p.parent.name in ['gutenberg-novel-prose-nine-markers-v4','gutenberg-novel-prose-seven-joins-v2'] else 'jsonl_text_fields'
   entries.append({'path':str(p.resolve()),'adapter':adapter})
  elif p.suffix=='.parquet' and p.parent==ROOT/'raw':entries.append({'path':str(p.resolve()),'adapter':'parquet_text'})
  elif p.suffix in {'.sqlite','.sqlite3'}:
   db=sqlite3.connect(p.resolve().as_uri()+'?mode=ro',uri=True)
   try:
    for table, in db.execute("select name from sqlite_master where type='table'"):
     cols=[v[1] for v in db.execute('pragma table_info("'+table.replace('"','""')+'")')]
     if 'text' in cols:entries.append({'path':str(p.resolve()),'adapter':'sqlite_text','table':table,'columns':cols})
     elif 'data' in cols and (table in ['rendered','pages'] or 'full-inventory' in rel):entries.append({'path':str(p.resolve()),'adapter':'sqlite_json_data','table':table,'columns':cols})
     else:metadata.append({'path':str(p.resolve()),'table':table,'scope':'METADATA_OR_IDENTITY_HASH_ONLY_NOT_TEXT_SCREENED'})
   finally:db.close()
 for p in sorted((BASE/'gutenberg-novel-prose-v1/chapters').glob('*.txt')):entries.append({'path':str(p.resolve()),'adapter':'native_or_plain_UTF8_file','scope':'Prior retained Austen body variant, same family; not new supply'})
 # Current29 materialized candidate bodies are explicit, not their raw books.
 manifest=ROOT/'gutenberg-post1900-first-complete-units-v1/documents.json'
 for row in json.loads(manifest.read_text())['documents']:
  body=manifest.parent/row['file']
  if str(body.resolve()) not in {e['path'] for e in entries}:entries.append({'path':str(body.resolve()),'adapter':'native_or_plain_UTF8_file','scope':'Exact current post1900 candidate main/note, not discovery raw book.'})
 entries.sort(key=lambda e:(e['path'],e['adapter'],e.get('table','')))
 for e in entries:
  path=pathlib.Path(e['path']);adapter=e['adapter']
  e['required_current_candidate_body_coverage']=(adapter=='sqlite_text' or (adapter=='sqlite_json_data' and e.get('table')=='rendered') or (adapter in ['jsonl_text_fields','jsonl_external_text_manifest'] and path.name not in ['source-records.jsonl','records.jsonl']) or (adapter=='native_or_plain_UTF8_file' and path.suffix in ['.txt','.utf8']))
  e['coverage_role']='CURRENT_OR_RETAINED_CANDIDATE_BODY' if e['required_current_candidate_body_coverage'] else 'OPTIONAL_RAW_ANCESTOR_OR_NATIVE_CONTEXT_NOT_NEW_CLEARANCE_REQUIREMENT'
 return entries,metadata

def texts(obj,prefix='',required_plaintext=False):
 if not isinstance(obj,dict):return
 for k in (['text'] if required_plaintext else ['text','wikitext','html','article_body','articleBody','content']):
  value=obj.get(k)
  if isinstance(value,str):yield prefix+k,value
 # Never recursively mine judgments/metadata, synthesize text, or follow paths.

def stream(entry,check,maxline=16000000,required_paths=None):
 p=pathlib.Path(entry['path']);adapter=entry['adapter']
 if adapter=='native_or_plain_UTF8_file':
  if p.stat().st_size>maxline:yield 'oversize',None,{'coverage_hold':'body_file_exceeds_16MB'};return
  try:text=p.read_bytes().decode('utf8',errors='strict')
  except UnicodeError:yield 'nonUTF8',None,{'coverage_hold':'native_binary_or_nonUTF8_not_interpreted'};return
  yield 'file',text,{'file':str(p)}
 elif adapter in ['jsonl_text_fields','jsonl_external_text_manifest']:
  with p.open('rb') as f:
   n=0
   while True:
    check();line=f.readline(maxline+1)
    if not line:break
    n+=1
    if len(line)>maxline:raise ValueError('JSONL_line_cap_no_silent_skip')
    obj=json.loads(line)
    if adapter=='jsonl_external_text_manifest':
     try:metadata=reference_alias(obj,p,required_paths)
     except (ValueError,KeyError,TypeError,OSError) as e:yield str(n),None,{'coverage_hold':'required_external_text_reference_unresolved:'+str(e)}
     else:yield str(n),None,metadata
     continue
    found=list(texts(obj,required_plaintext=entry['required_current_candidate_body_coverage']))
    for key,t in found:yield str(n)+':'+key,t,{k:obj.get(k) for k in ['source','source_id','family_id','title','url','page_id','revision_id','ebook_ID','split','training_admitted'] if k in obj}
    if not found and entry['required_current_candidate_body_coverage']:yield str(n),None,{'coverage_hold':'required_JSONL_row_missing_null_or_unrecognized_body'}
 elif adapter.startswith('sqlite_'):
  db=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True);db.execute('pragma query_only=ON');db.execute('pragma cache_size=-2048');table=entry['table'];cols=entry['columns']
  try:
   field='text' if adapter=='sqlite_text' else 'data';meta=[x for x in cols if x in ['source_ordinal','page_id','revision_id','family','source_id','row_index','url']];sql='select '+','.join('"'+x+'"' for x in meta+[field])+' from "'+table+'"'
   for n,row in enumerate(db.execute(sql),1):
    check();m=dict(zip(meta,row[:-1]));value=row[-1]
    if not isinstance(value,str):yield str(n),None,{**m,'coverage_hold':'SQLite_body_or_JSON_missing_or_null'};continue
    if len(value.encode())>maxline:yield str(n),None,{**m,'coverage_hold':'SQLite_body_or_JSON_exceeds16MB'};continue
    if adapter=='sqlite_text':yield str(n),value,m
    else:
     obj=json.loads(value)
     if isinstance(obj,dict):m.update({k:obj.get(k) for k in ['family_id','title','url','page_id','revision_id','structural_holds','extracted_text_sha256','training_admitted'] if k in obj})
     found=list(texts(obj,required_plaintext=entry['required_current_candidate_body_coverage']))
     for key,t in found:yield str(n)+':'+key,t,m
     if not found and entry['required_current_candidate_body_coverage']:yield str(n),None,{**m,'coverage_hold':'required_SQLiteJSON_row_missing_null_or_unrecognized_body'}
  finally:db.close()
 elif adapter=='parquet_text':
  import pyarrow.parquet as pq
  pf=pq.ParquetFile(p,memory_map=True,pre_buffer=False);names=pf.schema_arrow.names
  if 'text' not in names:raise ValueError('expected_rawParquet_text_column_missing')
  selected=[x for x in ['text','id','url','title','source','language'] if x in names];n=0
  try:
   for batch in pf.iter_batches(batch_size=1,columns=selected,use_threads=False):
    check()
    if batch.num_rows!=1:raise ValueError('one_row_Arrow_batch_contract')
    obj={name:batch.column(i)[0].as_py() for i,name in enumerate(selected)}
    try:
     n+=1;yield str(n),obj['text'],{k:v for k,v in obj.items() if k!='text'}
    finally:
     del obj,batch
     gc.collect(0)
     import pyarrow as pa
     pa.default_memory_pool().release_unused()
  finally:pf.close()
 else:raise ValueError('unknown_explicit_body_adapter')

def alias_signature(entry,file_digest):
 # Optional rawcontext limits cannot discharge required candidatebody coverage.
 return (file_digest,entry['adapter'],entry.get('table'),entry['required_current_candidate_body_coverage'])

def reference_alias(obj,manifest,required_paths):
 import hashlib,re
 if not isinstance(obj,dict) or not isinstance(obj.get('file'),str):raise ValueError('reference_filename_missing')
 rel=pathlib.PurePosixPath(obj['file'])
 if rel.is_absolute() or '..' in rel.parts or '\\' in obj['file']:raise ValueError('reference_path_unsafe')
 target=manifest.parent.joinpath(*rel.parts)
 if target.is_symlink() or not target.is_file() or not target.resolve().is_relative_to(manifest.parent.resolve()):raise ValueError('reference_missing_or_escaped')
 if required_paths is None or str(target.resolve()) not in required_paths:raise ValueError('referenced_body_not_already_frozen_required_adapter')
 digest=obj.get('sha256');length=obj.get('bytes')
 if not isinstance(digest,str) or not re.fullmatch('[a-f0-9]{64}',digest) or type(length)is not int:raise ValueError('reference_hash_size_missing')
 if target.stat().st_size!=length or hashlib.file_digest(target.open('rb'),'sha256').hexdigest()!=digest:raise ValueError('referenced_file_hash_size_mismatch')
 return {'body_reference_alias':True,'referenced_required_body_path':str(target.resolve()),'referenced_body_SHA256':digest,'referenced_body_bytes':length,'family_id':obj.get('family_id'),'split':obj.get('split'),'training_admitted':obj.get('training_admitted'),'scope':'Metadata-only chapter manifest reconciled to already scheduled exactbody adapter; not an extra missingbody obligation or newdocument'}
