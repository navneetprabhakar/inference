"""Real subprocess/lock/state integration tests; no cloud or training."""
import datetime as dt
import json
import sys
import unittest
from pathlib import Path
from verify_nano_recovery_gate import RecoveryGate
from cloud_training.nano_recovery_controller import Controller,canonical,validate_graph
from cloud_training.nano_recovery_gate import digest

class IntegratedController(RecoveryGate):
    # Inherited cases additionally exercise the common policy gate.
    def configure(self,code="import json;open('result.json','w').write(json.dumps({'status':'done'}))"):
        self.now=dt.datetime.now(dt.timezone.utc)
        self.r.update(python=sys.executable,lease_start_utc=(self.now-dt.timedelta(seconds=30)).isoformat(),provider_stop_utc=(self.now+dt.timedelta(hours=1)).isoformat())
        (self.root/'worker.py').write_text(code)
        self.r['files']['worker.py']=digest(self.root/'worker.py')
        self.r['tasks']=[{'id':'probe','stage':'qualification','kind':'command','source':'worker.py','argv':[sys.executable,'worker.py'],
                         'timeout_seconds':2,'outputs':['result.json'],'result':'result.json','expected_status':'done','needs':[]}]
        self.bind();self.r['authorization']['expires_utc']=(self.now+dt.timedelta(hours=2)).isoformat()
        self.request=self.root/'request.json';self.request.write_text(json.dumps(self.r))
        return Controller(self.root,self.request,self.root/'controller')
    def test_subprocess_and_restart_idempotency(self):
        c=self.configure();self.assertEqual(c.next()['status'],'task_completed')
        self.assertEqual(Controller(self.root,self.request,self.root/'controller').next()['status'],'complete_not_release_accepted')
        self.assertEqual(len(json.loads((self.root/'controller/state.json').read_text())['completed']),1)
    def test_actual_no_approval_no_subprocess(self):
        c=self.configure();c.request['authorization']=None
        self.assertEqual(c.next()['status'],'hold_gate');self.assertFalse((self.root/'result.json').exists())
    def test_output_mutation_blocks_restart(self):
        c=self.configure();c.next();(self.root/'result.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'output changed'):c.next()
    def test_zero_exit_wrong_status_is_failure(self):
        c=self.configure("open('result.json','w').write('{\"status\":\"failure\"}')")
        with self.assertRaises(ValueError):c.next()
        self.assertEqual(c.next()['status'],'hold_failed_task')
    def test_timeout_kills_and_no_retry(self):
        c=self.configure('import time;time.sleep(30)')
        with self.assertRaises(Exception):c.next()
        self.assertEqual(c.next()['status'],'hold_failed_task')
    def test_crash_intent_never_replayed(self):
        c=self.configure();state=c._state();state['running']={'id':'probe'};c._save(state,{'event':'test_crash'})
        with self.assertRaisesRegex(ValueError,'reconciliation'):c.next()
        self.assertFalse((self.root/'result.json').exists())
    def test_competing_writer(self):
        import fcntl
        c=self.configure()
        with (c.directory/'writer.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):c.next()
    def test_changed_bound_script_prevents_spawn(self):
        c=self.configure();(self.root/'worker.py').write_text("raise RuntimeError('must not run')")
        self.assertEqual(c.next()['status'],'hold_gate')
    def test_graph_unsafe_log_path(self):
        self.configure();self.r['tasks'][0]['id']='../escape'
        with self.assertRaises(ValueError):validate_graph(self.r,self.root)
    def test_graph_result_not_declared(self):
        self.configure();self.r['tasks'][0]['outputs']=[]
        with self.assertRaises(ValueError):validate_graph(self.r,self.root)
    def test_changed_graph_on_restart(self):
        c=self.configure();c.next();self.r['tasks'][0]['timeout_seconds']=10;self.bind();self.request.write_text(json.dumps(self.r))
        c=Controller(self.root,self.request,self.root/'controller')
        with self.assertRaisesRegex(ValueError,'spec changed'):c.next()
    def test_protected_output(self):
        self.configure();self.r['protected_roots']=['protected'];self.r['tasks'][0]['outputs']=['protected/payload.pt'];self.r['tasks'][0].pop('result')
        with self.assertRaises(ValueError):validate_graph(self.r,self.root)
if __name__=='__main__':unittest.main()

class BatchReview(RecoveryGate):
    def test_batch_requires_all_candidates_and_bound_review(self):
        import copy
        from cloud_training.nano_quality import atomic_report
        from cloud_training.nano_recovery_controller import Controller
        with self.subTest('review'):
            root=self.root.resolve()
            suite={'purpose':'training_fit_exposed_never_release','sessions':[{'id':str(i),'turns':[{}, {}, {}]} for i in range(24)]}
            dev={'purpose':'development_only_never_train','sessions':[{'id':'d','turns':[{}]}]}
            atomic_report(root/'fit.json',suite);atomic_report(root/'dev.json',dev)
            atomic_report(root/'training.json',{'step':2,'best_development_step':1})
            candidates=[];reviews=[]
            for scope in ('exposed_fit','development'):
                for step in (0,1,2):
                    source=suite if scope=='exposed_fit' else dev;sp=root/('fit.json' if scope=='exposed_fit' else 'dev.json')
                    records=[{'session':s['id'],'turn':i,'result':{'status':'complete','events':[],'broker_trace':[]}} for s in source['sessions'] for i in range(len(s['turns']))]
                    path=root/f'{scope}-{step}.json'
                    raw={'status':'fit_checks_complete_requires_review' if scope=='exposed_fit' else 'development_checks_complete','suite_sha256':digest(sp),'checkpoint_manifest_sha256':str(step)*64,'records':records}
                    atomic_report(path,raw);candidates.append({'scope':scope,'step':step,'path':path.name,'sha256':digest(path)})
                    reviews.append({'raw_sha256':digest(path),'checkpoint_manifest_sha256':raw['checkpoint_manifest_sha256'],'records':[{'session':r['session'],'turn':r['turn'],'pass':True,'reason':'synthetic integration fixture'} for r in records]})
            atomic_report(root/'index.json',{'status':'complete_requires_review','candidates':candidates})
            review={'index_sha256':digest(root/'index.json'),'reviewer':'fixture','reviewed_utc':self.now.isoformat(),'candidates':reviews}
            atomic_report(root/'review.json',review)
            c=object.__new__(Controller);c.root=root;c.directory=root;c.statepath=root/'state.json';c.spec_hash='a'*64
            task={'id':'review','raw':'index.json','review':'review.json','suite':'fit.json','development_suite':'dev.json','producer_result':'training.json'}
            state={'completed':{},'events':[],'failed':None,'evidence':{}}
            bad=copy.deepcopy(review);bad['candidates'].pop();atomic_report(root/'review.json',bad)
            with self.assertRaisesRegex(ValueError,'All checkpoint'):c._batch_review(task,state)
            atomic_report(root/'review.json',review)
            result=c._batch_review(task,state)
            self.assertEqual(result['status'],'review_passed_not_release')
            self.assertIn('fit_semantic_review',state['evidence'])

class PostStopReview(RecoveryGate):
    def test_review_can_finish_without_live_cloud_lease(self):
        from cloud_training.nano_quality import atomic_report
        root=self.root.resolve()
        suite={'purpose':'training_fit_exposed_never_release','sessions':[{'id':str(i),'turns':[{}, {}, {}]} for i in range(24)]}
        records=[{'session':s['id'],'turn':i,'result':{'status':'complete','events':[],'broker_trace':[]}} for s in suite['sessions'] for i in range(3)]
        raw={'status':'fit_checks_complete_requires_review','records':records,'suite_sha256':'','checkpoint_manifest_sha256':'b'*64}
        atomic_report(root/'suite.json',suite);raw['suite_sha256']=digest(root/'suite.json');atomic_report(root/'raw.json',raw)
        review={'raw_sha256':digest(root/'raw.json'),'suite_sha256':raw['suite_sha256'],'checkpoint_manifest_sha256':'b'*64,'reviewer':'fixture','reviewed_utc':'2030-01-01T00:00:00Z','records':[{'session':r['session'],'turn':r['turn'],'pass':True,'reason':'fixture'} for r in records]}
        atomic_report(root/'review.json',review);(root/'source.py').write_text('raise RuntimeError("never execute")')
        self.r['python']=sys.executable;self.r['files'].update({'source.py':digest(root/'source.py'),'suite.json':digest(root/'suite.json')})
        self.r['tasks']=[{'id':'probe','stage':'fit','kind':'command','source':'source.py','argv':[sys.executable,'source.py'],'timeout_seconds':1,'outputs':['raw.json']},
                         {'id':'review','stage':'fit','kind':'fit_review','needs':['probe'],'raw':'raw.json','review':'review.json','suite':'suite.json'}]
        self.bind();self.r['authorization']=None
        path=root/'request.json';atomic_report(path,self.r);c=Controller(root,path,root/'controller')
        state=c._state();state['completed']['probe']={'kind':'command','outputs':{'raw.json':digest(root/'raw.json')}};c._save(state,{'event':'synthetic_completed_probe'})
        self.assertEqual(c.next()['status'],'review_passed_not_release')
