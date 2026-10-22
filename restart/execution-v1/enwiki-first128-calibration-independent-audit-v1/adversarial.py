"""Only tiny synthetic bytes plus read-only pinned code/metadata; no source open."""
import bz2,contextlib,copy,hashlib,io,json,os,signal,sqlite3,sys,tempfile,types
from pathlib import Path
from unittest.mock import patch
BASE=Path(__file__).resolve().parent.parent;PREP=BASE/'enwiki-first128-calibration-preparation-v1';sys.path.insert(0,str(PREP))
with contextlib.redirect_stdout(io.StringIO()) as output:import checks
import pilot,engine,source_guard
baseline=json.loads(output.getvalue());assert baseline['count']==30
results=[]
def test(name,fn):fn();results.append(name)
def fail_engine(transform,committed=0):
 with tempfile.TemporaryDirectory() as z:
  out=Path(z);p,s,r,b=transform(*checks.fixture())
  try:engine.run(p,s,r,lambda off,n:b[off:off+n],out,lambda n=0:None)
  except BaseException:
   db=sqlite3.connect(out/'frame.sqlite');assert db.execute('SELECT count(*) FROM groups').fetchone()==(committed,);assert db.execute('PRAGMA integrity_check').fetchone()==('ok',);db.close();return
  raise AssertionError('unexpected complete')
def change_group(transform):
 def fn(p,s,r,b):
  parts=[b[:s['header_bytes']]];position=len(parts[0])
  for i,g in enumerate(s['groups']):
   raw=bz2.decompress(b[g['compressed_start']:g['compressed_end_exclusive']]);changed=transform(i,raw);part=bz2.compress(changed);g['compressed_start']=position;position+=len(part);g['compressed_end_exclusive']=position;g['compressed_bytes']=len(part);parts.append(part)
  s['compressed_prefix_end_exclusive']=p['limits']['compressed_bytes']=position
  return p,s,r,b''.join(parts)
 return fn
for label,change in [
 ('split_page_across_group',lambda i,b:b[:-7] if i==0 else b),
 ('extra_native_page',lambda i,b:b+checks.page(4) if i==0 else b),
 ('revision_ID_missing',lambda i,b:b.replace(b'<id>11</id>',b'') if i==0 else b),
 ('direct_ID_missing',lambda i,b:b.replace(b'<id>1</id>',b'') if i==0 else b),
 ('wrong_title',lambda i,b:b.replace(b'<title>T1</title>',b'<title>Wrong</title>') if i==0 else b),
 ('reordered_pages',lambda i,b:checks.page(2)+checks.page(1) if i==0 else b),
 ('DTD_entity',lambda i,b:b'<!DOCTYPE x [<!ENTITY x SYSTEM "file:///never">]>'+b if i==0 else b),
]:test(label+' terminal group rollback',lambda change=change:fail_engine(change_group(change)))
def trailing(p,s,r,b):
 g=s['groups'][0];at=g['compressed_end_exclusive'];b=b[:at]+b'x'+b[at:]
 g['compressed_end_exclusive']+=1;g['compressed_bytes']+=1
 s['groups'][1]['compressed_start']+=1;s['groups'][1]['compressed_end_exclusive']+=1
 s['compressed_prefix_end_exclusive']+=1;p['limits']['compressed_bytes']+=1;return p,s,r,b
test('trailing nongzip garbage after CRC cannot commit group',lambda:fail_engine(trailing))
def crc_after_pages(p,s,r,b):
 g=s['groups'][0];at=g['compressed_end_exclusive'];chunk=bytearray(b[g['compressed_start']:at]);chunk[-4]^=1;return p,s,r,b[:g['compressed_start']]+bytes(chunk)+b[at:]
test('late CRC damage after callbacks leaves no committed page',lambda:fail_engine(crc_after_pages))
def second_bad(p,s,r,b):
 r[2][3]='Wrong';return p,s,r,b
test('second group failure retains only prior group',lambda:fail_engine(second_bad,1))
def header_bad(p,s,r,b):
 h=bz2.compress(checks.H.replace(b'https://en.wikipedia.org/wiki/Main_Page',b'https://evil.invalid/wiki/Main_Page'));delta=len(h)-s['header_bytes'];b=h+b[s['header_bytes']:];s['header_bytes']=len(h)
 for g in s['groups']:g['compressed_start']+=delta;g['compressed_end_exclusive']+=delta
 s['compressed_prefix_end_exclusive']+=delta;p['limits']['compressed_bytes']+=delta;return p,s,r,b
test('actual bad base root holds prohibit first commit',lambda:fail_engine(header_bad))
def codec_states():
 with tempfile.TemporaryDirectory() as z:
  p,s,r,b=checks.fixture();raw=checks.page(1).replace(b'<text>Exact synthetic prose.</text>',b'<text bytes="0" deleted="deleted"/>')+checks.page(2)+checks.page(3)
  header=bz2.compress(checks.H);data=bz2.compress(raw);s={'rows':3,'header_bytes':len(header),'compressed_prefix_end_exclusive':len(header)+len(data),'groups':[{'group_ordinal':1,'compressed_start':len(header),'compressed_end_exclusive':len(header)+len(data),'compressed_bytes':len(data),'first_row_ordinal':1,'last_row_ordinal':3,'index_rows':3}]};p['limits']['compressed_bytes']=len(header)+len(data)
  rr=[[i,1,i,'T'+str(i)] for i in range(1,4)];body=header+data;out=Path(z);result=engine.run(p,s,rr,lambda x,n:body[x:x+n],out,lambda n=0:None)
  db=sqlite3.connect(out/'frame.sqlite');flags,n=db.execute('SELECT flags,main_text_bytes FROM pages WHERE row_ordinal=1').fetchone();assert flags & (1<<6);assert flags & (1<<2);db.close()
  assert b'DELETED' in (out/'exceptions.jsonl').read_bytes()
