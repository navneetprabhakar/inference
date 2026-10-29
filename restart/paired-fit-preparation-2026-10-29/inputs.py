"""Verified input adapter for core.Runner; this module cannot start training."""
import json,hashlib,sys
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parent;ROOT=P.parents[1];sys.path.insert(0,str(P.parent/'runner-readiness-2026-10-29'))
from runner import collate

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
class FitInputs:
 def __init__(self):
  manifest=read(P/'freeze.json')
  for name,h in manifest['files'].items():
   if sha(ROOT/name)!=h:raise RuntimeError('PROPOSAL_INPUT_CHANGED:'+name)
  self.rows=read(P/'private/fit-records.json');self.schedule=read(P/'private/schedules.json');self.replay_indices=read(P/'private/replay-indices.json');meta=read(P.parent/'runner-readiness-2026-10-29/replay.json')
  if sha(ROOT/meta['path'])!=meta['sha256']:raise RuntimeError('REPLAY_CHANGED')
  self.replay=np.load(ROOT/meta['path'],mmap_mode='r')
 def batch(self,wording,index,coefficient):
  if wording not in ['paired','shuffled'] or coefficient!=.5 or not 0<=index<256:raise ValueError('INVALID_FIT_ARM_OR_CURSOR')
  rows=[self.rows[i] for i in self.schedule[wording][index]]
  if len(rows)!=8 or len({r['scenario']['family'] for r in rows})!=8:raise RuntimeError('TASK_BALANCE')
  return collate(rows),np.asarray(self.replay[self.replay_indices[index]],np.int32)
