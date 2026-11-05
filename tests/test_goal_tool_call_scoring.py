import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from score_goal_tool_calls import score

class ExactCallTests(unittest.TestCase):
    def run_case(self,expected,events,output):
        cases=[{'id':'a','turns':[{'user':'Question','expected_calls':expected}]}]
        rows=[{'id':'a','turns':[{'user':'Question','student_reply':{'output':output},'tool_events':events}]}]
        return score(cases,rows)['cases'][0]['exact_match']
    def test_exact_call(self):
        call={'name':'calculate','arguments':{'op':'add','a':2,'b':3}}
        self.assertTrue(self.run_case([call],[{'call':call,'accepted_fixture':True}],'<|tool_call|>'))
    def test_wrong_arguments(self):
        self.assertFalse(self.run_case([{'name':'x','arguments':{'n':2}}],[{'call':{'name':'x','arguments':{'n':3}},'accepted_fixture':True}],'<|tool_call|>'))
    def test_malformed_call_not_abstention(self):
        self.assertFalse(self.run_case([],[{'accepted_fixture':False}],'<|tool_call|>broken'))
    def test_no_call_is_abstention_only_not_semantic_pass(self):
        self.assertTrue(self.run_case([],[],'Possibly incorrect answer'))

if __name__=='__main__':unittest.main()
