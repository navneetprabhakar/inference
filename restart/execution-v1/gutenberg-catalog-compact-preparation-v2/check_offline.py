"""Lossless compact archive tests only; network and ledger APIs absent."""
import ast,bz2,copy,hashlib,io,json,sqlite3,tempfile
from pathlib import Path
from unittest.mock import patch
import compact as c
cases=[]
RAW=(c.ROOT/'gutenberg-discovery-pilot-v2/metadata.raw').read_bytes();ROW=c.parse_rdf.parse(RAW,'pg1342.rdf')
def good(name,b):assert b,name;cases.append(name)
def refuse(fn):
 try:fn()
 except Exception:return
 raise AssertionError('expected refusal')
original_db=sqlite3.connect('file:'+str((c.ORIGINAL/'catalog.sqlite3').resolve())+'?mode=ro',uri=True)
try:original_payload=original_db.execute('select data from records order by member limit 1').fetchone()[0]
finally:original_db.close()
original_row=json.loads(original_payload);roundtrip=c.pack(original_row)
good('actual_failed_prefix_row_lossless_allfields_and_exact_rawJSONhash',c.unpack(*roundtrip)==original_row and roundtrip[1]==c.sha(original_payload.encode()))
packed=c.pack(ROW);good('actual_native_RDF_all_fields_lossless_roundtrip',c.unpack(*packed)==ROW)
good('rawJSON_and_compressed_hashes_codec_version_bound',c.sha(packed[-1])==packed[2] and packed[3]==c.CODEC and c.sha(json.dumps(ROW,ensure_ascii=True,separators=(',',':')).encode())==packed[1])
good('compression_reduces_actual_native_metadata',len(packed[-1])<packed[0]//2)
for name,index,value in [('compressedhash',2,'0'*64),('rawhash',1,'0'*64),('rawlength',0,packed[0]-1),('codec',3,'unknowncodec')]:
 bad=list(packed);bad[index]=value;refuse(lambda:c.unpack(*bad));cases.append(name+'_tamper_refused')
for name,blob in [('truncated',packed[-1][:-1]),('trailing',packed[-1]+b'junk')]:
 bad=list(packed);bad[-1]=blob;bad[2]=c.sha(blob);refuse(lambda:c.unpack(*bad));cases.append('zlib_'+name+'_even_with_recomputed_compressedhash_refused')
bad=list(packed);bad[0]=c.RAW_JSON_CAP+1;refuse(lambda:c.unpack(*bad));cases.append('JSON_decompression_size_bound')
idx=c.indexes(ROW);good('query_columns_supplement_full_payload',idx[0]==1 and json.loads(idx[1])==['Text'] and json.loads(idx[2])==['en'] and idx[3]==0)
def archive(path,rows):
 out=io.BytesIO()
 with __import__('tarfile').open(fileobj=out,mode='w',format=__import__('tarfile').USTAR_FORMAT) as t:
  for name,raw in rows:
   m=__import__('tarfile').TarInfo(name);m.size=len(raw);t.addfile(m,io.BytesIO(raw))
 path.write_bytes(bz2.compress(out.getvalue()));return path
with tempfile.TemporaryDirectory() as td:
 root=Path(td)
 def run(name,rows):
  out=root/name;out.mkdir();a=archive(root/(name+'.bz2'),rows);stats=c.inventory(a,c.Guards(out,c.clock()));return out,stats
 out,s=run('good',[('pg1342.rdf',RAW)])
 good('full_bzip2_CRC_tar_EOF_integrity_reconciliation',s['full_tar_EOF_verified'] and s['full_bzip2_CRC_EOF_verified'] and s['SQLite_integrity']=='ok' and s['English_Text_metadata_rows']==1 and s['lossless_record_roundtrips']==1)
 d=c.readonly_union([out/'catalog-0.sqlite3',out/'catalog-1.sqlite3']);stored=d.execute('select raw_bytes,raw_hash,packed_hash,codec,payload from records').fetchone();decoded=c.unpack(*stored)
 good('stored_BLOB_preserves_every_current_metadata_field',decoded==ROW and set(decoded)==set(ROW));d.close()
 good('no_compressed_archive_or_expanded_tar_duplicated',not list(out.glob('*.bz2')) and not list(out.glob('*.tar')))
 out,s=run('unknown',[('pg1342.rdf',RAW),('pg999.rdf',b'<unknown/>'),('README',b'catalog note')]);good('invalid_and_unknown_members_explicitheld_not_completeEnglishframe',s['held_potential_records']==1 and s['nonRDF_files']==1 and not s['all_potential_RDF_records_parsed_without_duplicate_ID'])
 out,s=run('duplicate',[('pg1342.rdf',RAW),('copy/pg1342.rdf',RAW)]);d=c.readonly_union([out/'catalog-0.sqlite3',out/'catalog-1.sqlite3']);rows=[c.unpack(*x) for x in d.execute('select raw_bytes,raw_hash,packed_hash,codec,payload from records')];d.close();good('duplicateIDs_retained_both_records_visibleholds',s['duplicate_ebook_ID_groups']==1 and all('duplicate_native_ebook_ID_in_catalog_requires_family_reconciliation' in row['holds'] for row in rows))
 with patch.object(c.archive_reader,'MEMBER_CAP',10):out,s=run('oversize',[('pg1342.rdf',RAW)])
 good('oversize_metadata_member_retains_identity_hash',s['held_potential_records']==1 and s['member_body_bytes']==len(RAW))
 a=archive(root/'corrupt.bz2',[('pg1342.rdf',RAW)]);b=bytearray(a.read_bytes());b[len(b)//2]^=1;a.write_bytes(b);out=root/'corrupt';out.mkdir();refuse(lambda:c.inventory(a,c.Guards(out,c.clock())));cases.append('compressed_CRC_corruption_refused')
 a=archive(root/'junk.bz2',[('pg1342.rdf',RAW)]);a.write_bytes(a.read_bytes()+b'junk');out=root/'junk';out.mkdir();refuse(lambda:c.inventory(a,c.Guards(out,c.clock())));cases.append('compressed_trailing_junk_refused')
 a=archive(root/'tail.bz2',[('pg1342.rdf',RAW)]);a.write_bytes(bz2.compress(bz2.decompress(a.read_bytes())+b'bad tar padding'));out=root/'tail';out.mkdir();refuse(lambda:c.inventory(a,c.Guards(out,c.clock())));cases.append('nonzero_tar_trailing_data_refused')
 a=archive(root/'cap.bz2',[('pg1342.rdf',RAW)]);out=root/'cap';out.mkdir();refuse(lambda:c.inventory(a,c.Guards(out,c.clock(),limits={'decoded_bytes':1024})));cases.append('same4GB_decoded_guard_scaled_boundary')
 out=root/'dbcap';out.mkdir();a=archive(root/'dbcap.bz2',[(f'{i}/pg1342.rdf',RAW) for i in range(200)])
 with patch.object(c,'DB_CAP',65536):refuse(lambda:c.inventory(a,c.Guards(out,c.clock())))
 good('SQLite_maxpage_DBhardbound_before_growth',all(p.stat().st_size<=65536 for p in out.glob('catalog-*.sqlite3')))
 out=root/'headroom';out.mkdir()
 with patch.object(c,'OUTPUT_CAP',2000000),patch.object(c,'HEADROOM',320000):refuse(lambda:c.Guards(out,c.clock()).check(700000))
 cases.append('prewrite_explicit32MB_journal_cache_headroom_scaled')
 refuse(lambda:c.Guards(out,c.clock()-571).check());cases.append('shared570second_worker_deadline')
 good('supervisor_two300MB_RSS1GB_600sec_stops',c.decision(0,0,0,[300000001,0],0,0,10**12,0) and c.decision(0,1000000001,0,[],0,0,10**12,0) and c.decision(600,0,0,[],0,0,10**12,0))
upstream=c.EXEC/'gutenberg-catalog-preparation-v1/catalog.py'
a=upstream.read_text();b=(c.HERE/'archive_reader.py').read_text()
def segment(source,name):return next(ast.get_source_segment(source,n) for n in ast.parse(source).body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name==name)
good('reviewed_strict_archive_functions_and_native_RDF_parser_exactly_reused',all(segment(a,n)==segment(b,n) for n in ['StrictBZ2','tar_members']) and (c.HERE/'parse_rdf.py').read_bytes()==(c.EXEC/'gutenberg-catalog-preparation-v1/parse_rdf.py').read_bytes())

with tempfile.TemporaryDirectory() as td:
 out=Path(td)
 # Force each of three actualmetadata members into its own routing batch.
 a=archive(out/'fixture.bz2',[('pg1342.rdf',RAW),('copy/pg1342.rdf',RAW),('third/pg1342.rdf',RAW)])
 with patch.object(c,'BATCH',1):stats=c.inventory(a,c.Guards(out,c.clock()))
 db=c.readonly_union([out/'catalog-0.sqlite3',out/'catalog-1.sqlite3'])
 try:
  slots=db.execute('select shard,count(*) from members group by shard').fetchall();records=[c.unpack(*x) for x in db.execute('select raw_bytes,raw_hash,packed_hash,codec,payload from records')]
  assert len(slots)==2 and sum(n for _,n in slots)==3 and len(records)==3 and all('duplicate_native_ebook_ID_in_catalog_requires_family_reconciliation' in r['holds'] for r in records)
  refuse(lambda:db.execute('delete from shard0.records'))
 finally:db.close()
 assert not list(out.glob('*.sqlite3-journal')) and all(p.stat().st_size<=300000000 for p in out.glob('catalog-*.sqlite3'))
 cases.append('serial_batched_shards_readonly_union_cross_shard_duplicateholds')
with tempfile.TemporaryDirectory() as td:
 out=Path(td);(out/'catalog-0.sqlite3-journal').write_bytes(b'x');(out/'catalog-1.sqlite3-journal').write_bytes(b'x')
 refuse(lambda:c.Guards(out,c.clock()).check());cases.append('two_active_journals_refused')
 (out/'catalog-1.sqlite3-journal').unlink()
 with patch.object(c,'JOURNAL_CAP',1000),patch.object(c,'HEADROOM',320):refuse(lambda:c.Guards(out,c.clock()).check(800))
 cases.append('single_journal_prewrite_headroom_scaled')

# Offline worker source has no imports or paths to network/IntakeLedger APIs.
for filename in ['compact.py','archive_reader.py']:
 source=(c.HERE/filename).read_text();tree=ast.parse(source);imports=[]
 for n in ast.walk(tree):
  if isinstance(n,ast.Import):imports += [x.name for x in n.names]
  elif isinstance(n,ast.ImportFrom):imports.append(n.module or '')
 assert not any(x in source for x in ['IntakeLedger(','urllib.request','requests.get','socket.socket']) and not any(x in imports for x in ['socket','requests','urllib.request','acquire_sources'])
cases.append('offline_entrypoint_reader_no_network_or_ledger_mutation_path')
# Manifest tests replace only a temporary container, never originalrun evidence.
goodm={'environment':c.environment(),'files_SHA256':{str(p.resolve()):c.file_sha(p) for p in c.bound_paths()}}
with tempfile.TemporaryDirectory() as td:
 path=Path(td)/'manifest.json'
 def verify(m,expected=None):
  path.write_text(json.dumps(m))
  with patch.object(c,'MANIFEST',path):return c.pins(c.file_sha(path) if expected is None else expected)
 verify(goodm);cases.append('parent_digest_exact_inventory_runtime_originalsourcepins')
 for name in ['empty','missing','extra','substitute','runtime']:
  bad=copy.deepcopy(goodm)
  if name=='empty':bad['files_SHA256']={}
  elif name=='missing':bad['files_SHA256'].pop(next(iter(bad['files_SHA256'])))
  elif name=='extra':bad['files_SHA256']['/tmp/unreviewed']='0'*64
  elif name=='substitute':bad['files_SHA256'][next(iter(bad['files_SHA256']))]='0'*64
  else:bad['environment']={}
  refuse(lambda:verify(bad));cases.append('manifest_'+name+'_refused')
 refuse(lambda:verify(goodm,'0'*64));cases.append('changed_manifest_container_rejected_by_parent_digest')
result={'status':'PASS_OFFLINE_COMPACT_ROUNDTRIP_TAMPER_BOUNDARY_NO_TRANSFER','case_count':len(cases),'cases':cases,'network_requests':0,'ledger_mutations':0,'new_admitted_documents':0,'new_admitted_tokens':0}
(c.HERE/'offline-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
