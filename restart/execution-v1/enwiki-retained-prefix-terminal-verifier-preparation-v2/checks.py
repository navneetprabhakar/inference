"""Synthetic-only verifier probes; never opens retained index or native data."""
import tempfile,pathlib,json,hashlib,sqlite3,sys
import core
checks=[]
def test(n,f):f();checks.append(n)
def must(f):
 try:f()
 except Exception:return
 raise AssertionError('must refuse')
def good():
 p=core.RevisionProof(3,5);p.page(1,2,50);p.page(2,0,None);p.page(3,1,10);p.seal();p.revision(10,3,1);p.revision(50,1,1);p.revision(90,1,2);assert p.finish()['observed']==3
 p=core.RevisionProof(2,2);p.page(1,1,10);p.page(2,1,10);p.seal();p.revision(10,1,1);p.revision(10,2,1);assert p.finish()['observed']==2
test('revision_bijection_outofpageorder_and_shared_revisionID_occurrences',good)
def wrong(kind):
 p=core.RevisionProof(2,5);p.page(1,2,10);p.page(2,1,20);p.seal()
 if kind=='missing':p.revision(10,1,1);must(p.finish)
 elif kind=='duplicate':p.revision(10,1,1);must(lambda:p.revision(11,1,1))
 elif kind=='ordinal':must(lambda:p.revision(20,2,2))
 elif kind=='first':must(lambda:p.revision(11,1,1))
 elif kind=='page':must(lambda:p.revision(1,3,1))
 elif kind=='PK':p.revision(20,2,1);must(lambda:p.revision(10,1,1))
for k in ['missing','duplicate','ordinal','first','page','PK']:test('refuse_revision_'+k,lambda k=k:wrong(k))
for count,first in [(0,1),(1,None),(10001,1),(-1,None)]:test('count_first_bound_'+str(count),lambda c=count,f=first:must(lambda:core.RevisionProof(1,30000).page(1,c,f)))
def tight():
 p=core.RevisionProof(1,1);must(lambda:p.page(2,1,1));must(lambda:p.page(1,2,1));p.page(1,1,1);p.seal();must(lambda:p.page(2,0,None))
test('revision_caps_and_seal_not_expandable',tight)
def footprint():
 p=core.RevisionProof(100000,100000)
 for n in range(1,100001):p.page(n,1,n)
 p.seal()
 for n in range(1,100001):p.revision(n,n,1)
 x=p.finish();assert x['array_and_bitset_bytes']==100001*14+12500 and x['observed']==100000
test('100k_revision_linear_arrays_exact14Bperpage_plus_bitset',footprint)
def json_probe():
 must(lambda:core.loads('{"k":1,"k":2}'));must(lambda:core.loads('{"v":NaN}'))
 with tempfile.TemporaryDirectory() as z:
  p=pathlib.Path(z)/'f';p.write_bytes(b'{}\n{}');must(lambda:list(core.json_lines(p,8,lambda:None)));p.write_bytes(b'{"long":"value"}\n');must(lambda:list(core.json_lines(p,8,lambda:None)))
