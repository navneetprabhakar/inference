"""Synthetic-only gzip/schema/SQLite/lifecycle controls; no corpus source reads."""
import gzip,hashlib,io,json,os,sqlite3,tempfile,time,types,signal,subprocess
from pathlib import Path
from unittest.mock import patch
import inventory as v,pilot,source_guard
names=[]
def test(n,f):f();names.append(n)
def must(f):
 try:f()
 except Exception:return
 raise AssertionError('must refuse')
def obj(i=1):return {'id':f'https://x.pressbooks.pub/book/chapter/c{i}/','text':'Café 😀 English.','source':'pressbooks','added':'2025-03-22T05:08:50.984510','created':'09-30-2024','metadata':{'license':'Creative Commons - Attribution - https://creativecommons.org/licenses/by/4.0/','url':f'https://x.pressbooks.pub/book/chapter/c{i}/','book_url':'https://x.pressbooks.pub/book/front-matter/introduction/','title':'Book','author':'A','institution':'I','subject':'S'}}
def line(o):return (json.dumps(o,ensure_ascii=False,separators=(',',':'))+'\n').encode()
def profile(raw,maxrows=100):return {'source':{'bytes':len(raw),'SHA256':hashlib.sha256(raw).hexdigest()},'limits':{'compressed_bytes':len(raw),'decoded_bytes':1000000,'encountered_records':maxrows,'parsed_record_bytes':4000000,'SQLite_bytes':2000000}}
def run(payload,transform=lambda x:x,p=None):
 raw=transform(gzip.compress(payload));p=p or profile(raw)
 with tempfile.TemporaryDirectory() as z:
  out=Path(z);r=v.run(p,out,io.BytesIO(raw).read,lambda *x:None);db=sqlite3.connect(out/'frame.sqlite');records=db.execute('SELECT * FROM records ORDER BY ordinal').fetchall();db.close();exception=(out/'schema-holds.jsonl').read_bytes();return r,records,exception

def coverage():
 a=line(obj());duplicate=b'{"id":"x","id":"y"}\n';badutf=b'{"text":"\xff"}\n';null=b'null\n';extra=obj(5);extra['unknown']='kept in exact original backing';payload=a+duplicate+badutf+null+line(extra)
 r,rows,e=run(payload);assert r['rows']==5 and r['committed_rows']==5 and sum(x[2] for x in rows)==len(payload)
 for x in rows:assert hashlib.sha256(payload[x[1]:x[1]+x[2]]).digest()==x[4]
 assert rows[0][17]==hashlib.sha256(obj()['text'].encode()).digest() and rows[0][18]==len(obj()['text'].encode()) and rows[0][19]==len(obj()['text'])
 assert rows[1][5]&v.FLAGS['MALFORMED_JSON_OR_DUPLICATE_KEY'] and rows[2][5]&v.FLAGS['MALFORMED_UTF8'] and rows[3][5]&v.FLAGS['NONOBJECT'] and rows[4][5]&v.FLAGS['SCHEMA_KEYS_OR_TYPES'];assert len(e.splitlines())==4
 assert r['stored_row_line_text_totals'][1]==len(payload)
test('all5rows/UTF8/rawline offsets+SHA/duplicatekeys/null/unknownschema/no skip',coverage)
def endings():
 p=line(obj()).replace(b'\n',b'\r\n')+line(obj(2)).rstrip(b'\n');r,rows,_=run(p);assert rows[0][3]==1 and rows[1][3]==0 and rows[1][1]==len(line(obj()).replace(b'\n',b'\r\n')) and sum(x[2] for x in rows)==len(p)
test('CRLF and final nonLF exact original line framing',endings)
def oversized():
 raw=b'abc'*100+b'\n'+b'last';seen=[];l=v.Lines(20,10,lambda *r:seen.append(r))
 for i in range(0,len(raw),7):l.add(raw[i:i+7])
 l.finish();assert seen[0][2]==301 and seen[0][4]==hashlib.sha256(raw[:301]).digest() and seen[0][5] is None and seen[1][1]==301 and seen[1][5]==b'last'
