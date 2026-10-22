"""Actual integrated paths on tiny synthetic groups; never retained native bytes."""
import bz2,hashlib,json,os,sqlite3,tempfile,time,contextlib,types,subprocess,sys
from pathlib import Path
import engine,pilot,source_guard
BASE=Path(__file__).resolve().parent.parent
SEM=BASE/'enwiki-semantic-SAX-metadata-preparation-v3/semantic.py'
SINK=BASE/'enwiki-compact-SQLite-sink-preparation-v2/sink.py'
H=b'<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/"><siteinfo><base>https://en.wikipedia.org/wiki/Main_Page</base><namespaces><namespace key="0"/></namespaces></siteinfo>'
def page(i,role=None,bad_hash=False):
    c=b'<model>wikitext</model><format>text/x-wiki</format><text>Exact synthetic prose.</text>'
    if role:c=b'<slots><slot role="'+role.encode()+b'">'+c+b'</slot></slots>'
    return b'<page><title>T'+str(i).encode()+b'</title><ns>0</ns><id>'+str(i).encode()+b'</id><revision><id>'+str(i+10).encode()+b'</id>'+c+(b'<sha1>0</sha1>' if bad_hash else b'')+b'</revision></page>'
def fixture(role=None,bad_hash=False):
    chunks=[bz2.compress(H),bz2.compress(page(1)+page(2,role,bad_hash)),bz2.compress(page(3))]
    pos=len(chunks[0]);groups=[];rows=[]
    for i,pages in enumerate([[1,2],[3]],1):
        n=len(chunks[i]);first=len(rows)+1
        for pid in pages:rows.append([pid,i,pid,'T'+str(pid)])
        groups.append({'group_ordinal':i,'compressed_start':pos,'compressed_end_exclusive':pos+n,
           'compressed_bytes':n,'first_row_ordinal':first,'last_row_ordinal':len(rows),'index_rows':len(pages)})
        pos+=n
    selection={'groups':groups,'rows':3,'header_bytes':len(chunks[0]),'compressed_prefix_end_exclusive':pos}
    profile={'semantic_module':str(SEM),'sink_module':str(SINK),'title_decoder':str(BASE/'enwiki-index-XML-title-proposal-v1/title_decode.py'),'limits':{'DB_bytes':2000000,'metadata_bytes':1000000,
      'revision_occurrences':30,'decoded_bytes':1000000,'max_group_compressed_bytes':1000000,'compressed_bytes':pos}}
    return profile,selection,rows,b''.join(chunks)
checks=[]
def actual(tmp,role=None,bad_hash=False,mutate=lambda p,s,r,b:(p,s,r,b),fault=lambda x:None):
    p,s,r,b=mutate(*fixture(role,bad_hash));reads=[]
    def read(offset,n):reads.append((offset,n));return b[offset:offset+n]
    result=engine.run(p,s,r,read,tmp,lambda n=0:None,fault=fault)
    return result,reads,p,s,r,b
with tempfile.TemporaryDirectory() as td:
    out=Path(td);r,reads,p,s,rows,raw=actual(out)
    assert r['counts']['pages']==3 and r['counts']['groups']==2 and r['counts']['revision_occurrences']==3
    assert sum(n for off,n in reads)==len(raw) and reads[0]==(0,s['header_bytes'])
    assert (out/'exceptions.jsonl').read_bytes()==b'' and r['exceptions']['events']==0
    assert r['exceptions']['bytes']==0 and r['exceptions']['ordered_exception_SHA256']==hashlib.sha256(b'').hexdigest()
    db=sqlite3.connect(out/'frame.sqlite');assert db.execute('SELECT count(*) FROM revisions').fetchone()==(3,)
    groups=db.execute('SELECT group_ordinal,raw_SHA256 FROM groups').fetchall()
    for g,h in groups:
        receipt=json.loads((out/'group-receipts.json').read_text())['groups'][g-1]
        assert h.hex()==receipt['decoded_SHA256'] and receipt['actual_native_identity_SHA256']==receipt['frozen_index_identity_SHA256']
        expected=[x for x in rows if x[1]==g]
        assert receipt['actual_native_identity_SHA256']==hashlib.sha256(b''.join(engine.transcript([x[0],x[2],x[3]]) for x in expected)).hexdigest()
    db.close();checks+=['integrated_exact_CRC_ID_title_order_SQL_3pages_2groups','no_normal_revision_JSON_spool','pergroup_native_identity_transcript','SQL_rawSHA_is_decodedXMLgroup_not_compressed','exact_selected_compressed_reads']
