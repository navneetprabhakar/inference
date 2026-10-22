import contextlib,gzip,hashlib,io,json,os,sqlite3,tempfile,time,types
from pathlib import Path
from unittest.mock import patch
import inventory as v,pilot,source_guard
names=[]
def test(n,f):f();names.append(n)
def must(f):
 try:f()
 except Exception:return
 raise AssertionError('accepted')
def obj(i=1):return {'id':f'daylord2001-04-04a-{i}','text':'Whole day: Café 😀. Question? Answer.','source':'uk-hansard-lords-debates','added':'2024-06-01','metadata':{'year':'2001','language':'en','license':'Open Parliament Licence - https://www.parliament.uk/site-information/copyright-parliament/open-parliament-licence/'}}
def line(o):return (json.dumps(o,ensure_ascii=False)+'\n').encode()
def fixture(root,payloads):
 inputs=[]
 for sid,payload in enumerate(payloads,1):
  raw=gzip.compress(payload);f=root/f'{sid}.gz';f.write_bytes(raw);inputs.append({'source_id':sid,'path':str(f),'stat':source_guard.ident(f.stat()),'bytes':len(raw),'SHA256':hashlib.sha256(raw).hexdigest()})
 return {'inputs':inputs,'limits':{'parsed_record_bytes':16000000,'encountered_records':500000,'decoded_bytes':10000000000,'SQLite_bytes':2000000}}
def run(payloads,change=lambda p:None):
 with tempfile.TemporaryDirectory() as z:
  root=Path(z).resolve();p=fixture(root,payloads);change(p);out=root/'out';out.mkdir();r=v.run(p,out,source_guard.opened,lambda *a:None);db=sqlite3.connect(out/'frame.sqlite');rows=db.execute('SELECT * FROM records ORDER BY source_id,ordinal').fetchall();db.close();return r,rows,(out/'schema-holds.jsonl').read_bytes()
def coverage():
 a=line(obj());extra=obj(2);extra['metadata']['speaker']='unsupported but sourcebacked'
 payloads=[a+b'{"id":"x","id":"y"}\n'+b'null\n',line(extra)+b'{"text":"\xff"}\n'];r,rows,ex=run(payloads);assert r['rows']==5 and len(rows)==5 and len(ex.splitlines())==4
 for x in rows:assert hashlib.sha256(payloads[x[0]-1][x[2]:x[2]+x[3]]).digest()==x[5]
 assert rows[0][13]==hashlib.sha256(obj()['text'].encode()).digest() and rows[0][14]==len(obj()['text'].encode()) and rows[0][15]==len(obj()['text']);assert rows[1][6]&4 and rows[2][6]&8 and rows[3][6]&16 and rows[4][6]&2
 assert r['decoded_total_bytes']==sum(map(len,payloads)) and len(r['counts'])==2 and all(c['gzip_CRC_EOF_members']==1 for c in r['counts'])
test('two sources all5rawrows locator/textSHA/types/unknownmetadata no skips',coverage)
def endings():
 p=line(obj()).replace(b'\n',b'\r\n');r,rows,_=run([p,line(obj()).rstrip(b'\n')]);assert rows[0][4]==1 and rows[1][4]==0 and rows[1][2]==0
test('independent fileoffsets CRLF/finalnonLF',endings)
def oversized():
 seen=[];l=v.Lines(20,5,lambda *a:seen.append(a));raw=b'x'*100+b'\n{}\n'
 for i in range(0,len(raw),7):l.add(raw[i:i+7])
 l.finish();assert len(seen)==2 and seen[0][5] is None and seen[0][4]==hashlib.sha256(raw[:101]).digest() and seen[1][1]==101
test('oversize wholeline hold hashed fixedchunks no splicing',oversized)
def members():
 a=line(obj());raw=gzip.compress(a)+gzip.compress(a);buf=io.BytesIO(raw);out=[];c=v.gzip_stream(lambda n:buf.read(min(n,1)),out.append,{'compressed_bytes':len(raw),'decoded_bytes':100000},lambda:None);assert c['gzip_CRC_EOF_members']==2 and b''.join(out)==a+a
test('multiple gzip members 1byte read CRC/EOF',members)
for label,transform in [('truncated',lambda b:b[:-4]),('CRC',lambda b:b[:-8]+bytes([b[-8]^1])+b[-7:]),('trailing',lambda b:b+b'garbage')]:
 def bad(transform=transform):
  raw=transform(gzip.compress(line(obj())));must(lambda:v.gzip_stream(io.BytesIO(raw).read,lambda x:None,{'compressed_bytes':len(raw),'decoded_bytes':100000},lambda:None))
 test('gzip '+label+' refuses complete',bad)
for name,change in [('combined rows',lambda p:p['limits'].update(encountered_records=1)),('combined decoded',lambda p:p['limits'].update(decoded_bytes=len(line(obj()))+5)),('sourceSHA',lambda p:p['inputs'][1].update(SHA256='0'*64))]:test(name+' partial not complete',lambda change=change:must(lambda:run([line(obj()),line(obj())],change)))
def scalar():
 o=obj();o['id']='x'*4097;o['metadata']['year']=2001;o['added']='yesterday';raw=line(o);r,reason=v.row(1,1,0,len(raw),True,hashlib.sha256(raw).digest(),raw);assert r[6]&16 and r[6]&32 and r[6]&64 and r[6]&256 and r[7] is None and r[10] is None
 raw=b'{"metadata":{"year":"1","year":"2"}}\n';r,_=v.row(1,1,0,len(raw),True,hashlib.sha256(raw).digest(),raw);assert r[6]&4 and all(x is None for x in r[7:])