test('oversize wholeline fixedchunk hash hold no reconstruct/truncate',oversized)
def nested():
 raw=b'{"metadata":{"license":"A","license":"B"}}\n';r=v.row(1,0,len(raw),True,hashlib.sha256(raw).digest(),raw)[0];assert r[5]&v.FLAGS['MALFORMED_JSON_OR_DUPLICATE_KEY'] and all(x is None for x in r[6:])
test('nested duplicate keys held before trusting any fields',nested)
def members():
 a=line(obj());b=line(obj(2));raw=gzip.compress(a)+gzip.compress(b);r,rows,_=run(a+b,transform=lambda _:raw);assert r['counts']['gzip_CRC_EOF_members']==2 and len(rows)==2
 got=[];limits={'compressed_bytes':len(raw),'decoded_bytes':len(a+b)+10};stream=io.BytesIO(raw)
 counts=v.gzip_stream(lambda n:stream.read(min(n,1)),got.append,limits,lambda:None);assert b''.join(got)==a+b and counts['gzip_CRC_EOF_members']==2
test('concatenated gzip members and1byte compressed boundary CRC/EOF',members)
for label,transform in [('truncated',lambda b:b[:-4]),('CRC',lambda b:b[:-8]+bytes([b[-8]^1])+b[-7:]),('trailing',lambda b:b+b'X')]:test('gzip '+label+' failclosed',lambda transform=transform:must(lambda:run(line(obj()),transform)))
def budget():
 payload=line(obj())*3;raw=gzip.compress(payload);p=profile(raw,2);must(lambda:run(payload,p=p));p=profile(raw);p['limits']['decoded_bytes']=5;must(lambda:run(payload,p=p))
test('record and decoded caps preservepartial notcomplete',budget)
def known():
 payload=line(obj());raw=gzip.compress(payload);p=profile(raw);p['known_holds']=[{'source_ordinal':1,'line_SHA256':hashlib.sha256(payload).hexdigest(),'id':obj()['id'],'text_SHA256':hashlib.sha256(obj()['text'].encode()).hexdigest()}];r,rows,e=run(payload,p=p);assert rows[0][5]&v.FLAGS['KNOWN_REVIEW_HOLD'] and r['flag_counts']['KNOWN_REVIEW_HOLD']==1 and b'1024' in e
 p['known_holds'][0]['text_SHA256']='0'*64;must(lambda:run(payload,p=p))
test('exact knownreview rawline+id+textSHA retained and drift refused',known)
def scalar():
 o=obj();o['metadata']['author']='x'*4097;raw=line(o);r,why=v.row(1,0,len(raw),True,hashlib.sha256(raw).digest(),raw);assert r[5]&v.FLAGS['SCALAR_OVERFLOW'] and r[14] is None and 'scalar_overflow:author' in why
 assert v.family('https://x.pressbooks.pub/book/front-matter/introduction/',o['id'])=='https://x.pressbooks.pub/book/' and v.family('https://other.example/book/',o['id']) is None
 o['metadata']['license']='unknown';o['created']='not a date';raw=line(o);r,_=v.row(1,0,len(raw),True,hashlib.sha256(raw).digest(),raw);assert r[5]&v.FLAGS['UNKNOWN_LICENSE_METADATA'] and r[5]&v.FLAGS['UNSUPPORTED_DATE_METADATA']
test('scalar overflow/date/license uncertainty and family lead never blanketclear',scalar)
def output():
 with tempfile.TemporaryDirectory() as z:
  out=Path(z)
  def stop(*a):raise ValueError('output prewrite stop')
  must(lambda:v.Sink(out/'frame.sqlite',{'SQLite_bytes':2000000},stop));assert not list(out.iterdir())