for role,bad,expected in [('aux',False,'UNSUPPORTED_OR_MISSING_SLOT_ROLE'),(None,True,'SIBLING_SHA1_MISMATCH')]:
    with tempfile.TemporaryDirectory() as td:
        out=Path(td);r,*_=actual(out,role,bad)
        events=[json.loads(x) for x in (out/'exceptions.jsonl').read_text().splitlines()]
        assert any(expected in x.get('holds',[]) for x in events)
        assert r['counts']['pages']==3 and r['exceptions']['bytes']==(out/'exceptions.jsonl').stat().st_size
        assert hashlib.sha256((out/'exceptions.jsonl').read_bytes()).hexdigest()==r['exceptions']['ordered_exception_SHA256']
        checks.append('held_slot_or_hash_preserved_not_source_admission_'+expected)
def expect_failure(name,mutate,error=None,fault=lambda x:None,committed=0):
    with tempfile.TemporaryDirectory() as td:
        out=Path(td)
        try:actual(out,mutate=mutate,fault=fault)
        except Exception as e:
            if error:assert error in str(e),(name,e)
            db=sqlite3.connect(out/'frame.sqlite');assert db.execute('SELECT count(*) FROM groups').fetchone()==(committed,);db.close();checks.append(name)
        else:raise AssertionError(name+' completed')
def title_bad(p,s,r,b):r[0][3]='Wrong';return p,s,r,b
expect_failure('actual_native_title_mismatch_rolls_back_group',title_bad,'ordered_native_index')
def pid_bad(p,s,r,b):r[0][2]=999;return p,s,r,b
expect_failure('actual_native_pageID_mismatch_rolls_back_group',pid_bad,'ordered_native_index')
def crc_bad(p,s,r,b):
    raw=bytearray(b);raw[s['groups'][0]['compressed_start']+20]^=1;return p,s,r,bytes(raw)
expect_failure('corrupt_BZ2_no_group_commit',crc_bad)
def decoded_cap(p,s,r,b):p['limits']['decoded_bytes']=len(H)+10;return p,s,r,b
expect_failure('decoded_cap_before_unbudgeted_probe',decoded_cap,'decoded')
def group_cap(p,s,r,b):p['limits']['max_group_compressed_bytes']=1;return p,s,r,b
expect_failure('compressed_group_bound_before_read',group_cap,'header_compressed_cap')
def exception_cap(p,s,r,b):p['limits']['metadata_bytes']=1;return p,s,r,b
expect_failure('metadata_prewrite_cap',exception_cap,'metadata_allfiles_cap')
def crash(stage):
    if stage=='before_group_commit':raise RuntimeError('injected_interrupt')
expect_failure('interrupt_before_atomic_commit',lambda *x:x,'injected_interrupt',fault=crash)
def crash_after(stage):
    if stage=='after_group_commit':raise RuntimeError('injected_after_commit')
expect_failure('interrupt_after_commit_preserves_only_durable_prefix',lambda *x:x,'injected_after_commit',fault=crash_after,committed=1)
for bad in ['', '100 1 20\n','99 1 -1\n','99 1 20\n99 1 30\n','99 99 20\n','garbage']:
    try:pilot.tree_rss(bad,99,100)
    except ValueError:checks.append('failclosed_RSS_'+str(len(checks)))
    else:raise AssertionError('bad RSS accepted')
