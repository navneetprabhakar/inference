"""Bounded exact-range transport and ordered-file hashing; no ledger or retries."""
import hashlib,json,os,pathlib,threading,time,urllib.request
CHUNK=1048576;HEADER_CAP=65536

def stat_id(p):
 s=pathlib.Path(p).stat();return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
def partition(start,total,width):
 if not all(type(v)is int for v in [start,total,width]) or not 0<=start<total or width<1:raise ValueError('range_frame')
 return [{'ordinal':i,'start':a,'end':min(a+width,total)-1,'bytes':min(width,total-a)} for i,a in enumerate(range(start,total,width))]
def header_packet(response):
 raw=b''.join((k+': '+v+'\r\n').encode('latin1') for k,v in response.headers.items())
 return raw,{'status':response.code,'URL':response.geturl(),'header_bytes':len(raw),'SHA256':hashlib.sha256(raw).hexdigest(),'prefix_hex':raw[:HEADER_CAP].hex(),'prefix_only':len(raw)>HEADER_CAP}
def validate(response,raw,part,url,total,etag):
 if len(raw)>HEADER_CAP:raise ValueError('aggregate_header_cap')
 if response.code!=206 or response.geturl()!=url:raise ValueError('exact206_URL_nofallback')
 h=response.headers
 for k,v in [('Content-Length',str(part['bytes'])),('Content-Range',f"bytes {part['start']}-{part['end']}/{total}"),('ETag',etag)]:
  if h.get_all(k,[])!=[v]:raise ValueError('exact_single_'+k)
 if h.get_all('Content-Encoding',[]) not in [[],['identity']] or h.get_all('Transfer-Encoding',[]):raise ValueError('identity_only_no_transferencoding')
class StartGate:
 """Lock covers open-through-headers, so actual open invocations cannot reorder."""
 def __init__(self,clock=time.clock_gettime):self.lock=threading.Lock();self.last=None;self.starts=[];self.clock=lambda:clock(time.CLOCK_MONOTONIC)
 def open(self,opener,request,guard):
  with self.lock:
   while self.last is not None and self.clock()-self.last<1:
    guard();time.sleep(min(.05,1-(self.clock()-self.last)))
   guard();started=self.clock();self.starts.append(started)
   try:response=opener.open(request,timeout=30)
   finally:self.last=self.clock() # >=1s after prior header phase, stronger than start spacing
   return response,started

def receive(response,path,length,guard,progress):
 n=0;h=hashlib.sha256();path=pathlib.Path(path)
 with path.open('xb') as f:
  try:
   while n<=length:
    guard();b=response.read1(min(CHUNK,length+1-n))
    if not b:break
    n+=len(b)
    if n>length+1:raise ValueError('reader_exceeded_reserved_EOF')
    if f.write(b)!=len(b):raise OSError('short_local_write')
    h.update(b);progress(n,h.hexdigest())
    if n>length:raise ValueError('extra_reserved_EOF_byte_retained')
  finally:f.flush();os.fsync(f.fileno())
 if n!=length:raise ValueError('short_range_body')
 return {'bytes':n,'SHA256':h.hexdigest(),'stat':stat_id(path)}
def hash_components(components,guard):
 """No copying/concatenation on disk. Every component hash/stat checked."""
 whole=[hashlib.md5(),hashlib.sha1(),hashlib.sha256()];count=0;receipts=[]
 for e in components:
  path=pathlib.Path(e['path'])
  if path.is_symlink() or not path.is_file():raise ValueError('component_symlink_or_missing')
  before=stat_id(path)
  if before[2]!=e['bytes'] or e.get('stat',before)!=before:raise ValueError('component_size_or_stat')
  n=0;local=hashlib.sha256()
  with path.open('rb') as f:
   if [getattr(os.fstat(f.fileno()),k) for k in ['st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns']]!=before:raise ValueError('component_open_stat')
   while True:
    guard();b=f.read(CHUNK)
    if not b:break
    n+=len(b)
    if n>e['bytes']:raise ValueError('component_growth')
    local.update(b)
    for h in whole:h.update(b)
   after=[getattr(os.fstat(f.fileno()),k) for k in ['st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns']]
  if n!=e['bytes'] or local.hexdigest()!=e['SHA256'] or after!=before or stat_id(path)!=before:raise ValueError('component_hash_or_mutation')
  count+=n;receipts.append({'path':str(path),'bytes':n,'SHA256':local.hexdigest(),'stat':before})
 return {'bytes':count,'MD5':whole[0].hexdigest(),'SHA1':whole[1].hexdigest(),'SHA256':whole[2].hexdigest(),'components':receipts}
