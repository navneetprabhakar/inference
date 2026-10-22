"""Authorized once-only bounded first-record schema discovery; no network."""
import time
START=time.clock_gettime(time.CLOCK_MONOTONIC)
import hashlib,json,os,signal,stat,sys,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent

def clock():return time.clock_gettime(time.CLOCK_MONOTONIC)
def sha(b):return hashlib.sha256(b).hexdigest()
def ident(s):return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
def alarm(*args):raise TimeoutError('30sec_discovery_cap')
def first_record(read,compressed_cap=1000000,decoded_cap=2000000,record_cap=1000000):
 d=zlib.decompressobj(16+zlib.MAX_WBITS);compressed=0;decoded=0;buf=bytearray();pending=b''
 while True:
  if not pending:
   if compressed>=compressed_cap:raise ValueError('compressed_cap_before_complete_first_record')
   pending=read(min(65536,compressed_cap-compressed));compressed+=len(pending)
   if not pending:raise ValueError('compressed_EOF_before_first_record')
  if decoded>=decoded_cap:raise ValueError('decoded_cap_before_complete_first_record')
  raw=d.decompress(pending,max_length=min(65536,decoded_cap-decoded));pending=d.unconsumed_tail;decoded+=len(raw);buf.extend(raw)
  end=buf.find(b'\n')
  if end>=0:
   line=bytes(buf[:end+1])
   if len(line)>record_cap:raise ValueError('first_record_cap')
   record=json.loads(line.decode('utf8',errors='strict'))
   if type(record) is not dict:raise ValueError('first_record_not_dictionary_JSONL')
   return record,line,{'compressed_bytes_read':compressed,'decoded_bytes_emitted':decoded,'first_record_bytes':len(line),'first_record_SHA256':sha(line),'gzip_member_EOF_observed':d.eof,'whole_shard_CRC_EOF_not_claimed':True}
  if len(buf)>record_cap:raise ValueError('first_record_cap_no_truncation')
  if d.eof:raise ValueError('first_record_no_complete_LF_framing_before_member_EOF')
def fields(x,path='$',depth=0):
 if depth>16:return [{'path':path,'type':type(x).__name__,'schema_depth_bound':True}]
 out=[{'path':path,'type':type(x).__name__}]
 if isinstance(x,dict):
  for k,v in x.items():out+=fields(v,path+'.'+k,depth+1)
 elif isinstance(x,list):out[0]['items']=len(x);out[0]['item_types']=sorted({type(v).__name__ for v in x})
 elif isinstance(x,str):out[0]['UTF8_bytes']=len(x.encode())
 if len(out)>4096:raise ValueError('schema_field_count_cap')
 return out

def checks():
 import io,gzip
 b=b'{"text":"English example","metadata":{"license":"CC-BY"}}\n'+b'{"text":"next"}\n'
 r,line,stats=first_record(io.BytesIO(gzip.compress(b)).read);assert r['metadata']['license']=='CC-BY' and line==b.splitlines(keepends=True)[0]
 for raw,kw in [(gzip.compress(b),{'record_cap':4}),(b'notgzip',{}),(gzip.compress(b'{"x":"\xff"}\n'),{}),(gzip.compress(b),{'compressed_cap':1})]:
  try:first_record(io.BytesIO(raw).read,**kw)
  except Exception:pass
  else:raise AssertionError('bound/schema fault accepted')
 return {'status':'PASS','controls':5,'retained_source_bytes':0}

def main():
 if '--checks' in sys.argv:print(json.dumps(checks()));return
 signal.signal(signal.SIGALRM,alarm);signal.setitimer(signal.ITIMER_REAL,max(.001,30-(clock()-START)))
 p=json.loads((HERE/'profile.json').read_text());registry=json.loads((HERE/'code-pins.json').read_text())['SHA256']
 if sha((HERE/'code-pins.json').read_bytes())!=sys.argv[sys.argv.index('--code-pins-sha256')+1]:raise ValueError('external_codepins')
 if set(registry)!={str(HERE/'profile.json'),str(HERE/'discover.py'),p['integrity_receipt'],p['python']} :raise ValueError('exact_inventory')
 for path,h in registry.items():
  if sha(Path(path).read_bytes())!=h:raise ValueError('input_pin')
 if str(Path(sys.executable).resolve())!=p['python']:raise ValueError('runtime')
 receipt=json.loads(Path(p['integrity_receipt']).read_text());assert receipt['path']==p['source'] and receipt['stat']==p['source_stat'] and receipt['SHA256']==p['source_SHA256']
 out=Path(p['output']);created=False;fd=None;existed=out.exists()
 try:
  if out.exists():raise ValueError('no_retry_existing_output')
  source=Path(p['source']);assert not source.is_symlink() and ident(source.stat())==p['source_stat'];fd=os.open(source,os.O_RDONLY|os.O_NOFOLLOW);assert ident(os.fstat(fd))==p['source_stat'] and stat.S_ISREG(os.fstat(fd).st_mode)
  def read(n):
   assert ident(os.fstat(fd))==p['source_stat'] and ident(source.stat())==p['source_stat'];return os.read(fd,n)
  record,line,counts=first_record(read)
  assert ident(os.fstat(fd))==p['source_stat'] and ident(source.stat())==p['source_stat'];os.close(fd);fd=None
  schema={'status':'COMPLETE_BIASED_FIRST_RECORD_SCHEMA_ONLY_NO_ADMISSION','scope':'One complete first physical JSONL record; not representative, no whole-shard EOF/CRC, quality, rights or usable counts claim.','all_fields':fields(record),'top_level_keys':list(record),'first_record_counts':counts,'source_SHA256_inherited':p['source_SHA256'],'source_stat':p['source_stat'],'elapsed_seconds':clock()-START,'new_admitted_documents':0}
  outputs={'first-record.jsonl':line,'schema.json':(json.dumps(schema,indent=2,ensure_ascii=False)+'\n').encode()};assert sum(map(len,outputs.values()))<4000000
  out.mkdir();created=True
  for name,raw in outputs.items():
   with (out/name).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
  result={'status':schema['status'],'outputs':{n:{'bytes':len(raw),'SHA256':sha(raw)} for n,raw in outputs.items()},'counts':counts,'elapsed_seconds':clock()-START,'new_admitted_documents':0}
  raw=(json.dumps(result,indent=2)+'\n').encode();assert sum(map(len,outputs.values()))+len(raw)<4000000;(out/'result.json').write_bytes(raw);print(json.dumps(result))
 except BaseException as error:
  if not existed:
   out.mkdir(exist_ok=True);(out/'result.json').write_text(json.dumps({'status':'TERMINAL_BOUNDED_DISCOVERY_STOP_NO_RETRY','error':type(error).__name__+':'+str(error)[:1000],'source_bytes_read_unreported_on_stop':True,'elapsed_seconds':clock()-START,'new_admitted_documents':0},indent=2)+'\n')
  raise
 finally:
  if fd is not None:os.close(fd)
  signal.setitimer(signal.ITIMER_REAL,0)
if __name__=='__main__':main()
