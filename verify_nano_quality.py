import time
import unittest
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
from cloud_training.nano_quality import assess,run_suite,supervise,atomic_report,output_guard

class QualityTests(unittest.TestCase):
    def result(self,text='54',events=None):
        return {'status':'complete','assistant_text':text,'events':events or []}
    def test_per_turn_budget_and_system_are_preserved_without_budget_leakage(self):
        seen=[]
        class Chat:
            def __init__(self):self.reply_budget=192;self.system=None
            def reset(self):seen.append(('reset',self.system))
            def turn(self,*args,**kwargs):
                seen.append(('turn',self.reply_budget,self.system))
                return {'status':'complete','assistant_text':'reference','events':[]}
        suite={'sessions':[{'id':'a','system':'Original instructions','turns':[{'user':'long','reply_budget':1342},{'user':'short'}]},{'id':'b','turns':[{'user':'new session'}]}]}
        result=run_suite(Chat,suite,deadline=time.monotonic()+10)
        self.assertEqual(seen,[('reset','Original instructions'),('turn',1342,'Original instructions'),('turn',192,'Original instructions'),('turn',192,None)])
        self.assertEqual([r['reply_budget'] for r in result['records']],[1342,192,192])
    def test_invalid_per_turn_budget_rejected_and_real_full_dev_validates(self):
        from cloud_training.nano_quality import validate_suite
        for value in (True,0,-1,2049,'512'):
            suite={'purpose':'development_only_never_train','sessions':[{'id':'a','turns':[{'user':'x','reply_budget':value}]}]}
            with self.assertRaisesRegex(ValueError,'reply budget'):validate_suite(suite)
        validate_suite(json.loads(Path('reports/local-readiness-v1/full-development-suite.json').read_text()))

    def test_correct_text_cannot_hide_missing_call(self):
        self.assertFalse(assess(self.result(),{'exact_answers':['54'],'expected_calls':[{'name':'calculate'}]})['automated_pass'])
    def test_negated_answer_does_not_pass(self):
        self.assertFalse(assess(self.result('not Mysuru'),{'exact_answers':['Mysuru']})['automated_pass'])
    def test_open_ended_answers_require_review(self):
        r=assess(self.result('A plan'),{});self.assertTrue(r['manual_review_required']);self.assertFalse(r['automated_pass'])
    def test_deadline_cannot_report_complete(self):
        r=run_suite(lambda:None,{'sessions':[{'id':'a','turns':[{}]}]},deadline=time.monotonic()-1)
        self.assertEqual(r['status'],'incomplete_deadline')
    def test_call_requires_dispatch_evidence(self):
        call={'name':'calculate','arguments':{'op':'subtract','a':73,'b':19}}
        events=[{'kind':'model_action','parsed':{'kind':'call','proposal':call}}]
        spec={'expected_calls':[call],'exact_answers':['54']}
        self.assertFalse(assess(self.result('54',events),spec)['automated_pass'])
        events.append({'kind':'broker_decision','decision':{'dispatched':True}})
        self.assertTrue(assess(self.result('54',events),spec)['automated_pass'])

    def test_last_turn_overrun_is_incomplete_with_raw_evidence(self):
        class Chat:
            def turn(self,*a,**kw):
                return {'status':'complete','assistant_text':'raw text','events':[]}
        published=[]
        with patch('cloud_training.nano_quality.time.monotonic',side_effect=[0,2]):
            result=run_suite(Chat,{'sessions':[{'id':'a','turns':[{'user':'hello'}]}]},
                             deadline=1,publish=published.append)
        self.assertEqual(result['status'],'incomplete_deadline')
        self.assertEqual(published[0]['records'][0]['user'],'hello')
        self.assertEqual(published[0]['records'][0]['result']['assistant_text'],'raw text')

    def test_watchdog_includes_loading_and_preserves_partial_evidence(self):
        with tempfile.TemporaryDirectory() as t:
            output=Path(t)/'result.json'
            atomic_report(output,{'status':'loading','records':[{'raw':'already saved'}]})
            result=supervise([sys.executable,'-c','import time;time.sleep(30)'],output,.1)
            self.assertEqual(result['status'],'incomplete_timeout')
            self.assertEqual(result['records'],[{'raw':'already saved'}])
            self.assertLess(result['wall_seconds'],3)
            self.assertNotEqual(result['worker_exit_code'],0)

    def test_worker_failure_cannot_be_reported_as_completed(self):
        with tempfile.TemporaryDirectory() as t:
            output=Path(t)/'result.json';atomic_report(output,{'status':'running','records':[]})
            result=supervise([sys.executable,'-c','raise RuntimeError("load failed")'],output,2)
            self.assertEqual(result['status'],'incomplete_worker_error')
            self.assertIn('load failed',Path(str(output)+'.log').read_text())

    def test_checkpoint_output_and_existing_evidence_protected(self):
        with tempfile.TemporaryDirectory() as t:
            checkpoint=Path(t)/'base';checkpoint.mkdir()
            with self.assertRaises(ValueError):output_guard(checkpoint,checkpoint/'quality.json')
            output=Path(t)/'quality.json';output.write_text('{}')
            with self.assertRaises(FileExistsError):output_guard(checkpoint,output)
            self.assertEqual(output_guard(checkpoint,Path(t)/'new.json'),(Path(t)/'new.json').resolve())

    def test_wrong_answer_with_correct_call_fails(self):
        call={'name':'calculate','arguments':{'op':'subtract','a':73,'b':19}}
        events=[{'kind':'model_action','parsed':{'kind':'tool','proposal':call}}]
        self.assertFalse(assess(self.result('55',events),{'expected_calls':[call],'exact_answers':['54']})['automated_pass'])

if __name__=='__main__':unittest.main()