test('scalar/type/date/year/nestedduplicate holds sourcebacked',scalar)
def unicode():
 raw=b'{"text":"\\ud800"}\n';r,_=v.row(1,1,0,len(raw),True,hashlib.sha256(raw).digest(),raw);assert r[6]&2
 raw=b'{"text":NaN}\n';assert v.row(1,1,0,len(raw),True,hashlib.sha256(raw).digest(),raw)[0][6]&4
test('surrogate/nonstandardconstants held',unicode)
def prewrite():
 with tempfile.TemporaryDirectory() as z:
  def no(*a):raise ValueError('cap')
  must(lambda:v.Sink(Path(z)/'frame.sqlite',{'SQLite_bytes':2000000},no,[]));assert not list(Path(z).iterdir())
test('outputprewrite before creation',prewrite)
def source():
 with tempfile.TemporaryDirectory() as z:
  p=Path(z).resolve()/'a';p.write_bytes(b'x');b={'path':str(p),'stat':source_guard.ident(p.stat()),'bytes':1}
  with source_guard.opened(b,lambda:None) as f:assert f(1)==b'x' and f(1)==b''
  link=p.with_name('b');link.symlink_to(p);must(lambda:source_guard.opened({**b,'path':str(link)},lambda:None).__enter__())
  try:
   with source_guard.opened(b,lambda:None) as f:p.write_bytes(b'z');must(f.assert_custody)
  except ValueError:pass
  else:raise AssertionError('mutation')
test('RO stat/FD EOF/symlink/mutation guards',source)
def rss():
 for s in ['', 'bad','1 1 2','10 1 -1','10 1 2\n10 1 3']:must(lambda s=s:pilot.tree_rss(s,10))
 assert pilot.tree_rss('10 1 2\n11 10 3',10,11)==5120
test('RSS failclosed and ownedtree exact',rss)
def lifecycle():
 old=pilot.ENTRY_START;pilot.ENTRY_START=pilot.clk()-1194.98
 try:
  with patch.object(pilot,'verify',lambda a:time.sleep(.1)):must(lambda:pilot.supervise(types.SimpleNamespace()))
 finally:pilot.ENTRY_START=old
 with tempfile.TemporaryDirectory() as z:
  p=Path(z);(p/'old').write_bytes(b'x')
  with patch.object(pilot,'verify',lambda a:{'output':str(p)}):must(lambda:pilot.supervise(types.SimpleNamespace()))
  assert list(p.iterdir())==[p/'old']
test('actual earlypreflightdeadline/existingOUT unchanged',lifecycle)
def worker():
 with tempfile.TemporaryDirectory() as z:
  root=Path(z).resolve();p=fixture(root,[line(obj()),line(obj(2))]);out=root/'out';out.mkdir();p['output']=str(out)
  for n,b in pilot.SLOTS.items():(out/n).write_bytes(b' '*b)
  a=types.SimpleNamespace(start=pilot.clk(),supervisor_pid=os.getppid(),profile_sha256='p',code_pins_sha256='c');(out/'ownership.json').write_text(json.dumps({'worker_PID':os.getpid(),'supervisor_PID':os.getppid(),'shared_start':a.start,'profile_SHA256':'p','codepins_SHA256':'c'}))
  with patch.object(pilot,'verify',lambda a:p),patch.object(pilot,'guard',lambda *a:None):pilot.worker(a)
  r=json.loads((out/'result.json').read_text());assert r['rows']==2 and r['status'].startswith('COMPLETE_') and r['artifacts']['frame.sqlite']['SHA256']==hashlib.sha256((out/'frame.sqlite').read_bytes()).hexdigest()
test('actual twoFD worker EOF/fullhash/SQL/postflight/streamartifacthash',worker)
def persist():
 with tempfile.TemporaryDirectory() as z:
  p=Path(z)/'frame.sqlite';s=v.Sink(p,{'SQLite_bytes':65536},lambda *a:None,[{'source_id':1,'path':'synthetic','SHA256':'0'*64,'bytes':1}]);j=Path(str(p)+'-journal');inode=j.stat().st_ino
  raw=line(obj());s.accept(1,1,0,len(raw),True,hashlib.sha256(raw).digest(),raw);s.commit()
  try:
   for i in range(2,1000):s.db.execute('INSERT INTO records SELECT source_id,?,line_offset,line_bytes,ends_LF,line_SHA256,flags,id,source,added,year,language,license,text_SHA256,text_UTF8_bytes,text_chars FROM records LIMIT 1',(i,))
  except sqlite3.DatabaseError:pass
  else:raise AssertionError('expected SQLFULL')
  s.db.rollback();s.close();assert j.exists() and j.stat().st_ino==inode and j.stat().st_size<=8000000
  db=sqlite3.connect(p);assert db.execute('SELECT count(*) FROM records').fetchone()==(1,);db.close()
test('PERSIST journal through commit/SQLFULL/rollback/close sameinode',persist)
print(json.dumps({'status':'PASS_SYNTHETIC_ONLY','controls':len(names),'names':names,'retained_source_body_reads':0},indent=2))