test('bounded_JSONL_complete_lines_duplicatekeys_constants_refused',json_probe)
# Complete tiny stored-output/index fixture, independent of native parser.
def stored_fixture(folder,mutate=lambda db,idx,receipts,bridge,producer:None):
 from pathlib import Path
 out=Path(folder);db=sqlite3.connect(out/'frame.sqlite');idx=sqlite3.connect(out/'index.sqlite')
 db.executescript('CREATE TABLE pages(row_ordinal INTEGER PRIMARY KEY,page_id INTEGER,first_revision_id INTEGER,namespace INTEGER,flags INTEGER,model_code INTEGER,revision_count INTEGER,main_text_bytes INTEGER,group_decoded_start INTEGER,raw_XML_bytes INTEGER,raw_SHA256 BLOB);CREATE TABLE groups(group_ordinal INTEGER PRIMARY KEY,compressed_start INTEGER,compressed_end_exclusive INTEGER,decoded_bytes INTEGER,first_page_ordinal INTEGER,last_page_ordinal INTEGER,page_count INTEGER,raw_SHA256 BLOB);CREATE TABLE revisions(revision_id INTEGER,page_ordinal INTEGER,revision_ordinal INTEGER,PRIMARY KEY(revision_id,page_ordinal,revision_ordinal),FOREIGN KEY(page_ordinal) REFERENCES pages(row_ordinal)) WITHOUT ROWID;')
 idx.executescript('CREATE TABLE groups(group_ordinal INTEGER PRIMARY KEY,block_start INTEGER,block_end_exclusive INTEGER,first_row INTEGER,last_row INTEGER,row_count INTEGER);CREATE TABLE rows(row_ordinal INTEGER PRIMARY KEY,page_id INTEGER,title TEXT,raw_line_sha256 BLOB,raw_line_bytes INTEGER,line_ends_LF INTEGER,noncanonical_offset_ascii TEXT,noncanonical_page_ascii TEXT,group_ordinal INTEGER);')
 titles=['A&amp;B','C','D'];values=[(1,1,10,0,0,1,1,1,0,2,hashlib.sha256(b'p1').digest()),(2,2,20,0,16,1,2,1,2,2,hashlib.sha256(b'p2').digest()),(3,3,None,0,40,0,0,-1,0,2,hashlib.sha256(b'p3').digest())];db.executemany('insert into pages values(?,?,?,?,?,?,?,?,?,?,?)',values);db.executemany('insert into revisions values(?,?,?)',[(10,1,1),(20,2,1),(21,2,2)])
 header=b'<mediawiki>';headerreceipt={'decoded_bytes':len(header),'decoded_SHA256':hashlib.sha256(header).hexdigest(),'compressed_bytes':570,'CRC_EOF_members':1,'trailing_absent':True};(out/'original-header.xml').write_bytes(header);(out/'header-receipt.json').write_text(json.dumps(headerreceipt));receipts=[];decoded=len(header);revs=0
 bridge={'expected_SQL_fields':[],'expected_groups':[]}
 for v in values:
  ordinal,pid,rev,ns,flags,model,rc,tb,span,length,sha=v;bridge['expected_SQL_fields'].append({'page_ID':pid,'first_revision_ID':rev,'namespace':ns,'revision_count':rc,'main_text_UTF8_bytes':tb,'group_decoded_start':span,'raw_XML_bytes':length,'raw_SHA256':sha.hex()})
 for g,first,last in [(1,1,2),(2,3,3)]:
  begin=570+(g-1)*100;end=begin+100;n=last-first+1;ghash=hashlib.sha256(('g'+str(g)).encode()).digest();db.execute('insert into groups values(?,?,?,?,?,?,?,?)',(g,begin,end,100,first,last,n,ghash));idx.execute('insert into groups values(?,?,?,?,?,?)',(g,begin,end,first,last,n));rawhash=hashlib.sha256();semhash=hashlib.sha256();linehash=hashlib.sha256();refs=0
  for ordinal in range(first,last+1):
   title=titles[ordinal-1];line=f'{begin}:{ordinal}:{title}\n'.encode();idx.execute('insert into rows values(?,?,?,?,?,?,?,?,?)',(ordinal,ordinal,title,hashlib.sha256(line).digest(),len(line),1,None,None,g));rawhash.update(core.transcript([ordinal,ordinal,title]));st=title.replace('&amp;','&');refs+=title.count('&amp;');semhash.update(core.transcript([ordinal,ordinal,st]));linehash.update(line)
  revs+=sum(v[6] for v in values[first-1:last]);receipts.append({'group_ordinal':g,'compressed_start':begin,'compressed_end_exclusive':end,'compressed_bytes':100,'decoded_global_start':decoded,'decoded_bytes':100,'decoded_SHA256':ghash.hex(),'compressed_SHA256':'0'*64,'native_pages':n,'CRC_EOF_members':1,'trailing_absent':True,'raw_index_lines_SHA256':linehash.hexdigest(),'raw_index_identity_SHA256':rawhash.hexdigest(),'actual_native_identity_SHA256':semhash.hexdigest(),'frozen_index_identity_SHA256':semhash.hexdigest(),'title_decoder_SHA256':'1'*64,'references_decoded_once':refs,'durable':{'durable_groups':g,'durable_pages':last,'durable_revision_occurrences':revs}});decoded+=100
 idx.execute('insert into groups values(3,770,800,4,4,1)');prod={'counts':{'pages':3,'groups':2,'revision_occurrences':3,'ns0_nonredirect':3,'namespace_counts':[[0,3]],'flag_counts':[[0,1],[16,1],[40,1]]},'decoded_prefix_bytes':decoded,'compressed_prefix_bytes_read':770,'exceptions':{'events':0,'bytes':0,'ordered_exception_SHA256':hashlib.sha256(b'').hexdigest()}}
 mutate(db,idx,receipts,bridge,prod);db.commit();idx.commit();db.close();idx.close();rb=b''.join(core.transcript(x) for x in receipts);(out/'group-receipts.jsonl').write_bytes(rb);(out/'exceptions.jsonl').write_bytes(b'');prod['exceptions'].update(group_receipt_count=2,group_receipt_bytes=len(rb),ordered_group_receipts_SHA256=hashlib.sha256(rb).hexdigest());(out/'codec.json').write_text(json.dumps({'models':[{'code':1,'model':'wikitext','format':'text/x-wiki'}]}));(out/'header-summary.json').write_text(json.dumps({'scope':'PREFIX_ONLY_EXTERNAL_GROUP_INDEX_PROOF_REQUIRED','root_holds':[],'siteinfo_base_status':'VERIFIED_HTTPS_ENWIKI_BASE','pages':3,'raw':{'actual_root_closed':False,'global_XML_validity':False,'decoded_bytes':decoded}}))
 def decoder(t):return {'semantic_expected_title':t.replace('&amp;','&'),'references_decoded_once':t.count('&amp;')}
 return core.verify_frame({'max_group_compressed_bytes':1000,'source_prefix_bytes':775},prod,{'groups':2,'rows':3,'header_bytes':570,'compressed_prefix_end_exclusive':770},out/'index.sqlite',out,decoder,'1'*64,bridge,lambda:None)
