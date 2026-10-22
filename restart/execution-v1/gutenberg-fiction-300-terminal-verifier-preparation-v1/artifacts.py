"""Bounded full local inventory/UTF8 diagnostics, never publisher/quality clearance."""
import codecs,hashlib,os,re,stat
from pathlib import Path

def require(v,m):
 if not v:raise ValueError(m)
def identity(s):return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
def readsmall(p,cap):
 p=Path(p);require(not p.is_symlink() and stat.S_ISREG(p.stat().st_mode) and p.stat().st_size<=cap,'bounded_regular_metadata')
 with p.open('rb') as f:b=f.read(cap+1)
 require(len(b)<=cap,'metadata_cap');return b

def verify(root,inventory,successes,check):
 root=Path(root);declared={r['path']:r for r in inventory['artifacts']};require(len(declared)==len(inventory['artifacts']),'duplicate_inventory_path')
 terminal={'result.json','inventory.json','controller.json'};actual=set();total=0;verifiedbytes=0;diagnostics=[]
 for parent,dirs,files in os.walk(root,followlinks=False):
  for name in dirs:require(not (Path(parent)/name).is_symlink(),'source_directory_symlink')
  for name in files:
   check();p=Path(parent)/name;s=p.stat(follow_symlinks=False);require(stat.S_ISREG(s.st_mode),'source_special_or_symlink');rel=str(p.relative_to(root));actual.add(rel);total+=s.st_size;require(total<=800000000,'source_output_cap')
   if rel in terminal:continue
   require(rel in declared and declared[rel]['bytes']==s.st_size,'all_artifacts_exact_sizes')
   require(not Path(rel).is_absolute() and '..' not in Path(rel).parts,'inventory_relative_path')
   fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW);decoder=codecs.getincrementaldecoder('utf8')('strict') if rel in successes else None;valid=True;head=bytearray();h=hashlib.sha256();n=0
   try:
    require(identity(os.fstat(fd))==identity(s),'artifact_FD_identity')
    while True:
     check();b=os.read(fd,min(1048576,s.st_size-n+1))
     if not b:break
     n+=len(b);require(n<=s.st_size,'artifact_grew');h.update(b)
     if rel in successes:
      if len(head)<16384:head.extend(b[:16384-len(head)])
      if decoder is not None:
       try:decoder.decode(b,final=False)
       except UnicodeError:valid=False;decoder=None
    if decoder is not None:
     try:decoder.decode(b'',final=True)
     except UnicodeError:valid=False
    require(n==s.st_size and identity(os.fstat(fd))==identity(s) and identity(p.stat(follow_symlinks=False))==identity(s),'artifact_changed')
   finally:os.close(fd)
   require(h.hexdigest()==declared[rel]['SHA256'],'artifact_SHA256');verifiedbytes+=n
   if rel in successes:
    r=successes[rel];require(n==r['bytes'] and h.hexdigest()==r['SHA256'] and 0<n<=2400000,'completed_raw_native_hash_size')
    try:prefix=codecs.getincrementaldecoder('utf8')('strict').decode(bytes(head),final=False);ids=sorted({int(x) for x in re.findall(r'(?i)\b(?:e-?book)\s*#\s*([0-9]+)',prefix)})
    except UnicodeError:ids=None
    diagnostics.append({'path':rel,'planned_ebook_ID':r['ebook_ID'],'plaintext_bytes':n,'local_plaintext_SHA256':h.hexdigest(),'strict_UTF8_whole_file':valid,'publisher_IDs_first16384bytes':ids,'expected_ID_observed_in_header_prefix':r['ebook_ID'] in ids if ids is not None else None,'publisher_checksum_or_current_catalog_version_verified':False,'rights_originalEnglish_quality_clearance':False})
 require(actual==set(declared)|terminal,'exact_artifact_file_inventory_no_extras')
 require(total==inventory['all_output_bytes_including_reserved_slots'],'complete_output_byte_reconciliation')
 require({r['path'] for r in diagnostics}==set(successes),'every_completed_raw_file_diagnostic')
 return {'all_artifacts_verified':len(declared),'hashed_nonterminal_bytes':verifiedbytes,'total_output_bytes':total,'raw_complete_file_diagnostics':diagnostics}
