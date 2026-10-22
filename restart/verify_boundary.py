"""Negative tests only: no weights or trainer may be constructed."""
import json
from pathlib import Path
from slm.common.config import initialize
from slm.common.checkpoint import load
from slm.common.training import Trainer
from slm.train import run
checks={
 'initialize': lambda:initialize(None),
 'checkpoint_load':lambda:load('/nonexistent-old-checkpoint'),
 'trainer_construct':lambda:Trainer(None,None,None),
 'trainer_resume':lambda:Trainer.resume('/nonexistent-old-checkpoint',None),
 'train_run':lambda:run(None,'/nonexistent-output')}
results={}
for name,call in checks.items():
 try:call()
 except RuntimeError as e:
  assert 'DESIGN ONLY' in str(e);results[name]='blocked before model/data access'
 else:raise AssertionError(name)
Path('restart/boundary-verification.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2))