test('SQL/exception prewrite guard before any datafile',output)
def source():
 with tempfile.TemporaryDirectory() as z:
  p=Path(z).resolve()/'source';p.write_bytes(b'abc');b={'path':str(p),'stat':source_guard.ident(p.stat()),'bytes':3}
  with source_guard.opened(b,lambda:None) as read:assert read(3)==b'abc' and read(1)==b'';read.assert_custody()
  link=p.parent/'link';link.symlink_to(p)
  with patch.object(source_guard.os,'open',lambda *x:(_ for _ in ()).throw(AssertionError('must not open symlink'))):must(lambda:source_guard.opened({**b,'path':str(link)},lambda:None).__enter__())
  try:
   with source_guard.opened(b,lambda:None) as read:p.write_bytes(b'xyz');must(read.assert_custody)
  except ValueError:pass
  else:raise AssertionError('changed source context not refused')
test('read-only exactstat/EOF/symlink/inplace mutation custody',source)
def rss():
 for raw in ['', '999 1 -1','garbage','999 999 1','999 1 1\n999 1 2']:must(lambda raw=raw:pilot.tree_rss(raw,999))
 assert pilot.tree_rss('999 1 2\n1000 999 3',999,1000)==5*1024
test('strict observed process tree RSS failclosed',rss)
def early():
 old=pilot.ENTRY_START;pilot.ENTRY_START=pilot.clk()-599.98
 try:
  with patch.object(pilot,'verify',lambda a:time.sleep(.1)):
   try:pilot.supervise(types.SimpleNamespace())
   except TimeoutError:pass
   else:raise AssertionError('blocked preflight not interrupted')
 finally:pilot.ENTRY_START=old
 with tempfile.TemporaryDirectory() as z:
  p=Path(z);(p/'old').write_bytes(b'old')
  with patch.object(pilot,'verify',lambda a:({'output':str(p)},{})):must(lambda:pilot.supervise(types.SimpleNamespace()))
  assert list(p.iterdir())==[p/'old'] and (p/'old').read_bytes()==b'old'
test('actual early deadline and existing output preservation',early)
def worker_success():
 payload=line(obj());raw=gzip.compress(payload)
 with tempfile.TemporaryDirectory() as z:
  root=Path(z).resolve();out=root/'out';out.mkdir();source=root/'source';source.write_bytes(raw)
  p=profile(raw);p['output']=str(out);binding={'path':str(source),'stat':source_guard.ident(source.stat()),'bytes':len(raw),'SHA256':hashlib.sha256(raw).hexdigest()}
  for name,n in pilot.SLOTS.items():(out/name).write_bytes(b' '*n)
  a=types.SimpleNamespace(start=pilot.clk(),supervisor_pid=os.getppid(),profile_sha256='p',code_pins_sha256='c');(out/'ownership.json').write_text(json.dumps({'worker_PID':os.getpid(),'supervisor_PID':os.getppid(),'shared_start':a.start,'profile_SHA256':'p','codepins_SHA256':'c'}))
  with patch.object(pilot,'verify',lambda a:(p,binding)),patch.object(pilot,'guard',lambda out,start,seconds,extra=0,custody=None:custody() if custody else None):pilot.worker(a)
  r=json.loads((out/'result.json').read_text());assert r['status']=='COMPLETE_FIRST_SHARD_METADATA_FRAME_NO_ADMISSION' and r['rows']==1 and r['artifacts']['frame.sqlite']['SHA256']==hashlib.sha256((out/'frame.sqlite').read_bytes()).hexdigest()
  assert (out/'schema-holds.jsonl').read_bytes()==b'' and source.read_bytes()==raw
test('actual worker success full gzip/SQL/postflight after FDclose/metadata result',worker_success)
def census_rename(kind):
 from tree_size import census
 with tempfile.TemporaryDirectory() as z:
  root=Path(z).resolve();moving=root/('frame.sqlite-journal' if kind=='journal' else 'download.partial');moving.write_bytes(b'x'*65536);(root/'stable').write_bytes(b'stable');final=root/'download.gz';real=Path.stat;fired=[]
  def race(path,*a,**kw):
   if path==moving and not fired:
    fired.append(True)
    if kind=='journal':moving.unlink()
    else:moving.rename(final)
   return real(path,*a,**kw)
  with patch.object(Path,'stat',race):total=census(root)
  assert total==6+(65536 if kind=='rename' else 0) and fired
