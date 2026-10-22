import hashlib,zlib
class Lines:
 def __init__(self,cap,maximum,callback):self.cap=cap;self.maximum=maximum;self.callback=callback;self.ordinal=0;self.offset=0;self.n=0;self.digest=hashlib.sha256();self.buf=bytearray();self.total=0
 def add(self,data):
  while data:
   if self.ordinal>=self.maximum:raise ValueError('encountered_record_cap_partial_frame')
   end=data.find(b'\n');part=data if end<0 else data[:end+1];data=b'' if end<0 else data[end+1:]
   self.n+=len(part);self.total+=len(part);self.digest.update(part)
   if self.buf is not None:
    if self.n<=self.cap:self.buf.extend(part)
    else:self.buf=None
   if end>=0:self.emit(True)
 def emit(self,ends):
  self.ordinal+=1;raw=bytes(self.buf) if self.buf is not None else None
  self.callback(self.ordinal,self.offset,self.n,ends,self.digest.digest(),raw)
  self.offset+=self.n;self.n=0;self.digest=hashlib.sha256();self.buf=bytearray()
 def finish(self):
  if self.n:self.emit(False)
 def partial(self):return {'consumed_partial_line_offset':self.offset,'consumed_partial_line_bytes':self.n,'consumed_partial_SHA256':self.digest.hexdigest(),'whole_line_hash_claimed':False}

def gzip_stream(read,feed,limits,check):
 pending=b'';d=None;compressed=0;decoded=0;members=0;digest=hashlib.sha256()
 while True:
  check()
  if not pending:
   raw=read(min(65536,limits['compressed_bytes']-compressed+1))
   if raw:
    compressed+=len(raw);digest.update(raw)
    if compressed>limits['compressed_bytes']:raise ValueError('compressed_source_cap')
    pending=raw
   else:
    if d is not None or members==0:raise ValueError('gzip_truncated_missing_CRC_EOF')
    break
  if d is None:
   if len(pending)==1:
    if compressed>=limits['compressed_bytes']:raise ValueError('incomplete_gzip_header_at_compressed_cap')
    extra=read(1);compressed+=len(extra);digest.update(extra);pending+=extra
   if not pending.startswith(b'\x1f\x8b'):raise ValueError('gzip_trailing_or_unknown_member')
   d=zlib.decompressobj(16+zlib.MAX_WBITS)
  if decoded>=limits['decoded_bytes']:raise ValueError('decoded_cap_partial_frame')
  raw=d.decompress(pending,max_length=min(65536,limits['decoded_bytes']-decoded));decoded+=len(raw)
  pending=d.unused_data if d.eof else d.unconsumed_tail
  if raw:feed(raw)
  if d.eof:members+=1;d=None
 return {'compressed_bytes':compressed,'compressed_SHA256':digest.hexdigest(),'decoded_bytes':decoded,'gzip_CRC_EOF_members':members,'trailing_absent':True}

