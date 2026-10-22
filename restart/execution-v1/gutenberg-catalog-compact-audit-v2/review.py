import ast,bz2,hashlib,io,json,os,pathlib,sqlite3,sys,tarfile,tempfile
from unittest.mock import patch
D=pathlib.Path(__file__).resolve().parent;S=D.parent/'gutenberg-catalog-compact-preparation-v2';V1=S.with_name('gutenberg-catalog-compact-preparation-v1');sys.path.insert(0,str(S));import compact as c
h=lambda p:hashlib.file_digest(p.open('rb'),'sha256').hexdigest();EXPECTED='659f01bfed7f887306f44f634456d1c75f57596e4cc7f4586b4f04dc9135db87';assert h(S/'ready.json')=='a23e98bada700b68606bac065d3b19bda8e45f892a8573dd4f03fa962f45451c' and h(S/'manifest.json')==EXPECTED and h(S/'compact.py')=='12a715dfbbcb5ec427cf684d9b7edcd83680400aa6140ff9dca124710dd2305b';c.pins(EXPECTED);inputs={str(p):h(p) for p in S.iterdir() if p.is_file()};cases=[]
orig=pathlib.Path.write_text
def route(self,data,*a,**kw):return orig(D/'offline-controls.json' if self==S/'offline-checks.json' else self,data,*a,**kw)
with patch.object(pathlib.Path,'write_text',route):exec(compile((S/'check_offline.py').read_bytes(),str(S/'check_offline.py'),'exec'),{'__name__':'__audit_controls__'})
def refuse(fn):
 try:fn()
 except ValueError:return
 raise AssertionError('Expected ValueError')
# No codec/parser/tar-reader drift from independently reviewed v1.
for name in ['parse_rdf.py','archive_reader.py']:assert (S/name).read_bytes()==(V1/name).read_bytes()
def segment(path,name):
 source=path.read_text();return next(ast.get_source_segment(source,n) for n in ast.parse(source).body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name==name)
for name in ['pack','unpack','indexes','storage']:assert segment(S/'compact.py',name)==segment(V1/'compact.py',name)
cases.append('source_parser_archive_reader_lossless_codec_indexes_and_storage_logic_unchanged')
with tempfile.TemporaryDirectory() as td:
 p=pathlib.Path(td)/'manifest';p.write_text(json.dumps({'environment':c.environment(),'files_SHA256':{}}))
 with patch.object(c,'MANIFEST',p):refuse(lambda:c.pins(EXPECTED));refuse(lambda:c.pins(h(p)))
 cases.append('old_empty_manifest_exploit_refused_with_original_and_recomputed_digest')
with patch.object(sys,'argv',['compact','--manifest-sha256','0'*64,'--execute']),patch.object(c,'execute',side_effect=AssertionError('Must not create outputs')):refuse(c.main)
with patch.dict(os.environ,{'PGCOMPACT_PARENT_PID':str(os.getppid()),'PGCOMPACT_SHARED_START':str(c.clock())}),patch.object(c,'inventory',side_effect=AssertionError('Must not scan')):refuse(lambda:c.worker('0'*64))
cases.append('main_and_worker_manifest_refusal_before_mutation')
with patch.object(sys,'argv',['compact','--manifest-sha256',EXPECTED,'--worker']),patch.object(c,'worker',return_value=None) as worker:c.main();worker.assert_called_once_with(EXPECTED)
cases.append('main_exact_digest_forwarding')
real=c.subprocess.Popen;captured={}
def dummy(command,**kw):
 if command[0]=='/bin/ps':return real(command,**kw)
 captured['command']=command;captured['env']=kw['env'];return real([sys.executable,'-c','import time;time.sleep(30)'],**kw)
out=D/'offline-supervisor-dummy'
with patch.object(c,'DEST',out),patch.object(c,'EXTERNAL_SECONDS',.1),patch.object(c,'storage',return_value=0),patch.object(c.subprocess,'Popen',side_effect=dummy):
 try:c.execute(EXPECTED)
 except SystemExit as e:assert e.code==1
