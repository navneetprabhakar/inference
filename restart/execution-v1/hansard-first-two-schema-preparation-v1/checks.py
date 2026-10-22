import gzip,hashlib,io,json,tempfile,types,time,os
from pathlib import Path
from unittest.mock import patch
import core,run
names=[]
def test(n,f):f();names.append(n)
def refuse(f):
 try:f()
 except (ValueError,UnicodeError,TimeoutError):return
 raise AssertionError('accepted')
def record():
 raw=b'{"id":"one","text":"hello","metadata":{"speaker":"A","date":"1900"}}\n';blob=gzip.compress(raw+b'junk\n');b=core.Budget(2000000);line,r=core.first(io.BytesIO(blob).read,b,lambda:None)
 assert line==raw and r['raw_line_SHA256']==hashlib.sha256(raw).hexdigest() and not r['whole_gzip_CRC_EOF_validation_claimed'];d=core.describe(core.parse(line));assert d['all_nontext_fields_exact']['metadata']['speaker']=='A' and d['text_UTF8_bytes']==5
test('whole firstline exact metadata/hash, later garbage not parsed',record)
test('oversized complete line refuses no truncation',lambda:refuse(lambda:core.first(io.BytesIO(gzip.compress(b'x'*100+b'\n')).read,core.Budget(1000),lambda:None,line_cap=100)))
test('decoded cap before parse',lambda:refuse(lambda:core.first(io.BytesIO(gzip.compress(b'x'*100+b'\n')).read,core.Budget(1000),lambda:None,decoded_cap=50)))
def shared():
 b=core.Budget(30);core.first(io.BytesIO(gzip.compress(b'{}\n')).read,b,lambda:None);refuse(lambda:core.first(io.BytesIO(gzip.compress(b'{}\n')).read,b,lambda:None))
test('shared compressed cap across both files',shared)
test('EOF missing complete physical LF refuses',lambda:refuse(lambda:core.first(io.BytesIO(gzip.compress(b'{}')).read,core.Budget(1000),lambda:None)))
test('duplicate nested JSON keys refuses',lambda:refuse(lambda:core.parse(b'{"metadata":{"a":1,"a":2}}\n')))
test('UTF8 surrogate/nonfinite JSON refuses',lambda:[refuse(lambda:core.parse(x)) for x in [b'{"x":"\xff"}\n',b'{"x":"\\ud800"}\n',b'{"x":NaN}\n']])
test('RSS empty malformed missingroot failsclosed',lambda:[refuse(lambda:run.rss(s,100)) for s in ['', '100 1 -1','101 1 10']])
test('RSS actual tree accounting',lambda: (_ for _ in ()).throw(AssertionError()) if run.rss('100 1 2\n101 100 3\n',100,101)!=5120 else None)
def outold():
 with tempfile.TemporaryDirectory() as z:
  p=Path(z);(p/'old').write_bytes(b'x')
  with patch.object(run,'verify',lambda a:{'output':str(p)}):refuse(lambda:run.supervise(types.SimpleNamespace()))
  assert (p/'old').read_bytes()==b'x' and len(list(p.iterdir()))==1
test('actual supervisor refuses existing OUT unchanged',outold)
def deadline():
 old=run.START;run.START=run.clk()-26.98
 try:
  with patch.object(run,'verify',lambda a:time.sleep(.1)):refuse(lambda:run.supervise(types.SimpleNamespace()))
 finally:run.START=old
test('actual preflight deadline alarm before IO',deadline)
def worker_success():
 with tempfile.TemporaryDirectory() as z:
  root=Path(z);out=root/'out';out.mkdir();inputs=[]
  for i in range(2):
   path=root/f'{i}.gz';path.write_bytes(gzip.compress(json.dumps({'id':i,'text':'Hello whole text','metadata':{'speaker':'S','date':'1900-01-01'}}).encode()+b'\n'))
   inputs.append({'path':str(path),'stat':run.ident(path.stat()),'SHA256':run.h(path),'source_ordinal':i})
  a=types.SimpleNamespace(start=run.clk(),parent=os.getppid(),profile_sha256='p',code_pins_sha256='c')
  for name in ['result.json','supervisor.json']:(out/name).write_bytes(b' '*run.SLOT)
  (out/'ownership.json').write_text(json.dumps({'supervisor_PID':a.parent,'worker_PID':os.getpid(),'start':a.start,'profile_SHA256':'p','codepins_SHA256':'c'}))
  with patch.object(run,'verify',lambda a:{'output':str(out),'inputs':inputs}):run.worker(a)
  r=json.loads((out/'result.json').read_text());assert len(r['records'])==2 and r['status'].startswith('COMPLETE_') and not r['whole_gzip_CRC_EOF_validation_claimed']
  assert (out/'record-0.jsonl').read_bytes()==gzip.decompress(Path(inputs[0]['path']).read_bytes())
test('actual worker two sourceFD lifecycles/postflight/rawcopy',worker_success)
print(json.dumps({'status':'PASS_SYNTHETIC_ONLY','controls':len(names),'names':names,'retained_source_body_reads':0},indent=2))
