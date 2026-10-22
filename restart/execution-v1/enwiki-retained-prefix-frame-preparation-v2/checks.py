"""Finite synthetic retained-prefix/frame controls. No native retained reader."""
import bz2,contextlib,hashlib,json,os,sqlite3,subprocess,sys,tempfile,time,types
from pathlib import Path
from unittest.mock import patch
import engine,index_reader,pilot,source_guard
BASE=Path(__file__).resolve().parent.parent
SEM=BASE/'enwiki-semantic-SAX-metadata-preparation-v3/semantic.py';SINK=BASE/'enwiki-compact-SQLite-sink-preparation-v2/sink.py';TITLE=BASE/'enwiki-index-XML-title-proposal-v1/title_decode.py'
H=b'<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/"><siteinfo><base>https://en.wikipedia.org/wiki/Main_Page</base><namespaces><namespace key="0"/></namespaces></siteinfo>'
def page(i,title=None):return b'<page><title>'+(title or ('T'+str(i)).encode())+b'</title><ns>0</ns><id>'+str(i).encode()+b'</id><revision><id>'+str(i+10).encode()+b'</id><model>wikitext</model><format>text/x-wiki</format><text>Exact prose.</text></revision></page>'
def fixture(z,titles=None):
    root=Path(z).resolve();parts=[bz2.compress(H),bz2.compress(page(1,(titles or {}).get(1))+page(2)),bz2.compress(page(3))];data=b''.join(parts);dbpath=root/'index.sqlite'
    db=sqlite3.connect(dbpath);db.executescript('CREATE TABLE groups(group_ordinal INTEGER PRIMARY KEY,block_start INTEGER,block_end_exclusive INTEGER,first_row INTEGER,last_row INTEGER,row_count INTEGER);CREATE TABLE rows(row_ordinal INTEGER PRIMARY KEY,page_id INTEGER UNIQUE,group_ordinal INTEGER,title TEXT,raw_line_sha256 BLOB,raw_line_bytes INTEGER,line_ends_LF INTEGER,noncanonical_offset_ascii TEXT,noncanonical_page_ascii TEXT);')
    offset=len(parts[0]);grows=[];ordinal=0
    for g,pids in enumerate([[1,2],[3]],1):
        first=ordinal+1;end=offset+len(parts[g]);grows.append((g,offset,end,first,first+len(pids)-1,len(pids)))
        for pid in pids:
            ordinal+=1;title=(titles or {}).get(pid,('T'+str(pid)).encode()).decode();line=(str(offset)+':'+str(pid)+':'+title+'\n').encode();db.execute('INSERT INTO rows VALUES(?,?,?,?,?,?,?,?,?)',(ordinal,pid,g,title,hashlib.sha256(line).digest(),len(line),1,None,None))
        offset=end
    db.executemany('INSERT INTO groups VALUES(?,?,?,?,?,?)',grows);db.commit();db.close()
    profile={'index':{'path':str(dbpath),'stat':index_reader.identity(dbpath.stat())},'source':{'bytes':len(data)},'semantic_module':str(SEM),'sink_module':str(SINK),'title_decoder':str(TITLE),'selection':{'groups':2,'rows':3,'header_bytes':len(parts[0]),'compressed_prefix_end_exclusive':len(data),'require_next_group_outside_prefix':False},'limits':{'DB_bytes':2000000,'metadata_bytes':1000000,'revision_occurrences':30,'decoded_bytes':1000000,'max_group_compressed_bytes':1000000,'compressed_bytes':len(data)}}
    return profile,data,grows
checks=[]
def control(name,fn):fn();checks.append(name)
def run(mutate=lambda p,b,g:(p,b,g),fault=lambda stage:None,title=None):
    with tempfile.TemporaryDirectory() as z:
        p,b,g=fixture(z,title);p,b,g=mutate(p,b,g);out=Path(z)/'out';out.mkdir();reads=[]
        def read(o,n):reads.append((o,n));return b[o:o+n]
        with index_reader.opened(p,lambda *a,**k:None) as groups:r=engine.run(p,groups,read,out,lambda *a,**k:None,fault=fault)
        db=sqlite3.connect(out/'frame.sqlite');assert db.execute('PRAGMA integrity_check').fetchone()==('ok',);assert db.execute('PRAGMA foreign_key_check').fetchone() is None
        assert db.execute('SELECT count(*) FROM pages').fetchone()==(3,);db.close()
        receipts=(out/'group-receipts.jsonl').read_bytes();lines=[json.loads(x) for x in receipts.splitlines()];assert len(lines)==2
        assert r['exceptions']['group_receipt_count']==2 and r['exceptions']['group_receipt_bytes']==len(receipts) and r['exceptions']['ordered_group_receipts_SHA256']==hashlib.sha256(receipts).hexdigest()
        assert all(x['actual_native_identity_SHA256']==x['frozen_index_identity_SHA256'] for x in lines)
        assert sum(n for o,n in reads)==len(b);assert r['counts']['namespace_counts']==[(0,3)] and sum(n for _,n in r['counts']['flag_counts'])==3
        return r