for kind in ['journal','rename']:test('shared census full restart exactbytes after '+kind,lambda kind=kind:census_rename(kind))
def census_churn():
 from tree_size import census
 with tempfile.TemporaryDirectory() as z:
  root=Path(z).resolve();calls=[]
  def gone(*a,**kw):calls.append(1);raise FileNotFoundError('synthetic churn')
  with patch.object(Path,'stat',gone):must(lambda:census(root))
  assert len(calls)==8
  calls=[]
  def denied(*a,**kw):calls.append(1);raise PermissionError('must propagate')
  with patch.object(Path,'stat',denied):must(lambda:census(root))
  assert len(calls)==1
test('shared census persistent8churn failclosed and othererrors notignored',census_churn)
def persist_lifecycle():
 with tempfile.TemporaryDirectory() as z:
  path=Path(z)/'frame.sqlite';sink=v.Sink(path,{'SQLite_bytes':2000000},lambda *a:None);journal=Path(str(path)+'-journal');assert journal.exists();inode=journal.stat().st_ino
  assert sink.db.execute('PRAGMA journal_mode').fetchone()==('persist',) and sink.db.execute('PRAGMA temp_store').fetchone()==(2,)
  payload=line(obj());sink.accept(1,0,len(payload),True,hashlib.sha256(payload).digest(),payload);assert journal.exists();sink.commit();assert journal.stat().st_ino==inode
  payload2=line(obj(2));sink.accept(2,len(payload),len(payload2),True,hashlib.sha256(payload2).digest(),payload2);sink.db.rollback();assert journal.exists() and journal.stat().st_ino==inode;sink.close();assert journal.exists() and journal.stat().st_ino==inode
  assert journal.stat().st_size<=8000000 and (not journal.read_bytes()[:28].strip(b'\x00'))
  db=sqlite3.connect(path);assert db.execute('SELECT count(*) FROM records').fetchone()==(1,) and db.execute('PRAGMA integrity_check').fetchone()==('ok',);db.close()
  assert not list(path.parent.glob('*-wal')) and not list(path.parent.glob('*-shm'))
test('actual PERSIST journal stable inode through commit/rollback/close, zeroheader and integrity',persist_lifecycle)
def persist_full():
 with tempfile.TemporaryDirectory() as z:
  path=Path(z)/'frame.sqlite';sink=v.Sink(path,{'SQLite_bytes':65536},lambda *a:None);journal=Path(str(path)+'-journal');inode=journal.stat().st_ino;large=obj();large['metadata']['title']='a'*4096;large['metadata']['author']='b'*4096;large['metadata']['institution']='c'*4096;large['metadata']['subject']='d'*4096;payload=line(large);failed=False
  try:
   for i in range(1,30):sink.accept(i,(i-1)*len(payload),len(payload),True,hashlib.sha256(payload).digest(),payload)
  except sqlite3.DatabaseError:failed=True;sink.db.rollback()
  finally:sink.close()
  assert failed and journal.exists() and journal.stat().st_ino==inode and journal.stat().st_size<=8000000
  db=sqlite3.connect(path);assert db.execute('PRAGMA integrity_check').fetchone()==('ok',);db.close()
test('actual PERSIST SQLfull fault rollback/close keeps journal path/inode',persist_full)
def journal_hardguard():
 with tempfile.TemporaryDirectory() as z:
  path=Path(z)/'frame.sqlite';sink=v.Sink(path,{'SQLite_bytes':2000000},lambda *a:None);journal=Path(str(path)+'-journal');real=Path.stat;payload=line(obj())
  def fake(p,*a,**kw):
   result=real(p,*a,**kw)
   if p==journal:return types.SimpleNamespace(st_size=8000001)
   return result
  try:
   with patch.object(Path,'stat',fake):must(lambda:sink.accept(1,0,len(payload),True,hashlib.sha256(payload).digest(),payload))
   sink.db.rollback()
  finally:sink.close()
test('PERSIST actual inserted-row journal8MB hardreserve refusal',journal_hardguard)
print(json.dumps({'status':'PASS_SYNTHETIC_ONLY','count':len(names),'names':names,'retained_source_bytes_read':0,'network_requests':0},indent=2))