def stored_good():
 with tempfile.TemporaryDirectory() as z:
  v=stored_fixture(z);assert v['pages']==3 and v['revisions']['observed']==3 and v['references_decoded_once']==1
test('full_stored_fixture_3pages_2groups_raw_semantic_transcripts_revisionbitmap',stored_good)
mutations=[('overlap',lambda db,idx,r,b,p:db.execute('update pages set group_decoded_start=0 where row_ordinal=2')),('missing_page',lambda db,idx,r,b,p:db.execute('delete from pages where row_ordinal=3')),('rawline',lambda db,idx,r,b,p:idx.execute('update rows set raw_line_sha256=zeroblob(32) where row_ordinal=1')),('semantic_raw_confusion',lambda db,idx,r,b,p:r[0].update(actual_native_identity_SHA256=r[0]['raw_index_identity_SHA256'])),('bridge_SHA',lambda db,idx,r,b,p:b['expected_SQL_fields'][0].update(raw_SHA256='0'*64)),('duplicate_revordinal',lambda db,idx,r,b,p:db.execute('insert into revisions values(22,2,2)')),('missing_revision',lambda db,idx,r,b,p:db.execute('delete from revisions where revision_id=21')),('nextgroup_cutoff',lambda db,idx,r,b,p:idx.execute('update groups set block_end_exclusive=775 where group_ordinal=3'))]
for name,fn in mutations:
 def bad(fn=fn):
  with tempfile.TemporaryDirectory() as z:must(lambda:stored_fixture(z,fn))
 test('stored_counterexample_'+name,bad)
# Actual runner entry-path faults remain synthetic and source-free.
import types,time,signal,os
from unittest.mock import patch
import runner

def pending_binding():
 with tempfile.TemporaryDirectory() as z:
  p=pathlib.Path(z)/'pending';p.write_text('{"status":"PENDING"}');a=types.SimpleNamespace(binding=str(p),binding_sha256=runner.sha(p));must(lambda:runner.bound(a,{}))
test('actual_runner_refuses_pending_terminal_binding_before_SQL',pending_binding)
def early_supervisor():
 old=runner.START;runner.START=time.monotonic()-3654.98
 try:
  with patch.object(runner,'verify',lambda a:time.sleep(.1)):must(lambda:runner.supervise(types.SimpleNamespace()))
 finally:runner.START=old;signal.setitimer(signal.ITIMER_REAL,0)
test('actual_supervisor_alarm_interrupts_blocked_preflight',early_supervisor)
def existing_output():
 with tempfile.TemporaryDirectory() as z:
  p=pathlib.Path(z);f=p/'old';f.write_bytes(b'old')
  with patch.object(runner,'verify',lambda a:{'output':str(p)}),patch.object(runner,'bound',lambda *a:None),patch.object(runner.subprocess,'Popen',lambda *a,**k:(_ for _ in ()).throw(AssertionError('mustnotspawn'))):must(lambda:runner.supervise(types.SimpleNamespace()))
  assert list(p.iterdir())==[f] and f.read_bytes()==b'old'
