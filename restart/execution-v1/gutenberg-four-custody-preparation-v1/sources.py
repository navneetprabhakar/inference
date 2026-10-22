"""Finite retained-body inventory and bounded streaming adapters; no extraction."""
import json,pathlib,sqlite3
BASE=pathlib.Path(__file__).resolve().parents[1];ROOT=BASE/'m2-intake'
TEXT_EXT={'.txt','.utf8','.xml','.cnxml','.html','.raw'}
JSONL_NAMES={'candidates.jsonl','chapters.jsonl','extracted.jsonl','source-records.jsonl','discovery-sample.jsonl','wikipedia-discovery-sample.jsonl','records.jsonl'}
EXCLUDE_NAMES={'detector-input.txt','changed8-detector-input.txt','retained-texts-for-manual-review.txt'}
def discover():
 entries=[];metadata=[]
 for p in sorted(ROOT.rglob('*')):
  if not p.is_file() or p.is_symlink() or p.is_relative_to(ROOT/'gutenberg-four-current-custody-v1'):continue
  rel=str(p.relative_to(ROOT))
  if p.relative_to(ROOT).parts[0].startswith('gutenberg-post1900-'):continue # Live/raw discovery only, not current candidate/training/evaluation corpus
  if p.suffix in TEXT_EXT and p.name not in EXCLUDE_NAMES:entries.append({'path':str(p.resolve()),'adapter':'native_or_plain_UTF8_file','scope':'Literal native markup is not rendered; decoded independent source-text aliases are separately included when retained.'})
  elif p.name in JSONL_NAMES:entries.append({'path':str(p.resolve()),'adapter':'jsonl_text_fields'})
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
 for e in entries:
  path=pathlib.Path(e['path']);adapter=e['adapter']
  e['required_current_candidate_body_coverage']=(adapter=='sqlite_text' or (adapter=='sqlite_json_data' and e.get('table')=='rendered') or (adapter=='jsonl_text_fields' and path.name not in ['source-records.jsonl','records.jsonl']) or (adapter=='native_or_plain_UTF8_file' and path.suffix in ['.txt','.utf8']))
  e['coverage_role']='CURRENT_OR_RETAINED_CANDIDATE_BODY' if e['required_current_candidate_body_coverage'] else 'OPTIONAL_RAW_ANCESTOR_OR_NATIVE_CONTEXT_NOT_NEW_CLEARANCE_REQUIREMENT'
 return entries,metadata

def texts(obj,prefix=''):
 if not isinstance(obj,dict):return
 for k in ['text','wikitext','html','article_body','articleBody','content']:
  value=obj.get(k)
  if isinstance(value,str):yield prefix+k,value
 # Never recursively mine judgments/metadata, synthesize text, or follow paths.

def stream(entry,check,maxline=16000000):
 p=pathlib.Path(entry['path']);adapter=entry['adapter']
 if adapter=='native_or_plain_UTF8_file':
  if p.stat().st_size>maxline:yield 'oversize',None,{'coverage_hold':'body_file_exceeds_16MB'};return
  try:text=p.read_bytes().decode('utf8',errors='strict')
  except UnicodeError:yield 'nonUTF8',None,{'coverage_hold':'native_binary_or_nonUTF8_not_interpreted'};return
  yield 'file',text,{'file':str(p)}
 elif adapter=='jsonl_text_fields':
  with p.open('rb') as f:
   n=0
   while True:
    check();line=f.readline(maxline+1)
    if not line:break
    n+=1
    if len(line)>maxline:raise ValueError('JSONL_line_cap_no_silent_skip')
    obj=json.loads(line)
    for key,t in texts(obj):yield str(n)+':'+key,t,{k:obj.get(k) for k in ['source','source_id','family_id','title','url','page_id','revision_id','ebook_ID','split','training_admitted'] if k in obj}
 elif adapter.startswith('sqlite_'):
  db=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True);db.execute('pragma query_only=ON');db.execute('pragma cache_size=-2048');table=entry['table'];cols=entry['columns']
  try:
   field='text' if adapter=='sqlite_text' else 'data';meta=[x for x in cols if x in ['source_ordinal','page_id','revision_id','family','source_id','row_index','url']];sql='select '+','.join('"'+x+'"' for x in meta+[field])+' from "'+table+'"'
   for n,row in enumerate(db.execute(sql),1):
    check();m=dict(zip(meta,row[:-1]));value=row[-1]
    if len(value.encode())>maxline:yield str(n),None,{**m,'coverage_hold':'SQLite_body_or_JSON_exceeds16MB'};continue
    if adapter=='sqlite_text':yield str(n),value,m
    else:
     obj=json.loads(value);m.update({k:obj.get(k) for k in ['family_id','title','url','page_id','revision_id','structural_holds','extracted_text_sha256','training_admitted'] if k in obj})
     for key,t in texts(obj):yield str(n)+':'+key,t,m
  finally:db.close()
 elif adapter=='parquet_text':
  import pyarrow.parquet as pq
  pf=pq.ParquetFile(p);names=pf.schema_arrow.names
  if 'text' not in names:raise ValueError('expected_rawParquet_text_column_missing')
  selected=[x for x in ['text','id','url','title','source','language'] if x in names];n=0
  for batch in pf.iter_batches(batch_size=32,columns=selected):
   check()
   for obj in batch.to_pylist():
    n+=1;yield str(n),obj['text'],{k:v for k,v in obj.items() if k!='text'}
 else:raise ValueError('unknown_explicit_body_adapter')

def alias_signature(entry,file_digest):
 # Optional rawcontext limits cannot discharge required candidatebody coverage.
 return (file_digest,entry['adapter'],entry.get('table'),entry['required_current_candidate_body_coverage'])
