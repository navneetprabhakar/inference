import time
import unittest
from cloud_training.nano_quality import assess,run_suite

class QualityTests(unittest.TestCase):
    def result(self,text='54',events=None):
        return {'status':'complete','assistant_text':text,'events':events or []}
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

    def test_wrong_answer_with_correct_call_fails(self):
        call={'name':'calculate','arguments':{'op':'subtract','a':73,'b':19}}
        events=[{'kind':'model_action','parsed':{'kind':'tool','proposal':call}}]
        self.assertFalse(assess(self.result('55',events),{'expected_calls':[call],'exact_answers':['54']})['automated_pass'])

if __name__=='__main__':unittest.main()
