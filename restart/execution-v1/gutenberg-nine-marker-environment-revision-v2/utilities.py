"""Only exact pinned stdlib utility functions; no XML/network/ML imports."""

import hashlib,json,os,platform,sqlite3,sys,time
from pathlib import Path
import tokenizers
ROOT=Path(__file__).resolve().parent.parent/'m2-intake'

def sha(b):return hashlib.sha256(b).hexdigest()

def file_sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()

def clock():return time.clock_gettime(time.CLOCK_MONOTONIC)

def size(root):
 total=0
 for p in root.rglob('*'):
  try:
   if p.is_file():total+=p.stat().st_size
  except FileNotFoundError:pass # A committed DELETE journal may vanish during supervisor observation.
 return total

class StopInventory(ValueError):
    def __init__(self,reason,diagnostic=None):
        super().__init__(reason);self.diagnostic=diagnostic

def output_size(p):return sum(x.stat().st_size for x in p.rglob('*') if x.is_file())

def terminal_write(path,result,cap,kind='worker'):
    """Fixed-size preallocated terminal slot; never grows at a hard stop."""
    slot=min(384*1024 if kind=='worker' else 128*1024,cap//8)
    if slot<8192:raise StopInventory('terminal_slot_budget_too_small')
    payload=(json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode()
    if len(payload)>slot:
        result={'status':'PARTIAL_INVENTORY_NO_ADMISSION','reason':'terminal_metadata_exceeded_fixed_slot',
                'original_status':result.get('status'),'original_reason':result.get('reason'),
                'new_admitted_documents':0,'new_admitted_tokens':0}
        payload=(json.dumps(result,indent=2)+'\n').encode()
    if not path.exists():
        if output_size(path.parent)+slot>cap:raise StopInventory('cannot_allocate_terminal_slot_within_output_cap')
        with path.open('xb') as f:f.write(b' '*slot)
    if path.stat().st_size!=slot:raise StopInventory('terminal_slot_size_mismatch')
    with path.open('r+b') as f:
        f.write(payload+b' '*(slot-len(payload)));f.flush();os.fsync(f.fileno())
    return result

def tree_rss_from_ps(snapshot,root_pid):
    parents={};rss={}
    for line in snapshot.splitlines():
        parts=line.split()
        if len(parts)!=3:continue
        try:pid,ppid,kib=map(int,parts)
        except ValueError:continue
        parents[pid]=ppid;rss[pid]=kib*1024
    if root_pid not in rss:raise ValueError('supervisor_process_missing_from_RSS_snapshot')
    owned={root_pid}
    while True:
        updated=owned|{pid for pid,ppid in parents.items() if ppid in owned}
        if updated==owned:break
        owned=updated
    return sum(rss.get(pid,0) for pid in owned),sorted(owned)

def environment():
 return {'python':sys.version,'launcher':sys.executable,'resolved_executable':str(Path(sys.executable).resolve()),'sys_prefix':sys.prefix,'sys_base_prefix':sys.base_prefix,'platform':platform.platform(),'sqlite':sqlite3.sqlite_version,'tokenizers':tokenizers.__version__,'tokenizers_wrapper':tokenizers.__file__}
