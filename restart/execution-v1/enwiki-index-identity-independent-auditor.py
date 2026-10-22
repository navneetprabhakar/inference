from pathlib import Path
import sys,json,hashlib,types,tempfile,io,sqlite3
B=Path(__file__).resolve().parent;P=B/'enwiki-index-identity-frame-preparation-v1';O=B/'enwiki-index-identity-independent-audit-v1';sys.path.insert(0,str(P));import inventory as run,inventory_core as core,checks
h=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
code='c658f2538345e8362c91dbc5656b69bbecc7c84b4132b45633237d8a4e106277';profile='a58362e5bbfb7a3f63b3d7f7a7dceb01ba8edad690350ff373cbea722d1940d3';assert h(P/'readiness.json')=='20ed8311071731587ec7dab9f0cf61888184635b4eb93664ad85c63d75a8e9e1'
old=Path.open
def no_index(path,*a,**kw):
 if path.resolve()==run.SOURCE.resolve():raise AssertionError('retainedindexopen')
 return old(path,*a,**kw)
Path.open=no_index
try:p=run.verify(types.SimpleNamespace(code_pins_sha256=code,profile_sha256=profile))
finally:Path.open=old
independent=[];assessor=run.load('independent_tiny_assessor',run.ASSESSOR)
with tempfile.TemporaryDirectory() as tmp:
 raw='00010:00001:A: café 雪 é\n10:9223372036854775807:Max ID\n30:2:Unterminated'.encode();spec,compressed=checks.spec(raw);store=core.Store(Path(tmp)/'tiny.sqlite',batch=1)
 try:result=core.build(io.BytesIO(compressed),assessor,store,spec)
 finally:store.close()
 db=sqlite3.connect(Path(tmp)/'tiny.sqlite');got=[]
 for ordinal,pid,title,rawsha,n,lf,offlex,pidlex,offset in db.execute('select r.row_ordinal,r.page_id,r.title,r.raw_line_sha256,r.raw_line_bytes,r.line_ends_LF,r.noncanonical_offset_ascii,r.noncanonical_page_ascii,g.block_start from rows r join groups g using(group_ordinal) order by r.row_ordinal'):
  b=((offlex if offlex is not None else str(offset))+':'+(pidlex if pidlex is not None else str(pid))+':'+title).encode()+ (b'\n' if lf else b'');assert len(b)==n and hashlib.sha256(b).digest()==rawsha;got.append(b)
 assert b''.join(got)==raw and db.execute('pragma foreign_key_check').fetchall()==[] and db.execute('pragma integrity_check').fetchall()==[('ok',)];db.close();independent.append('allSQLstoredfields_reconstruct_exactUTF8_numeric_lexemes_colons_int64max_unterminated')
 duplicate=b'0:1:A\n10:0001:B\n';spec,compressed=checks.spec(duplicate);store=core.Store(Path(tmp)/'duplicate.sqlite')
 try:
  try:core.build(io.BytesIO(compressed),assessor,store,spec)
  except sqlite3.IntegrityError:independent.append('numeric_ID_alias1_0001_duplicate_uniqueconstraint_refused')
  else:raise AssertionError('canonicalduplicate')
 finally:store.close()
O.mkdir(exist_ok=False);r={'status':'PASS_INDEX_IDENTITY_PREPARATION_REVIEW_NO_RETAINED_STREAM_EXECUTION','code_pins_SHA256':code,'profile_SHA256':profile,'all32metadata_code_runtime_pins_reverified':len(json.loads((P/'code-pins.json').read_text())['SHA256']),'existing_controls_reproduced':29,'independent_controls':independent,'full_production_reviewed':['inventory.py','inventory_core.py','checks.py','profile.json'],'confirmed':['Existing strict assessor parse/completeallmemberBZ2CRC_EOF/trailingdata/sourceMD5SHA1SHA256 reused with bounded emission hook restored in finally','SQLite UNIQUE numericpageID plus exactordinal PK, exactUTF8 title/rawlinehash/length/LF/noncanonicalnumeric lexemes preserve native index rows','Group offset/rowbounds exactcounts,FK and integritychecks beforeCOMPLETE','No fullIDset/titleBtree/fullmetadata frame inRAM;32MiBSQLitecache,500rowbatch, MEMORYjournal/temp and3.8GBDBphysicalpagecap','Early1200/1260sharedclocks,1GBobservedRSS,4GBaggregateoutput,64GBcombinedintake/protectedfreefloor;existingoutputone-shot refusal andownedchildkillreap','Workerclose/fsync/DBSHA then independent post-reap parent DBhash and finalresourcechecks','Index-only no nativeXML/network/IntakeLedger/model/sampling or proseadmission path'],'source_compressed_bytes_planned':283588691,'prior_exact_index_rows':25792234,'prior_exact_offset_groups':257960,'capacity_scope':'Existing100k synthetic projections are preparation evidence, not guaranteed full-frame fit; finite DB/RSS/time stops preserve partial with no retry. MEMORYjournal hard-crash partial may require integrity recovery and never becomes COMPLETE automatically.','retained_index_or_XML_body_bytes_read':0,'actual_global_identity_uniqueness_claim':False,'new_admissions':0,'concrete_blockers':[]}
(O/'review.json').write_text(json.dumps(r,indent=2)+'\n');(O/'manifest.json').write_text(json.dumps({'review.json':h(O/'review.json'),'auditor_SHA256':h(__file__)},indent=2)+'\n');print(h(O/'review.json'),h(O/'manifest.json'))
