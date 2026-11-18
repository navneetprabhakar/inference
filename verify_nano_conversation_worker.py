"""Check real worker command construction without allocating or importing CUDA."""
import ast,json,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from cloud_training.nano_sft import main

class WorkerTests(unittest.TestCase):
 def test_qualification_commands_parse_real_trainer_and_bind_block_mode(self):
  path=Path('reports/ganesh-conversation-execution-v1/gpu_qualify.py');tree=ast.parse(path.read_text());fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='sft')
  root=Path('/tmp/ganesh-conversation-worker-test')
  seen=[];scope={'ROOT':root,'P':root/'reports/ganesh-conversation-execution-v1','OUT':root/'qualification','cfg':{'backup_prefix':'gs://bucket/run','parent_manifest_sha256':'a'*64,'tokenizer_sha256':'b'*64},'sys':SimpleNamespace(executable='python'),'end':'2026-11-18T12:00:00Z','run':lambda cmd,*args:seen.append(cmd),'os':__import__('os')}
  exec(compile(ast.Module(body=[fn],type_ignores=[]),str(path),'exec'),scope)
  for name,steps in [('continuous',2),('split_first',1),('split_resume',1)]:scope['sft'](name,steps,resume=root/'restore' if name=='split_resume' else None)
  from cloud_training.nano_retention import _prefix
  for cmd in seen:
   _prefix(cmd[cmd.index('--backup-prefix')+1])
   argv=['nano_sft',*cmd[3:],'--validate-only']
   with patch('sys.argv',argv),patch('cloud_training.nano_sft.run',return_value=0) as run,patch('cloud_training.nano_sft.ensure_separate_output',return_value=(root,root/'output')),patch('pathlib.Path.mkdir'),patch('pathlib.Path.open'),patch('fcntl.flock'):
    self.assertEqual(main(),0);args=run.call_args.args[0]
    self.assertEqual(args.block_arm,'broad');self.assertTrue(args.deterministic);self.assertFalse(args.deterministic_attention);self.assertEqual(args.eval_every_updates,1);self.assertLessEqual(args.max_updates,2);self.assertFalse(args.fit_diagnostic)

class SnapshotTests(unittest.TestCase):
 def test_combined_suite_preserves_all_source_sessions_and_budget(self):
  import copy,importlib.util
  from cloud_training.nano_fit_probe import validate_inputs
  P=Path('reports/ganesh-conversation-execution-v1')
  combined=json.loads((P/'combined-development-suite.json').read_text());expected=[]
  for path in ['reports/ganesh-conversation-pilot-v1/development-suite.json','cloud_training/evaluation/conversation-tools-dev.json']:
   sessions=copy.deepcopy(json.loads(Path(path).read_text())['sessions'])
   for s in sessions:
    for turn in s['turns']:turn.setdefault('reply_budget',96)
   expected.extend(sessions)
  self.assertEqual(combined['sessions'],expected);self.assertEqual(sum(len(s['turns']) for s in expected),117)
  self.assertEqual(combined['purpose'],'development_only_never_train')

class PrefixPreflightTests(unittest.TestCase):
 def test_invalid_backup_is_rejected_before_runtime_load(self):
  from cloud_training.nano_sft import main
  args=['nano_sft','--validate-only','--backup-prefix','gs://bucket/not-checkpoints']
  for name in ('manifest','base','base-manifest-sha','tokenizer','tokenizer-sha','repo','output','quality-contract'):args.extend(['--'+name,'unused'])
  with patch('sys.argv',args),patch('cloud_training.nano_sft.run') as run,patch('sys.stderr'):
   with self.assertRaises(SystemExit):main()
   run.assert_not_called()

if __name__=='__main__':unittest.main()