test('deleted text remains held finite flags and explicit exception',codec_states)
def ownership_refusal():
 with tempfile.TemporaryDirectory() as z:
  out=Path(z);p,s,r,b=checks.fixture();p['output']=str(out);arg=types.SimpleNamespace(start=pilot.clk(),supervisor_pid=os.getppid(),profile_sha256='x',code_pins_sha256='y')
  (out/'ownership.json').write_text(json.dumps({'worker_PID':os.getpid()+1,'supervisor_PID':os.getppid(),'shared_start':arg.start,'profile_SHA256':'x','codepins_SHA256':'y'}))
  with patch.object(pilot,'verify',lambda a:(p,s,r,{})),patch.object(source_guard,'opened',lambda *a:(_ for _ in ()).throw(AssertionError('must not open'))):
   try:pilot.worker(arg)
   except ValueError as e:assert str(e)=='owned_worker_receipt'
   else:raise AssertionError('ownership accepted')
  assert not (out/'frame.sqlite').exists()
test('production wrong ownership refuses source opening',ownership_refusal)
def custody_path_swap():
 with tempfile.TemporaryDirectory() as z:
  p=Path(z).resolve()/'a';p.write_bytes(b'abc');binding={'path':str(p),'stat':source_guard.ident(p.stat())}
  try:
   with source_guard.opened(binding,lambda:None) as read:
    assert read(0,1)==b'a';q=p.with_name('old');p.rename(q);p.write_bytes(b'abc');read.assert_custody()
  except ValueError as e:assert str(e)=='source_guard_stat_changed'
  else:raise AssertionError('swapped path accepted')
test('same bytes replacement inode refused while FD remains open',custody_path_swap)
def postflight_failure():
 with tempfile.TemporaryDirectory() as z:
  out=Path(z);p,s,r,b=checks.fixture();p['output']=str(out);source=out/'synthetic';source.write_bytes(b);binding={'path':str(source),'stat':source_guard.ident(source.stat()),'SHA256':hashlib.sha256(b).hexdigest()}
  for n,c in pilot.SLOTS.items():(out/n).write_bytes(b' '*c)
  arg=types.SimpleNamespace(start=pilot.clk(),supervisor_pid=os.getppid(),profile_sha256='x',code_pins_sha256='y');(out/'ownership.json').write_text(json.dumps({'worker_PID':os.getpid(),'supervisor_PID':os.getppid(),'shared_start':arg.start,'profile_SHA256':'x','codepins_SHA256':'y'}))
  @contextlib.contextmanager
  def reader(binding,check):
   def read(off,n):return b[off:off+n]
   read.assert_custody=lambda:None;yield read
  calls=[0]
  def verify(a):
   calls[0]+=1
   if calls[0]>1:raise ValueError('postflight_code_pin_change')
   return p,s,r,binding
  with patch.object(pilot,'verify',verify),patch.object(source_guard,'verify',lambda p:binding),patch.object(source_guard,'opened',reader),patch.object(pilot,'guard',lambda *a,**k:None):
   try:pilot.worker(arg)
   except ValueError as e:assert str(e)=='postflight_code_pin_change'
   else:raise AssertionError('postflight bypassed')
  assert json.loads((out/'result.json').read_text())['status']=='PARTIAL_CALIBRATION_NO_RETRY'
test('actual postflight pin error preserves partial not COMPLETE',postflight_failure)

def metadata_pins():
 def sha(p):
  with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
 assert sha(PREP/'readiness.json')=='3ef4afb65f5e4f1b927995f735592c38f6df60b8184ea7738444e8b3ab69aafc'
 assert sha(PREP/'profile.json')=='0d582266ff29bf118f6df3ef37a3a644c1254372a58cc8fe5338ec7bf503fee2'
 assert sha(PREP/'code-pins.json')=='dc8d9f4ea3506df0657da54c3930dd28c3435beb41ece34e9b4e79c6e32026b7'
 pins=json.loads((PREP/'code-pins.json').read_text())['SHA256'];assert len(pins)==47
 for path,h in pins.items():assert sha(Path(path))==h
 profile=json.loads((PREP/'profile.json').read_text());assert set(pins)==pilot.required(profile)
 # Only code/small transport/source metadata and frozen index selection rows.
 assert all(Path(path).stat().st_size<8000000 for path in pins)
 assert not any(path.endswith(('assembled.partial','.sqlite','.bz2')) for path in pins)
 return len(pins)
count=metadata_pins();results.append('all47 exact code metadata pins no retained corpus body')
print(json.dumps({'status':'PASS','baseline':baseline,'independent_controls':len(results),'independent':results,'pins':count,'source_body_reads':0,'network_requests':0,'global_ledger_operations':0},indent=2))
