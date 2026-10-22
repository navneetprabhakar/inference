"""Terminal-context-only immutable metadata/selected native-range readers.
No file access occurs on import. No implicit fullDB/prefix rehash or writes.
"""
import contextlib,os,stat,sqlite3,hashlib
from pathlib import Path

def need(v,m):
 if not v:raise ValueError(m)
def identity(s):return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
def context(ctx):need(ctx.get('status')=='VERIFIED_TERMINAL_CONTEXT_NO_SOURCE_BODY_OPENED','actual_verified_terminal_context_required')
def pathcheck(entry):
 p=Path(entry['path']);need(not p.is_symlink() and str(p.resolve())==str(p) and stat.S_ISREG(p.stat(follow_symlinks=False).st_mode) and identity(p.stat(follow_symlinks=False))==entry['stat'],'verified_file_stat_custody');return p
@contextlib.contextmanager
def metadata_db(ctx,key,check):
 context(ctx);need(key in ['frame','index'],'metadata_db_role');entry=ctx['binding'][key];p=pathcheck(entry);fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW);db=None
 try:
  need(identity(os.fstat(fd))==entry['stat'],'metadata_FD_custody');db=sqlite3.connect(p.as_uri()+'?mode=ro&immutable=1',uri=True);db.row_factory=sqlite3.Row
  for q in ['query_only=ON','temp_store=MEMORY','cache_size=-16384','mmap_size=0']:db.execute('PRAGMA '+q)
  db.set_progress_handler(lambda:(check() or 0),10000);yield db;check();need(identity(os.fstat(fd))==entry['stat'],'metadata_FD_after');pathcheck(entry)
 finally:
  if db is not None:db.close()
  os.close(fd)
@contextlib.contextmanager
def native_readers(ctx,capture_plan,check):
 context(ctx);b=ctx['binding'];entry=b['prefix'];p=pathcheck(entry);fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW);seen=set();header_seen=False;allowed={(g['group_ordinal'],g['compressed_start'],g['compressed_end_exclusive']) for g in capture_plan['groups_read_order']}
 def custody():
  check();need(identity(os.fstat(fd))==entry['stat'],'native_FD_custody');pathcheck(entry)
 try:
  custody()
  def read_group(g):
   custody();k=(g['group_ordinal'],g['compressed_start'],g['compressed_end_exclusive']);need(k in allowed and k not in seen,'selected_group_read_once');n=k[2]-k[1];need(0<n<=4078038 and 0<=k[1]<k[2]<=min(17988779480,entry['stat'][2]),'native_range_prefix_bound');seen.add(k);raw=os.pread(fd,n,k[1]);custody();need(len(raw)==n,'short_native_group_read');return raw
  def header():
   nonlocal header_seen
   need(not header_seen,'header_once');header_seen=True;h=b['header'];hp=pathcheck(h);hf=os.open(hp,os.O_RDONLY|os.O_NOFOLLOW)
   try:
    need(identity(os.fstat(hf))==h['stat'],'header_FD');raw=os.read(hf,65537);need(len(raw)==h['stat'][2]<=65536 and hashlib.sha256(raw).hexdigest()==h['SHA256'] and identity(os.fstat(hf))==h['stat'],'exact_original_header')
   finally:os.close(hf)
   pathcheck(h);return raw
  yield read_group,header,custody
  custody();need(seen==allowed and header_seen,'all_selected_groups_header_once')
 finally:os.close(fd)
