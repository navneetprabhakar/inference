"""Local deletion-gate tests; no cloud access and no real project file deletion."""
import contextlib,importlib.util,io,json,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('migration',Path(__file__).with_name('migrate_to_gcs.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class MigrationTests(unittest.TestCase):
 def run_case(self,mode):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);r=root/'reports';r.mkdir();(r/'storage_policy.json').write_text(json.dumps({'migration_authorized':True,'local_eviction_authorized':True}));p=root/'payload.jsonl';p.write_text('required corpus\n');original=m.sha(p)
   def readback(uri,size):
    self.assertTrue(uri.endswith('#123'))
    if mode=='corrupt':return '0'*64
    if mode=='mutated':p.write_text('concurrent mutation\n')
    return uri.split("/objects/")[1].split("/")[0]
   argv=['migration','--apply','--evict'] if mode!='plan' else ['migration']
   with patch.multiple(m,ROOT=root,R=r,ALLOWED=[p]),patch.object(sys,'argv',argv),patch.object(m.subprocess,'run',return_value=subprocess.CompletedProcess([],0)) as upload,patch.object(m.subprocess,'check_output',return_value=json.dumps({'generation':'123'})),patch.object(m,'readback',side_effect=readback),contextlib.redirect_stdout(io.StringIO()):
    if mode in ('corrupt','mutated'):
     with self.assertRaises(ValueError):m.main()
     self.assertTrue(p.exists())
    else:
     m.main();self.assertEqual(p.exists(),mode=='plan')
    if mode=='plan':upload.assert_not_called()
    if mode=='success':
     receipt=json.loads((r/'migration-receipt.json').read_text())[0]
     self.assertTrue(receipt['readback_verified'] and receipt['local_removed']);self.assertEqual(receipt['sha256'],original)
 def test_paused_policy_blocks_cloud(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);(r/'storage_policy.json').write_text(json.dumps({'migration_authorized':False}))
   with patch.object(m,'R',r),patch.object(sys,'argv',['migration','--apply','--evict']),patch.object(m.subprocess,'run') as cloud,contextlib.redirect_stderr(io.StringIO()):
    with self.assertRaises(SystemExit):m.main()
    cloud.assert_not_called()
 def test_corruption_preserves_local(self):self.run_case('corrupt')
 def test_concurrent_mutation_preserves_local(self):self.run_case('mutated')
 def test_verified_copy_eviction(self):self.run_case('success')
 def test_plan_cannot_upload_or_delete(self):self.run_case('plan')
if __name__=='__main__':unittest.main()