control('production iterator+engine+SAX+sink exact3pages2groups CRC identity rawspans',run)
for title in [b'British &amp; Irish Lions',b'A&#38;B',b'&amp;amp;',b'e\xcc\x81 &lt;title&gt;']:
 control('strict_decode_once_'+title.decode(),lambda title=title:run(title={1:title}))
def failure(mutate=lambda p,b,g:(p,b,g),fault=lambda stage:None,expected_groups=0):
    with tempfile.TemporaryDirectory() as z:
        p,b,g=fixture(z);p,b,g=mutate(p,b,g);out=Path(z)/'out';out.mkdir()
        try:
            with index_reader.opened(p,lambda *a,**k:None) as groups:engine.run(p,groups,lambda o,n:b[o:o+n],out,lambda *a,**k:None,fault=fault)
        except Exception:
            if (out/'frame.sqlite').exists():
                db=sqlite3.connect(out/'frame.sqlite');assert db.execute('SELECT count(*) FROM groups').fetchone()==(expected_groups,);db.close()
            return
        raise AssertionError('unexpected complete')
def SQLchange(query,args=()):
 def f(p,b,g):
    path=Path(p['index']['path']);db=sqlite3.connect(path);db.execute(query,args);db.commit();db.close();p['index']['stat']=index_reader.identity(path.stat());return p,b,g
 return f
for label,query in [('title','UPDATE rows SET title="Wrong" WHERE row_ordinal=1'),('rawlinehash','UPDATE rows SET raw_line_sha256=zeroblob(32) WHERE row_ordinal=1'),('membership','UPDATE rows SET group_ordinal=2 WHERE row_ordinal=1'),('rowcount','UPDATE groups SET row_count=1 WHERE group_ordinal=1'),('end','UPDATE groups SET block_end_exclusive=block_end_exclusive+1 WHERE group_ordinal=1'),('gap','DELETE FROM rows WHERE row_ordinal=1')]:control('index_'+label+'_refusal',lambda q=query:failure(SQLchange(q)))
def identity_change(p,b,g):
 path=Path(p['index']['path']);db=sqlite3.connect(path);title='Wrong';off=g[0][1];line=(str(off)+':1:'+title+'\n').encode();db.execute('UPDATE rows SET title=?,raw_line_sha256=?,raw_line_bytes=? WHERE row_ordinal=1',(title,hashlib.sha256(line).digest(),len(line)));db.commit();db.close();p['index']['stat']=index_reader.identity(path.stat());return p,b,g
control('selfconsistent wrong index title still native identity stop',lambda:failure(identity_change))
def crc(p,b,g):
 raw=bytearray(b);raw[g[0][2]-4]^=1;return p,bytes(raw),g
control('late CRC no group commit',lambda:failure(crc))
def cap(p,b,g):p['limits']['decoded_bytes']=len(H)+10;return p,b,g
control('decoded hard cap',lambda:failure(cap))
def metcap(p,b,g):p['limits']['metadata_bytes']=1;return p,b,g
control('combined metadata prewrite cap',lambda:failure(metcap))
def crash(stage):
 if stage=='before_group_commit':raise RuntimeError('fixture')
control('before group commit rollback',lambda:failure(fault=crash))
def after(stage):
 if stage=='after_group_commit':raise RuntimeError('fixture')
control('after commit before receipt is partial not resumable',lambda:failure(fault=after,expected_groups=1))
def nextbad(p,b,g):p['selection']['require_next_group_outside_prefix']=True;return p,b,g
control('explicit nextgroup boundary proof required',lambda:failure(nextbad,expected_groups=2))
for value in ['', '9 1 0\n','9 1 20\n9 1 30\n','9 9 20\n','9 1 -1\n']:
 def bad(value=value):
  try:pilot.tree_rss(value,9)
  except ValueError:return
  raise AssertionError('badRSS accepted')
 control('RSS failclosed '+repr(value),bad)
def source_custody():
 with tempfile.TemporaryDirectory() as z:
  p=Path(z).resolve()/'source';p.write_bytes(b'abc');binding={'path':str(p),'stat':source_guard.ident(p.stat())}
  try:
   with source_guard.opened(binding,lambda:None) as read:
    assert read(0,1)==b'a';p.write_bytes(b'xyz');read.assert_custody()
  except ValueError:return
  raise AssertionError('source mutation accepted')