assert pilot.tree_rss('99 1 20\n100 99 30\n101 100 40\n',99,100)==90*1024;checks.append('owned_process_tree_RSS_sum')
with tempfile.TemporaryDirectory() as td:
    p=Path(td).resolve()/'synthetic';p.write_bytes(b'abcde');binding={'path':str(p),'stat':source_guard.ident(p.stat())}
    try:
        with source_guard.opened(binding,lambda:None) as read:
            assert read(0,2)==b'ab';read.assert_custody()
            raise RuntimeError('fixture_end')
    except RuntimeError:checks.append('synthetic_O_RDONLY_NOFOLLOW_FD_custody_and_cleanup')
    p.unlink();p.symlink_to(Path(td)/'absent')
    try:
        with source_guard.opened(binding,lambda:None):pass
    except ValueError:checks.append('source_symlink_refused_before_IO')
    else:raise AssertionError('symlink accepted')
with tempfile.TemporaryDirectory() as td:
    p=Path(td).resolve()/'synthetic';p.write_bytes(b'abcde');binding={'path':str(p),'stat':source_guard.ident(p.stat())}
    try:
        with source_guard.opened(binding,lambda:None) as read:
            p.write_bytes(b'ABCDE');read.assert_custody()
    except ValueError:checks.append('source_inplace_mutation_stat_guard')
    else:raise AssertionError('mutation accepted')
# Actual worker success lifecycle, including final check after readerFD closed.
with tempfile.TemporaryDirectory() as td:
    out=Path(td).resolve();p,s,r,b=fixture();p['output']=str(out)
    src=out/'fixture-input';src.write_bytes(b)
    binding={'path':str(src),'stat':source_guard.ident(src.stat()),'SHA256':hashlib.sha256(b).hexdigest()}
    for n,c in pilot.SLOTS.items():(out/n).write_bytes(b' '*c)
    a=types.SimpleNamespace(start=pilot.clk(),supervisor_pid=os.getppid(),profile_sha256='p',code_pins_sha256='c')
    (out/'ownership.json').write_text(json.dumps({'worker_PID':os.getpid(),'supervisor_PID':os.getppid(),'shared_start':a.start,'profile_SHA256':'p','codepins_SHA256':'c'}))
    oldverify,oldsource,oldopen,oldguard=pilot.verify,source_guard.verify,source_guard.opened,pilot.guard
    closed=[False]
    @contextlib.contextmanager
    def fixture_opened(binding,check):
        def read(offset,n):return b[offset:offset+n]
        def custody():
            if closed[0]:raise OSError('synthetic_closed_FD_EBADF')
        read.assert_custody=custody
        try:yield read
        finally:closed[0]=True
    try:
        pilot.verify=lambda a:(p,s,r,binding);source_guard.verify=lambda profile:binding;source_guard.opened=fixture_opened
        pilot.guard=lambda out,start,seconds,extra=0,custody=None:custody() if custody else None
        pilot.worker(a)
        assert closed[0] and json.loads((out/'result.json').read_text())['status']=='COMPLETE_FIRST128_TERMINAL_PREFIX_CALIBRATION_NO_ADMISSION'
        checks.append('actual_worker_success_postflight_after_reader_close')
    finally:pilot.verify,source_guard.verify,source_guard.opened,pilot.guard=oldverify,oldsource,oldopen,oldguard

# Production supervisor early shared alarm interrupts blocked preflight before IO.
oldverify,oldentry=pilot.verify,pilot.ENTRY_START
try:
    pilot.ENTRY_START=pilot.clk()-599.95
    def blocked(a):time.sleep(.3);raise AssertionError('preflight_deadline_failed')
    pilot.verify=blocked
    try:pilot.supervise(types.SimpleNamespace())
    except TimeoutError:checks.append('actual_supervisor_blocked_preflight_interrupted_before_output')
    else:raise AssertionError('early alarm missed')
finally:pilot.verify,pilot.ENTRY_START=oldverify,oldentry

with tempfile.TemporaryDirectory() as td:
    out=Path(td);(out/'old').write_bytes(b'preserve')
    oldverify,oldentry=pilot.verify,pilot.ENTRY_START
    try:
        pilot.ENTRY_START=pilot.clk();pilot.verify=lambda a:({'output':str(out)},None,None,None)
        try:pilot.supervise(types.SimpleNamespace())
        except ValueError as e:assert 'once_only_output' in str(e)
        assert list(out.iterdir())==[out/'old'] and (out/'old').read_bytes()==b'preserve'
        checks.append('existing_output_untouched_on_preflight_refusal')
    finally:pilot.verify,pilot.ENTRY_START=oldverify,oldentry
