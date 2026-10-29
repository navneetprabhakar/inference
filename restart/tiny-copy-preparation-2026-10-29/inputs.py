"""CPU-only proposed input adapter. No training entry point."""
import sys,json,hashlib
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parent;ROOT=P.parents[1];sys.path.insert(0,str(P.parent/'runner-readiness-2026-10-29'))
from runner import collate

def read(p):return json.loads(p.read_text())
class TinyInputs:
 def __init__(self):
  for p,h in read(P/'freeze.json')['files'].items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h,p
  self.rows=read(P/'private/fit.json');self.schedule=read(P/'private/schedules.json');self.indices=read(P/'private/replay-indices.json');meta=read(P.parent/'runner-readiness-2026-10-29/replay.json');path=ROOT/meta['path'];assert hashlib.sha256(path.read_bytes()).hexdigest()==meta['sha256'];self.replay=np.load(path,mmap_mode='r')
 def batch(self,family,index,coefficient):
  if family not in self.schedule or not 0<=index<128 or coefficient!=.5:raise ValueError('INVALID_TINY_ARM')
  rows=[self.rows[i] for i in self.schedule[family][index]];assert len(rows)==4 and {r['family'] for r in rows}=={family}
  return collate(rows),np.asarray(self.replay[self.indices[index]],np.int32)