control('source FD/path stat mutation refused',source_custody)
def index_swap():
 with tempfile.TemporaryDirectory() as z:
  p,b,g=fixture(z)
  try:
   with index_reader.opened(p,lambda:None) as groups:
    gen=groups();next(gen);path=Path(p['index']['path']);path.rename(path.with_name('old'));path.write_bytes(b'x');groups.assert_custody()
  except ValueError:return
  raise AssertionError('index replacement accepted')
control('index inode replacement refused',index_swap)
def streaming_hash():
 with tempfile.TemporaryDirectory() as z:
  p=Path(z)/'blob';p.write_bytes(b'a'*2000000)
  with patch.object(Path,'read_bytes',lambda *a:(_ for _ in ()).throw(AssertionError('wholefile read prohibited'))):assert pilot.stream_sha(p,lambda:None)==hashlib.sha256(b'a'*2000000).hexdigest()
control('actual artifact verifier never whole-file read_bytes',streaming_hash)
def bounded_counters():
 class Sink:
  def page(self,*a):pass
 c=engine.Codec(Sink(),lambda x:None,lambda:None);c.namespace_counts={i:1 for i in range(1024)}
 p={'page_ID':1,'title':'T1','page_ordinal':1,'redirect':None,'namespace':2000,'holds':[],'revision_count':0,'main_text':None,'model':None,'format':None,'raw_XML':{'start':0,'bytes':1,'SHA256':'0'*64}}
 try:c.page(p)
 except ValueError as e:assert str(e)=='bounded_summary_cardinality_cap';return
 raise AssertionError('namespace counter unbounded')
control('aggregate namespace/flag maps operationally bounded',bounded_counters)
def early_alarm():
 oldverify,oldstart=pilot.verify,pilot.ENTRY_START
 try:
  pilot.ENTRY_START=pilot.clk()-21894.95
  def blocked(a):time.sleep(.3);raise AssertionError('alarm missed')
  pilot.verify=blocked
  try:pilot.supervise(types.SimpleNamespace())
  except TimeoutError:return
  raise AssertionError('deadline accepted')
 finally:pilot.verify,pilot.ENTRY_START=oldverify,oldstart
control('actual supervisor early preflight deadline',early_alarm)
child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'],start_new_session=True);pilot.kill(child);assert child.poll() is not None;checks.append('owned child group killed/reaped')
def noncanonical(p,b,g):
    path=Path(p['index']['path']);db=sqlite3.connect(path);off='000'+str(g[0][1]);ident='0001';raw=(off+':'+ident+':T1\n').encode();db.execute('UPDATE rows SET noncanonical_offset_ascii=?,noncanonical_page_ascii=?,raw_line_sha256=?,raw_line_bytes=? WHERE row_ordinal=1',(off,ident,hashlib.sha256(raw).digest(),len(raw)));db.commit();db.close();p['index']['stat']=index_reader.identity(path.stat());return p,b,g
control('noncanonical numeric lexemes lossless verified not normalized source',lambda:run(noncanonical))
def worker_lifecycle(wrong_owner=False,postflight=False):
    with tempfile.TemporaryDirectory() as z:
        p,b,g=fixture(z);out=Path(z).resolve()/'out';out.mkdir();p['output']=str(out)
        for name,n in pilot.SLOTS.items():(out/name).write_bytes(b' '*n)
        binding={'path':str(Path(z).resolve()/'synthetic-source'),'SHA256':hashlib.sha256(b).hexdigest(),'stat':[0]*5}
        arg=types.SimpleNamespace(start=pilot.clk(),supervisor_pid=os.getppid(),profile_sha256='P',code_pins_sha256='C')
        (out/'ownership.json').write_text(json.dumps({'worker_PID':os.getpid()+(1 if wrong_owner else 0),'supervisor_PID':os.getppid(),'shared_start':arg.start,'profile_SHA256':'P','codepins_SHA256':'C'}))
        calls=[0];closed=[False];opened=[False]
        def verify(a):
            calls[0]+=1
            if postflight and calls[0]>1:raise ValueError('fixture_postflight_changed')
            return p,binding
        @contextlib.contextmanager
        def source(binding,check):
            opened[0]=True
            def read(off,n):return b[off:off+n]
            def custody():
                if closed[0]:raise OSError('closed_source_FD')
            read.assert_custody=custody
            try:yield read
            finally:closed[0]=True
        with patch.object(pilot,'verify',verify),patch.object(source_guard,'verify',lambda p:binding),patch.object(source_guard,'opened',source),patch.object(pilot,'guard',lambda out,start,sec,extra=0,custody=None:custody() if custody else None),patch.object(source_guard,'ident',lambda s:[0]*5),patch.object(Path,'stat',Path.stat):
            # Worker final stat needs a real synthetic path, outside output.
            Path(binding['path']).write_bytes(b)
            if wrong_owner or postflight:
                try:pilot.worker(arg)
                except ValueError:pass
                else:raise AssertionError('worker failure expected')
                if wrong_owner:assert not opened[0]
                else:assert json.loads((out/'result.json').read_text())['status']=='PARTIAL_RETAINED_PREFIX_FRAME_NO_RETRY'
            else:
                pilot.worker(arg);assert closed[0] and calls[0]==2
                assert json.loads((out/'result.json').read_text())['status']=='COMPLETE_RETAINED_PREFIX_FRAGMENT_FRAME_NO_ADMISSION'
