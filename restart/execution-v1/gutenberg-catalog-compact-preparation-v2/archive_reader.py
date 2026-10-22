"""Exact reused strict reader functions; no downloader or ledger imports."""
import bz2,hashlib,sys,tarfile
from pathlib import Path,PurePosixPath
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'wikibooks-identity-frame-preparation-v1'))
from inventory import Decoded
MAX_MEMBERS=150000;MEMBER_CAP=1000000
def sha(b):return hashlib.sha256(b).hexdigest()
class StrictBZ2:
 """Bounded decompression, complete CRC for every stream, no trailing junk."""
 def __init__(self,handle):
  self.handle=handle;self.decoder=None;self.pending=b'';self.complete=False;self.streams=0
 def read(self,n):
  out=[];used=0
  while used<n and not self.complete:
   if self.decoder is None:
    chunk=self.pending;self.pending=b''
    if len(chunk)<4:chunk+=self.handle.read(4-len(chunk))
    if not chunk:
     if self.streams==0:raise ValueError('Empty compressed archive')
     self.complete=True;break
    if len(chunk)<4 or chunk[:3]!=b'BZh' or chunk[3:4] not in b'123456789':raise ValueError('Invalid or trailing nonbzip2 compressed bytes')
    self.decoder=bz2.BZ2Decompressor();self.pending=chunk
   if self.decoder.needs_input:
    chunk=self.pending;self.pending=b''
    if not chunk:chunk=self.handle.read(65536)
    if not chunk:raise ValueError('Truncated bzip2 stream')
   else:chunk=b''
   part=self.decoder.decompress(chunk,max_length=n-used);out.append(part);used+=len(part)
   if self.decoder.eof:
    self.pending=self.decoder.unused_data;self.streams+=1;self.decoder=None
  return b''.join(out)

def tar_members(archive,guard,stats):
 """Reuse pinned bounded decoded exact reads; never write an expanded tar."""
 with archive.open('rb') as f:
  strict=StrictBZ2(f);decoded=Decoded(strict,guard)
  try:
   while True:
    header=decoded.exact(512)
    if header==b'\0'*512:
     if decoded.exact(512)!=b'\0'*512:raise ValueError('Missing second tar EOF block')
     while True:
      b=decoded.read(65536)
      if not b:break
      if any(b):raise ValueError('Nonzero data after tar EOF')
     if not strict.complete:raise ValueError('Compressed full EOF not established')
     stats['bzip2_streams']=strict.streams;stats['full_tar_EOF_verified']=stats['full_bzip2_CRC_EOF_verified']=True;return
    member=tarfile.TarInfo.frombuf(header,'utf-8','strict');stats['members']+=1
    if stats['members']>MAX_MEMBERS:raise ValueError('150k tar member cap')
    name=PurePosixPath(member.name)
    if name.is_absolute() or '..' in name.parts or len(member.name.encode())>4096:raise ValueError('Unsafe/unbounded tar member path')
    if not member.isfile() and not member.isdir():raise ValueError('Unsupported tar membertype; no alias/longname interpretation')
    if member.isdir() and member.size:raise ValueError('Nonempty directorymember')
    h=hashlib.sha256();remaining=member.size;parts=[];parsed=member.isfile() and member.name.endswith('.rdf') and member.size<=MEMBER_CAP
    while remaining:
     b=decoded.exact(min(65536,remaining));h.update(b);remaining-=len(b)
     if parsed:parts.append(b)
    padding=(-member.size)%512
    if padding and decoded.exact(padding)!=b'\0'*padding:raise ValueError('Nonzero tar padding')
    stats['member_body_bytes']+=member.size
    yield {'ordinal':stats['members'],'name':member.name,'size':member.size,'body_SHA256':h.hexdigest(),'header_SHA256':sha(header),'kind':'directory' if member.isdir() else 'file','raw':b''.join(parts) if parsed else None,'hold':'oversize_RDF_member_not_parsed' if member.isfile() and member.name.endswith('.rdf') and not parsed else None}
  finally:stats['actual_decoded_tar_bytes']=decoded.n
