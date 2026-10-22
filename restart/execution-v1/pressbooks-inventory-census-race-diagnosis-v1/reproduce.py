"""Actual frozen size() race on isolated tempfiles only; no source body access."""
import json,os,sys,tempfile
from pathlib import Path
from unittest.mock import patch
B=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(B/'pressbooks-first-shard-inventory-preparation-v1'));import pilot
out=[]
for kind in ['journal_unlink','large_partial_rename']:
 with tempfile.TemporaryDirectory() as z:
  root=Path(z).resolve();p=root/('frame.sqlite-journal' if kind=='journal_unlink' else 'source.partial');p.write_bytes(b'x'*65536);final=root/'source.gz';real=Path.is_file;fired=[]
  def race(self):
   yes=real(self)
   if self==p and yes and not fired:
    fired.append(True)
    if kind=='journal_unlink':p.unlink()
    else:p.rename(final)
   return yes
  error=None
  try:
   with patch.object(Path,'is_file',race):pilot.size(root)
  except FileNotFoundError as e:error={'type':type(e).__name__,'errno':e.errno,'name':Path(e.filename).name}
  assert fired and error and error['errno']==2
  out.append({'scenario':kind,'actual_frozen_function':'pilot.size','result':'REPRODUCED_ENOENT_AFTER_IS_FILE_TRUE_BEFORE_SECOND_STAT','error':error,'remaining_actual_size':sum(q.stat().st_size for q in root.iterdir()),'large_partial_was_not_safely_skippable':kind=='large_partial_rename'})
print(json.dumps({'status':'REPRODUCED_BOTH_RACES','cases':out,'retained_source_bytes_read':0,'production_modified':False},indent=2))