control('actual worker lifecycle closes both source/index before postflight',worker_lifecycle)
control('actual worker bad owner no source opening',lambda:worker_lifecycle(wrong_owner=True))
control('actual worker postflight error terminal partial',lambda:worker_lifecycle(postflight=True))

def census_unlink():
    from tree_size import census
    with tempfile.TemporaryDirectory() as z:
        root=Path(z).resolve();stable=root/'stable';stable.write_bytes(b'x'*17);journal=root/'index.sqlite-journal';journal.write_bytes(b'old');real=Path.stat;calls={};removed=[False]
        def stat(path,*args,**kw):
            calls[str(path)]=calls.get(str(path),0)+1
            if path==journal and not removed[0]:journal.unlink();removed[0]=True
            return real(path,*args,**kw)
        with patch.object(Path,'stat',stat),patch.object(Path,'is_file',lambda *a:(_ for _ in ()).throw(AssertionError('double-is_file/stat prohibited'))):assert census(root)==17
        assert removed[0] and calls[str(root)]==2
control('census actual journal unlink restarts entire scan',census_unlink)
def census_rename():
    from tree_size import census
    with tempfile.TemporaryDirectory() as z:
        root=Path(z).resolve();partial=root/'large.partial';final=root/'large.gz'
        with partial.open('wb') as f:f.truncate(300000000)
        (root/'small').write_bytes(b'x'*7);real=Path.stat;calls={};renamed=[False]
        def stat(path,*args,**kw):
            calls[str(path)]=calls.get(str(path),0)+1
            if path==partial and not renamed[0]:os.replace(partial,final);renamed[0]=True
            return real(path,*args,**kw)
        with patch.object(Path,'stat',stat),patch.object(Path,'is_file',lambda *a:(_ for _ in ()).throw(AssertionError('double stat prohibited'))):assert census(root)==300000007
        assert calls[str(root)]==2 and calls[str(final)]==1
control('census actual300MB sparse partial rename final counted exact after full restart',census_rename)
def census_churn():
    from tree_size import census
    with tempfile.TemporaryDirectory() as z:
        root=Path(z).resolve();journal=root/'journal';real=Path.stat;rootcalls=[0];unlinks=[0]
        def stat(path,*args,**kw):
            if path==root:rootcalls[0]+=1;journal.write_bytes(b'x')
            if path==journal:journal.unlink();unlinks[0]+=1
            return real(path,*args,**kw)
        with patch.object(Path,'stat',stat):
            try:census(root)
            except ValueError as e:assert str(e)=='census_persistent_ENOENT_after8_full_attempts'
            else:raise AssertionError('persistent churn silently skipped')
        assert rootcalls[0]==8 and unlinks[0]==8
control('census persistent actual unlink churn eight attempts failclosed',census_churn)
def census_once():
    from tree_size import census
    with tempfile.TemporaryDirectory() as z:
        root=Path(z).resolve();sub=root/'sub';sub.mkdir();(root/'a').write_bytes(b'xx');(sub/'b').write_bytes(b'yyy');real=Path.stat;calls={}
        def stat(path,*args,**kw):calls[str(path)]=calls.get(str(path),0)+1;assert kw=={'follow_symlinks':False};return real(path,*args,**kw)
        with patch.object(Path,'stat',stat),patch.object(Path,'is_file',lambda *a:(_ for _ in ()).throw(AssertionError('is_file prohibited'))),patch.object(Path,'open',lambda *a,**k:(_ for _ in ()).throw(AssertionError('body open prohibited'))):assert census(root)==5
        assert len(calls)==4 and all(n==1 for n in calls.values())
control('census one lstat per stable path no is_file no source open',census_once)
def census_other_error():
    from tree_size import census
    with tempfile.TemporaryDirectory() as z:
        root=Path(z).resolve();real=Path.stat;calls=[0]
        def stat(path,*args,**kw):
            if path==root:calls[0]+=1;raise PermissionError('fixture')
            return real(path,*args,**kw)
        with patch.object(Path,'stat',stat):
            try:census(root)
            except PermissionError:pass
            else:raise AssertionError('nonENOENT error hidden')
        assert calls[0]==1
control('census nonENOENT errors propagate no silent retry',census_other_error)

print(json.dumps({'status':'PASS_SYNTHETIC_ONLY','count':len(checks),'checks':checks,'retained_native_reads':0,'retained_index_reads':0,'network_ledger_model_operations':0},indent=2))
