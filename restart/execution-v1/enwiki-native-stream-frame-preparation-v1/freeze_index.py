"""One bounded first16-group metadata freeze; never reads native XML."""
import argparse,bz2,hashlib,json,os,pathlib,signal,sys,time
HERE=pathlib.Path(__file__).resolve().parent;BASE=HERE.parent;ROOT=BASE/'m2-intake';OUT=ROOT/'enwiki-first16-index-groups-v1'
INDEX=ROOT/'enwiki-native-index-20260801-v1/enwiki-20260801-pages-articles-multistream-index.txt.bz2'
SIZE=283588691;SHA='bffbe20df7a75a5b83984298614f1e20ebfd013faf62f46c489a10c7964bf1d1';MD5='ddb7189ac212f0567376a4db47dabc48';SHA1='49d4f7e965c2311a16a8ace5de74addc4687785e'
LIMITS={'verification_bytes':SIZE,'compressed_prefix_decode_read_bytes':16000000,'decoded_prefix_bytes':16000000,'seconds':30,'output_bytes':4000000,'selected_complete_offset_groups':16,'boundary_distinct_offset':17}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def inventory():return {str(p.resolve()) for p in [HERE/'freeze_index.py',ROOT/'enwiki-native-index-20260801-v1/worker-result.json',ROOT/'enwiki-native-index-20260801-v1/supervisor-result.json',ROOT/'enwiki-native-index-assessment-v1/result.json',ROOT/'enwiki-native-index-assessment-v1/supervisor.json']}
def verify(pin):
 p=HERE/'index-freeze-input-pins.json'
 if sha(p)!=pin:raise ValueError('external_index_freeze_manifest')
 x=json.loads(p.read_text())
 if set(x['files'])!=inventory() or x['limits']!=LIMITS or x['runtime']!=sys.version:raise ValueError('exact_inventory_limits_runtime')
 for f,h in x['files'].items():
  if pathlib.Path(f).is_symlink() or sha(pathlib.Path(f))!=h:raise ValueError('input_pin')
 assessment=json.loads((ROOT/'enwiki-native-index-assessment-v1/result.json').read_text())
 if not assessment['all_BZ2_EOF_CRC_verified'] or assessment['source_SHA256']!=SHA:raise ValueError('historical_complete_index_CRC_source_pin')
 return x
def parse_line(raw,ordinal):
 if not raw.endswith(b'\n') or len(raw)>65536:raise ValueError('exact_index_line_limit_LF')
 a,b,title=raw[:-1].split(b':',2)
 if not a.isdigit() or not b.isdigit():raise ValueError('index_offset_ID')
 return {'row_ordinal':ordinal,'offset':int(a),'page_ID':int(b),'title':title.decode('utf8'),'raw_line_hex':raw.hex(),'raw_line_SHA256':hashlib.sha256(raw).hexdigest()}
def groups_from_chunks(chunks):
 d=bz2.BZ2Decompressor();pending=b'';groups=[];current=None;rows=[];ordinal=0;decoded=0;compressed=0;boundary=None
 for chunk in chunks:
  compressed+=len(chunk)
  if compressed>LIMITS['compressed_prefix_decode_read_bytes']:raise ValueError('compressed_prefix_cap')
  payload=chunk
  while True:
   b=d.decompress(payload,max_length=min(65536,LIMITS['decoded_prefix_bytes']+1-decoded));payload=b'';decoded+=len(b)
   if decoded>LIMITS['decoded_prefix_bytes']:raise ValueError('decoded_prefix_cap')
   pending+=b
   while b'\n' in pending:
    raw,pending=pending.split(b'\n',1);raw+=b'\n';ordinal+=1;r=parse_line(raw,ordinal)
    if current is None:current=r['offset']
    if r['offset']<current:raise ValueError('decreasing_offset')
    if r['offset']!=current:
     groups.append({'start':current,'end_exclusive':r['offset'],'rows':rows});rows=[];current=r['offset']
     if len(groups)==16:boundary=r;break
    rows.append(r)
    if len(rows)>10000 or len(pending)>65536:raise ValueError('group_or_line_cap')
   if boundary:return {'groups':groups,'boundary_first_row':boundary,'verification_scope':'First16completegroups fixed before XML content; no replacement. WholeindexCRC/EOF only inherited from prior completeassessment, not thisprefixdecode.','compressed_prefix_decode_read_bytes':compressed,'decoded_prefix_bytes':decoded,'raw_lines_consumed':ordinal,'index_prefix_member_EOF_at_stop':d.eof}
   if d.eof:
    if d.unused_data:raise ValueError('unexpected_index_member_before17groups')
    break
   if d.needs_input:break
  if d.eof:break
 raise ValueError('fewer_than17_offset_groups_or_prefix_truncation')
def run(pin):
 start=time.monotonic();old=signal.getsignal(signal.SIGALRM)
 def stop(s,f):raise TimeoutError('index_freeze30seconds')
 signal.signal(signal.SIGALRM,stop);signal.setitimer(signal.ITIMER_REAL,30)
 try:
  verify(pin)
  if OUT.exists() or INDEX.is_symlink() or INDEX.stat().st_size!=SIZE:raise ValueError('once_only_exact_index_source')
  ds=[hashlib.md5(),hashlib.sha1(),hashlib.sha256()];n=0
  with INDEX.open('rb') as f:
   for b in iter(lambda:f.read(1048576),b''):
    n+=len(b)
    if n>SIZE:raise ValueError('verification_byte_cap')
    for h in ds:h.update(b)
  if n!=SIZE or [h.hexdigest() for h in ds]!=[MD5,SHA1,SHA]:raise ValueError('fresh_full_index_triplehash')
  before=INDEX.stat()
  def chunks():
   with INDEX.open('rb') as f:
    left=LIMITS['compressed_prefix_decode_read_bytes']
    while left:
     b=f.read(min(65536,left))
     if not b:break
     left-=len(b);yield b
  result=groups_from_chunks(chunks());end=result['groups'][-1]['end_exclusive']
  if end>16000000:raise ValueError('selected_XML_prefix16MB_cap')
  after=INDEX.stat()
  if (before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns):raise ValueError('index_changed')
  result.update(status='FROZEN_FIRST16_COMPLETE_INDEX_GROUPS_NO_XML_READ',index_path=str(INDEX),index_SHA256=SHA,index_MD5=MD5,index_SHA1=SHA1,verification_bytes=n,XML_prefix_start=0,XML_prefix_end_exclusive=end,header_prefix_bytes=result['groups'][0]['start'],indexed_rows_first16groups=sum(len(g['rows']) for g in result['groups']),elapsed_seconds=time.monotonic()-start,limits=LIMITS,XML_bytes_read=0,network_requests=0,global_ledger_writes=0)
  blob=(json.dumps(result,indent=2,ensure_ascii=False)+'\n').encode()
  if len(blob)>4000000:raise ValueError('output4MB')
  OUT.mkdir()
  with (OUT/'groups.json').open('xb') as f:f.write(blob);f.flush();os.fsync(f.fileno())
  print(json.dumps({k:result[k] for k in ['status','verification_bytes','compressed_prefix_decode_read_bytes','decoded_prefix_bytes','XML_prefix_end_exclusive','header_prefix_bytes','indexed_rows_first16groups','elapsed_seconds']}));return result
 finally:signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,old)
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--manifest-sha256',required=True);a.add_argument('--execute',action='store_true');x=a.parse_args()
 if x.execute:run(x.manifest_sha256)
 else:verify(x.manifest_sha256);print('PREPARED_NO_INDEX_DECODE_NO_XML_ACCESS')