assert captured['command'][-2:]==['--manifest-sha256',EXPECTED] and captured['env']['PGCOMPACT_PARENT_PID']==str(os.getpid());sup=json.loads((out/'supervisor-result.json').read_text());assert sup['status']=='FAILED' and sup['reason']=='external600secondcap' and not sup['retry'];cases.append('actual_external_dummy_watchdog_and_same_digest_child_argv')
# Actual native RDF metadata, synthetic small archive: directories/nonRDF count
# toward routing batch, each native ordinal/record is stored exactly once.
raw=(c.ROOT/'gutenberg-discovery-pilot-v2/metadata.raw').read_bytes()
with tempfile.TemporaryDirectory() as td:
 root=pathlib.Path(td);archive=root/'source.bz2';out=root/'output';out.mkdir();stream=io.BytesIO();expected={}
 with tarfile.open(fileobj=stream,mode='w',format=tarfile.USTAR_FORMAT) as t:
  m=tarfile.TarInfo('catalog/');m.type=tarfile.DIRTYPE;t.addfile(m)
  for pos,eid in enumerate([101,102,103,104,105],2):
   body=raw.replace(b'1342',str(eid).encode());name=f'catalog/pg{eid}.rdf';m=tarfile.TarInfo(name);m.size=len(body);t.addfile(m,io.BytesIO(body));expected[pos]=c.parse_rdf.parse(body,name)
  m=tarfile.TarInfo('README');m.size=4;t.addfile(m,io.BytesIO(b'note'))
 archive.write_bytes(bz2.compress(stream.getvalue()))
 with patch.object(c,'BATCH',2):stats=c.inventory(archive,c.Guards(out,c.clock()))
 db=c.readonly_union([out/'catalog-0.sqlite3',out/'catalog-1.sqlite3']);members=db.execute('select ordinal,count(*) from members group by ordinal order by ordinal').fetchall();assert members==[(i,1) for i in range(1,8)]
 records=db.execute('select shard,member,ebook_ID,English_Text,types,languages,missing_mask,missingness,hold_count,raw_bytes,raw_hash,packed_hash,codec,payload from records order by member').fetchall();assert len(records)==5 and {x[0] for x in records}=={0,1}
 for slot,member,eid,*rest in records:row=c.unpack(*rest[6:]);assert row==expected[member] and eid==row['ebook_ID'] and tuple(rest[:6])==c.indexes(row)
 try:db.execute('delete from shard0.members')
 except sqlite3.OperationalError:pass
 else:raise AssertionError('readonly union writable')
 db.close();assert stats['members']==7 and stats['parsed_ebook_records']==5 and stats['directories']==1 and stats['nonRDF_files']==1 and stats['full_tar_EOF_verified'] and stats['full_bzip2_CRC_EOF_verified'];assert not list(out.glob('*-journal'));cases.append('exact_once_native_member_record_routing_over_both_shards_with_directory_and_nonRDF_batches')
 for p in out.glob('catalog-*.sqlite3'):
  db=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True);assert db.execute('pragma page_size').fetchone()[0]==65536;assert db.execute('pragma integrity_check').fetchone()[0]=='ok';db.close()
 cases.append('readonly_union_query_columns_payload_and_both_64KiB_shard_integrity')
 # Force duplicate native IDs into opposite routing batches; both held.
 out=root/'duplicates';out.mkdir();stream=io.BytesIO()
 with tarfile.open(fileobj=stream,mode='w',format=tarfile.USTAR_FORMAT) as t:
  for name in ['first/pg1342.rdf','second/pg1342.rdf']:
   m=tarfile.TarInfo(name);m.size=len(raw);t.addfile(m,io.BytesIO(raw))
 archive=root/'duplicate.bz2';archive.write_bytes(bz2.compress(stream.getvalue()))
 with patch.object(c,'BATCH',1):stats=c.inventory(archive,c.Guards(out,c.clock()))
 db=c.readonly_union([out/'catalog-0.sqlite3',out/'catalog-1.sqlite3']);rs=db.execute('select shard,raw_bytes,raw_hash,packed_hash,codec,payload from records').fetchall();assert {x[0] for x in rs}=={0,1} and stats['duplicate_ebook_ID_groups']==1 and not stats['all_potential_RDF_records_parsed_without_duplicate_ID'];assert all('duplicate_native_ebook_ID_in_catalog_requires_family_reconciliation' in c.unpack(*x[1:])['holds'] for x in rs);db.close();cases.append('cross_shard_duplicate_ID_rejects_complete_selection_frame_and_holds_every_copy')
assert (c.DB_CAP,c.AGG_DB_CAP,c.JOURNAL_CAP,c.PAGE_SIZE,c.BATCH,c.OUTPUT_CAP,c.DECODED_CAP,c.RSS_CAP,c.EXTERNAL_SECONDS,c.WORKER_SECONDS)==(300000000,600000000,300000000,65536,100,1000000000,4000000000,1000000000,600,570);cases.append('all_reviewed_two_shard_caps_exact')
# No HTTP or global ledger path introduced in any of the three local modules.
for name in ['compact.py','archive_reader.py','parse_rdf.py']:
 tree=ast.parse((S/name).read_text());imports=[]
 for n in ast.walk(tree):
  if isinstance(n,ast.Import):imports.extend(x.name for x in n.names)
  elif isinstance(n,ast.ImportFrom):imports.append(n.module)
 assert not any(x and (x in ['urllib','urllib.request'] or x.split('.')[0] in ['requests','socket','acquire_sources']) for x in imports)
cases.append('offline_entrypoint_reader_parser_no_HTTP_or_ledger_imports')
assert all(h(pathlib.Path(n))==v for n,v in inputs.items());c.pins(EXPECTED);result={'status':'PASS_FOCUSED_V2_CAPACITY_PROFILE_REVIEW_NO_CONFIRMED_BLOCKER','external_manifest_SHA256':EXPECTED,'readiness_SHA256':inputs[str(S/'ready.json')],'baseline_controls':json.loads((D/'offline-controls.json').read_text())['case_count'],'independent_cases':cases,'preparation_and_all_original_pinned_inputs_unchanged':True,'input_SHA256':inputs,'capacity_assessment':'Independent actual-prefix projection audit supports only a bounded attempt:80k+25percent narrowly fits600MB;100k+25percent exceeds600MB. Actual full record count and metadata width unknown.','capacity_projection_audit':str(D.parent/'gutenberg-catalog-storage-audit-v1/review.json'),'selection_semantics':'Duplicate IDs are preserved with holds in all shards and prohibit complete selection-frame claim; complete source identity inventory can still be recorded.','actual_full_catalog_parsed':False,'network_requests':0,'ledger_mutations':0};(D/'review.json').write_text(json.dumps(result,indent=2)+'\n');(D/'manifest.json').write_text(json.dumps({str(p.relative_to(D)):h(p) for p in D.rglob('*') if p.is_file() and p.name!='manifest.json'},indent=2)+'\n');print(json.dumps({'status':result['status'],'baseline_controls':result['baseline_controls'],'independent_cases':len(cases),'manifest_SHA256':h(D/'manifest.json')}))
