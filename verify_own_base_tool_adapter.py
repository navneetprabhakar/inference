"""Tiny CPU-only fixtures for replay binding and current-turn target masking."""
from copy import deepcopy
import json
import unittest
from dialogue import IGNORE, _frames
from own_base_chat import stable_tool_record
from own_base_tool_adapter import adapt_lesson, legacy_projection
from tokenizer import load
from tools import FixtureSession


def calc(op='add',a=2,b=3):return dict(name='calculate',arguments=dict(op=op,a=a,b=b))
def conv():return dict(name='convert',arguments={'value':2,'from':'m','to':'cm'})


def lesson(turns):
    """Create only explicitly supplied tiny cases, never bulk generators."""
    out=dict(family='synthetic-cpu-fixture',history=[],observations=[],policy=[]);session=FixtureSession()
    for user,policy,calls,answer in turns:
        p=dict(permit_calls=True,fixture_for=None,fixture=None);p.update(policy)
        session.start_turn(**p);out['policy'].append(p);out['history'].append(dict(role='user',text=user))
        for call in calls:
            obs=session.propose(json.dumps(call),assistant_call_boundary=True)
            out['history'].extend([dict(role='assistant',call=call),dict(role='tool',result=legacy_projection(obs))]);out['observations'].append(stable_tool_record(obs))
        out['history'].append(dict(role='assistant',text=answer))
    return out


class Checks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.tok=load()
    def apply(self,x):return adapt_lesson(x,self.tok)
    def test_actual_calculate_convert_and_verbatim(self):
        for call,answer in [(calc(),' 5 '),(conv(),'200 cm')]:
            original=lesson([('Please calculate.',{},[call],answer)]);saved=deepcopy(original);r=self.apply(original)
            self.assertEqual(original,saved);self.assertEqual(r['turns'][0]['history'][-1]['text'],answer)
            self.assertEqual(r['audit']['observation_sources'],['offline fixture']);self.assertFalse(r['admitted'])
            self.assertIn('timestamp',r['audit']['replay_records'][0])
            self.assertNotIn('timestamp',r['turns'][0]['history'][3]['record'])
    def test_within_turn_chain(self):
        r=self.apply(lesson([('Add then double.',{},[calc(),calc('multiply',5,2)],'10')]))
        self.assertEqual([m['call_id'] for m in r['turns'][0]['history'] if m['role']=='assistant' and 'call' in m],['c1','c2'])
    def test_permissions_change_and_masking(self):
        r=self.apply(lesson([('Add.',{},[calc()],'5'),('Recall without calling.',{'permit_calls':False},[],'5')]))
        last=r['turns'][-1];self.assertIn('"permit_calls":false',last['history'][0]['text'])
        user=max(i for i,m in enumerate(last['history']) if m['role']=='user');prefix,_,_=_frames(self.tok,last['history'][:user])
        self.assertTrue(all(x==IGNORE for x in last['row'].labels[:len(prefix)-1]));self.assertGreater(last['row'].target_count,0)
    def test_error_then_retry(self):
        call=calc('multiply',2,3)
        r=self.apply(lesson([('Try.',{'fixture_for':call,'fixture':{'error':'temporary failure'}},[call],'The fixture failed.'),('Retry.',{},[call],'6')]))
        self.assertEqual(r['audit']['observation_sources'],['synthetic recorded fixture','offline fixture'])
        self.assertFalse(r['audit']['replay_records'][0]['ok']);self.assertTrue(r['audit']['replay_records'][1]['ok'])
    def test_counterfactual_chain_and_scoped_policy(self):
        first=calc();r=self.apply(lesson([('Read and double.',{'fixture_for':first,'fixture':{'result':99},'allowed_names':['calculate']},[first,calc('multiply',99,2)],'198')]))
        self.assertEqual(r['audit']['observation_sources'],['synthetic recorded fixture','offline fixture'])
        self.assertEqual(r['audit']['replay_records'][1]['arguments']['a'],99)
        self.assertEqual(r['audit']['replay_records'][1]['data']['result'],198)
        self.assertIn('"allowed_tools":["calculate"]',r['turns'][0]['history'][0]['text'])
    def test_actual_division_error(self):
        r=self.apply(lesson([('Divide.',{},[calc('divide',1,0)],'Division failed.')]))
        self.assertFalse(r['audit']['replay_records'][0]['ok']);self.assertEqual(r['audit']['observation_sources'],['offline fixture'])
    def test_synthetic_label_and_no_answer_repair(self):
        call=calc();r=self.apply(lesson([('Read fixture.',{'fixture_for':call,'fixture':{'result':99}},[call],'99')]))
        self.assertEqual(r['audit']['observation_sources'],['synthetic recorded fixture']);self.assertEqual(r['audit']['replay_records'][0]['data']['result'],99)
        wrong=lesson([('Add.',{},[calc()],'This answer is intentionally unverified.')]);self.assertEqual(self.apply(wrong)['turns'][0]['history'][-1]['text'],wrong['history'][-1]['text'])
    def test_mismatches(self):
        base=lesson([('Add.',{},[calc()],'5')])
        variants=[]
        x=deepcopy(base);x['observations'][0]['data']['result']=9;variants.append(x)
        x=deepcopy(base);x['history'][2]['result']['result']=9;variants.append(x)
        x=deepcopy(base);x['history'][1]['call']['arguments']['a']=9;variants.append(x)
        x=deepcopy(base);x['observations'][0]['call_id']='c9';variants.append(x)
        x=deepcopy(base);x['observations'][0]['source']='synthetic recorded fixture';variants.append(x)
        x=deepcopy(base);x['observations'].append(x['observations'][0]);variants.append(x)
        x=deepcopy(base);x['policy']=[];variants.append(x)
        x=deepcopy(base);x['history'].pop();variants.append(x)
        for x in variants:
            with self.subTest(x=x):
                with self.assertRaises(ValueError):self.apply(x)
    def test_policy_prohibited_teacher_call(self):
        with self.assertRaises(ValueError):self.apply(lesson([('No calls.',{'permit_calls':False},[calc()],'Blocked.')]))
    def test_context_overflow_and_reply_cap(self):
        for user,answer in [('long '*1500,'Short.'),('Short.','word '*400)]:
            with self.assertRaises(ValueError):self.apply(lesson([(user,{},[],answer)]))
    def test_model_history_deterministic_audit_is_separate(self):
        original=lesson([('Add.',{},[calc()],'5')]);a=self.apply(original);b=self.apply(original)
        self.assertEqual(a['source_lesson_sha256'],b['source_lesson_sha256']);self.assertEqual(a['turns'][0]['history'],b['turns'][0]['history']);self.assertEqual(a['turns'][0]['row'],b['turns'][0]['row'])

if __name__=='__main__':unittest.main(verbosity=2)