test('actual_supervisor_existingOUT_preserved_nochild',existing_output)
def owner_fault():
 with tempfile.TemporaryDirectory() as z:
  p=pathlib.Path(z);(p/'ownership.json').write_text('{}');a=types.SimpleNamespace(start=time.monotonic(),supervisor_pid=os.getppid(),profile_sha256='p',code_pins_sha256='c')
  with patch.object(runner,'verify',lambda a:{'output':str(p)}),patch.object(runner,'bound',lambda *a:({}, {}, {})),patch.object(runner.sourcepilot,'verify',lambda *a:(_ for _ in ()).throw(AssertionError('no_metadata_scan_before_ownership'))):must(lambda:runner.worker(a))
  signal.setitimer(signal.ITIMER_REAL,0)
test('actual_worker_invalid_owner_refused_before_metadata_scan',owner_fault)
def worker_lifecycle(postflight=False):
 with tempfile.TemporaryDirectory() as z:
  root=pathlib.Path(z);out=root/'out';out.mkdir();folder=root/'producer';folder.mkdir();blob=folder/'frame.sqlite';blob.write_bytes(b'synthetic stored artifact');native=root/'synthetic_native';native.write_bytes(b'synthetic');idx=root/'index';idx.write_bytes(b'synthetic metadata');dec=root/'decoder.py';dec.write_text('def decode_once(x):return x\n');bridge=root/'bridge.json';bridge.write_text(json.dumps({'expected_SQL_fields':[{}]*1600,'expected_groups':[{}]*16}));calls=[0]
  p={'output':str(out),'producer_output':str(folder),'producer_profile_SHA256':'p','producer_codepins_SHA256':'c','bridge':str(bridge)};a=types.SimpleNamespace(start=time.monotonic(),supervisor_pid=os.getppid(),profile_sha256='p',code_pins_sha256='c',binding_sha256='b')
  for n,size in runner.SLOTS.items():(out/n).write_bytes(b' '*size)
  (out/'ownership.json').write_bytes(core.transcript({'worker_PID':os.getpid(),'supervisor_PID':os.getppid(),'profile_SHA256':'p','codepins_SHA256':'c','shared_start':a.start}))
  b={'files':{'frame.sqlite':{'stat':runner.ident(blob),'SHA256':runner.sha(blob)}}};r={'artifacts':{'frame.sqlite':{'bytes':blob.stat().st_size,'SHA256':runner.sha(blob)}}};s={'all_output_bytes':blob.stat().st_size,'peak_observed_RSS_bytes':1,'elapsed_seconds':1};prod={'index':{'path':str(idx)},'title_decoder':str(dec),'limits':{'max_group_compressed_bytes':100},'source':{'bytes':native.stat().st_size},'selection':{}};binding={'path':str(native),'stat':runner.ident(native)}
  def verify(a):
   calls[0]+=1
   if postflight and calls[0]>1:raise ValueError('postflight_pin_drift')
   return p
  with patch.object(runner,'verify',verify),patch.object(runner,'bound',lambda *a:(b,r,s)),patch.object(runner,'resource_guard',lambda *a:None),patch.object(runner.sourcepilot,'verify',lambda *a:(prod,binding)),patch.object(runner.core,'verify_frame',lambda *a:{'pages':3}):
   if postflight:must(lambda:runner.worker(a));assert runner.load(out/'result.json')['status']=='PARTIAL_INDEPENDENT_VERIFICATION_NO_RETRY'
   else:runner.worker(a);assert runner.load(out/'result.json')['status']=='COMPLETE_INDEPENDENT_STORED_FRAGMENT_METADATA_VERIFICATION_NO_ADMISSION' and calls[0]==2
  signal.setitimer(signal.ITIMER_REAL,0)
test('actual_worker_success_hashes_storedartifact_postflight_stat_and_pin',worker_lifecycle)
test('actual_worker_postflight_pin_drift_terminal_partial',lambda:worker_lifecycle(True))
print(json.dumps({'status':'PASS_SYNTHETIC_ONLY','count':len(checks),'checks':checks,'native_or_retained_index_reads':0},indent=2))
