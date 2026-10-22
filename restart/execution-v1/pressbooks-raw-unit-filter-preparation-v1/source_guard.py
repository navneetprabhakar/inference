"""Read-only first-shard custody; no whole-file hash replay before source run."""
import contextlib,os,stat
from pathlib import Path

def ident(s):return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
def small(path,cap=8000000):
 p=Path(path)
 if p.is_symlink() or not p.is_file() or p.stat().st_size>cap:raise ValueError('bounded_metadata_regular_file')
 raw=p.read_bytes()
 if len(raw)>cap:raise ValueError('metadata_read_cap')
 return raw
@contextlib.contextmanager
def opened(binding,check):
 p=Path(binding['path']);expected=binding['stat']
 def path_check():
  if p.is_symlink() or str(p.resolve())!=str(p) or ident(p.stat())!=expected or not stat.S_ISREG(p.stat().st_mode):raise ValueError('source_path_stat')
 path_check();fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW);total=0
 try:
  if ident(os.fstat(fd))!=expected:raise ValueError('source_FD_stat')
  def custody():
   path_check()
   if ident(os.fstat(fd))!=expected:raise ValueError('source_FD_changed')
  def read(n):
   nonlocal total
   check();custody()
   if type(n) is not int or not 0<n<=65536 or total>binding['bytes']:raise ValueError('bounded_source_read')
   b=os.read(fd,min(n,binding['bytes']-total+1));total+=len(b)
   if total>binding['bytes']:raise ValueError('source_excess_bytes')
   return b
  read.assert_custody=custody
  yield read
  custody()
 finally:os.close(fd)