child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'],start_new_session=True)
pilot.kill(child);assert child.poll() is not None;checks.append('owned_worker_process_group_killed_and_reaped')
with tempfile.TemporaryDirectory() as td:
    out=Path(td);realhere=pilot.HERE
    profile=(realhere/'profile.json').read_bytes()
    (out/'profile.json').write_bytes(profile);(out/'code-pins.json').write_text('{"SHA256":{}}')
    a=types.SimpleNamespace(profile_sha256=hashlib.sha256(profile).hexdigest(),code_pins_sha256=hashlib.sha256((out/'code-pins.json').read_bytes()).hexdigest())
    try:
        pilot.HERE=out
        try:pilot.verify(a)
        except ValueError as e:assert 'exact_required_inventory' in str(e);checks.append('empty_mutable_codepins_registry_refused_before_source_guard')
        else:raise AssertionError('empty code registry accepted')
    finally:pilot.HERE=realhere
# New exact representation cases run through real engine, SAX and atomic sink.
def encoded_fixture(rawtitle):
 def mutate(p,s,r,b):
  header=b[:s['header_bytes']];chunks=[header];pos=len(header)
  for g in s['groups']:
   payload=bz2.decompress(b[g['compressed_start']:g['compressed_end_exclusive']])
   if g['group_ordinal']==1:payload=payload.replace(b'<title>T1</title>',b'<title>'+rawtitle.encode()+b'</title>')
   z=bz2.compress(payload);g['compressed_start']=pos;g['compressed_end_exclusive']=pos+len(z);g['compressed_bytes']=len(z);pos+=len(z);chunks.append(z)
  r[0][3]=rawtitle;s['compressed_prefix_end_exclusive']=pos;p['limits']['compressed_bytes']=pos
  return p,s,r,b''.join(chunks)
 return mutate
for title in ['British &amp; Irish Lions','A&#38;B','A&#x26;B','&amp;amp;','e\u0301 &lt;title&gt;']:
 with tempfile.TemporaryDirectory() as td:
  out=Path(td);result,*_=actual(out,mutate=encoded_fixture(title));assert result['counts']['pages']==3
  receipt=json.loads((out/'group-receipts.json').read_text())['groups'][0]
  assert receipt['actual_native_identity_SHA256']==receipt['frozen_index_identity_SHA256']
  assert receipt['raw_index_identity_SHA256']!=receipt['frozen_index_identity_SHA256']
  assert receipt['references_decoded_once']>=1 and receipt['title_decoder_SHA256']==hashlib.sha256((BASE/'enwiki-index-XML-title-proposal-v1/title_decode.py').read_bytes()).hexdigest()
  checks.append('exact_XML_decode_once_engine_SAX_sink_'+title)
def bad_entity(p,s,r,b):r[0][3]='T1&nbsp;';return p,s,r,b
expect_failure('unknown_HTML_entity_hold_without_index_mutation_or_group_commit',bad_entity,'unknown_XML_entity')
with tempfile.TemporaryDirectory() as td:
 try:actual(Path(td),mutate=title_bad)
 except ValueError as e:
  detail=json.loads(str(e).split(':',1)[1]);assert detail['expected_ordinal']==1 and detail['actual_ordinal']==1 and detail['expected_page_ID']==1 and detail['actual_page_ID']==1
  assert detail['expected_semantic_title_SHA256']==hashlib.sha256(b'Wrong').hexdigest() and detail['actual_native_title_SHA256']==hashlib.sha256(b'T1').hexdigest()
  checks.append('bounded_precise_mismatch_ordinal_ID_and_title_hash_metadata')
 else:raise AssertionError('mismatch not refused')
print(json.dumps({'status':'INTEGRATED_SYNTHETIC_ONLY_PASS','count':len(checks),'checks':checks,'retained_native_source_reads':0,'network_ledger_model_operations':0},indent=2))
