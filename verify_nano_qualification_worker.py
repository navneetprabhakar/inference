"""Validate real qualification launcher arguments without CUDA or cloud calls."""
import ast,sys,unittest,json,tempfile
from pathlib import Path
from cloud_training.nano_retention import _prefix
from cloud_training.nano_qualification_schedule import restart_branches

class Captured(Exception):pass

def arguments(path):
    tree=ast.parse(Path(path).read_text())
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='sft')
    calls=[]
    def capture(argv,*args):calls.append(argv);raise Captured()
    scope={'sys':sys,'restart_branches':restart_branches,'ROOT':Path('/opt/example'),
           'BASE':Path('/base'),'PACKET':Path('/packet'),'OUT':Path('/out'),
           'REMOTE':'gs://own-test-bucket/qualification',
           'config':{'base_manifest_sha256':'0'*64,'tokenizer_sha256':'1'*64,'worker_deadline_utc':'2030-01-01T00:00:00Z'},'run':capture}
    exec(compile(ast.Module(body=[fn],type_ignores=[]),str(path),'exec'),scope)
    for branch in restart_branches():
        try:scope['sft'](branch,resume=Path('/restore') if branch=='split_resume' else None)
        except Captured:pass
    return calls

class WorkerWiring(unittest.TestCase):
    def test_live_templates_match_retention_and_restart_contract(self):
        for path in ['reports/english-first-v1/gpu_qualify.py','reports/english-a100-v1/repair/gpu_qualify.py']:
            with self.subTest(path=path):
                calls=arguments(path)
                prefixes=[_prefix(a[a.index('--backup-prefix')+1]) for a in calls]
                self.assertEqual(prefixes[1],prefixes[2])
                self.assertNotEqual(prefixes[0],prefixes[1])
                for argv in calls:
                    self.assertEqual(argv[argv.index('--eval-every-updates')+1],'1')
                self.assertEqual([a[a.index('--max-updates')+1] for a in calls],['2','1','1'])
                self.assertEqual(['--resume' in a for a in calls],[False,False,True])
    def test_historical_failure_is_reproduced(self):
        for argv in arguments('reports/english-a100-v1/gpu_qualify.py'):
            with self.assertRaisesRegex(ValueError,'ending /checkpoints'):
                _prefix(argv[argv.index('--backup-prefix')+1])
class JournalAuthority(unittest.TestCase):
    def test_stale_local_snapshots_use_one_current_remote_journal(self):
        tree=ast.parse(Path('reports/english-first-v1/gpu_qualify.py').read_text())
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='authoritative_journals')
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);remote='gs://own-test/qualification';prefix=remote+'/split/checkpoints'
            old={'campaign_prefix':prefix,'identity':{'test':1},'lease_phase':'ready','entries':[{'state':'committed','id':'pruned0'}]}
            current={**old,'entries':[{'state':'deleted','id':'pruned0'},{'state':'committed','id':'live1'},{'state':'committed','id':'live2'}]}
            paths=[root/'first.json',root/'resumed.json']
            paths[0].write_text(json.dumps(old));paths[1].write_text(json.dumps(current));calls=[]
            def fetch(uri,target,**kwargs):calls.append(uri);target.write_text(json.dumps(current))
            scope={'json':json,'ROOT':root,'REMOTE':remote,'copy':fetch}
            exec(compile(ast.Module(body=[fn],type_ignores=[]),'real_worker_journal_reader','exec'),scope)
            self.assertEqual(scope['authoritative_journals'](paths),[current])
            self.assertEqual(calls,[prefix+'/retention-journal.json'])
            current['lease_phase']='checkpoint_upload_in_progress'
            with self.assertRaisesRegex(ValueError,'Unfinished authoritative'):scope['authoritative_journals'](paths)
    def test_foreign_namespace_is_rejected_before_fetch(self):
        tree=ast.parse(Path('reports/english-first-v1/gpu_qualify.py').read_text())
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='authoritative_journals')
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'journal.json';path.write_text(json.dumps({'campaign_prefix':'gs://foreign/checkpoints'}))
            scope={'json':json,'ROOT':Path(d),'REMOTE':'gs://own-test/qualification','copy':lambda *a,**k:self.fail('Unexpected fetch')}
            exec(compile(ast.Module(body=[fn],type_ignores=[]),'real_worker_journal_reader','exec'),scope)
            with self.assertRaisesRegex(ValueError,'Unexpected qualification namespace'):scope['authoritative_journals']([path])
if __name__=='__main__':unittest.main()
