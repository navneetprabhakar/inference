import copy,json,unittest
import harness as h
class Tools(unittest.TestCase):
 def test_all_ten_crud(self):
  for name,field in h.TOOLS.items():
   m=h.MockTools()
   for op,value in [('create','one'),('read',None),('update','two'),('read',None),('delete',None)]:
    args={'op':op,'id':'r1'}
    if value:args[field]=value
    r=m.call({'name':name,'arguments':args});self.assertTrue(r['ok'])
    if op=='read':self.assertEqual(r['record'][field],'two' if len(m.trace)==4 else 'one')
   self.assertEqual(m.state[name],{})
 def test_disabled_no_mutation(self):
  m=h.MockTools();before=copy.deepcopy(m.state);self.assertTrue(m.call({'name':'notes','arguments':{'op':'create','id':'r1','text':'x'}},False)['blocked']);self.assertEqual(m.state,before)
 def test_duplicate_missing_invalid(self):
  m=h.MockTools();p={'name':'notes','arguments':{'op':'create','id':'r1','text':'a'}};m.call(p);self.assertEqual(m.call(p)['error'],'already_exists')
  self.assertEqual(m.call({'name':'notes','arguments':{'op':'read','id':'absent'}})['error'],'not_found')
  before=copy.deepcopy(m.state);p['arguments']['extra']='bad';self.assertTrue(m.call(p)['blocked']);self.assertEqual(m.state,before)
 def test_isolation(self):
  m=h.MockTools();m.call({'name':'notes','arguments':{'op':'create','id':'r1','text':'a'}});self.assertEqual(h.MockTools().state['notes'],{})
class Transport(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  import sys
  sys.path.insert(0,str(h.ROOT/'runs/nanochat-source'))
  from nanochat.tokenizer import RustBPETokenizer
  from cloud_training.nano_chat_format import token_contract
  cls.tok=RustBPETokenizer.from_directory(str(h.ROOT/'runs/ownbase-v2-data/tokenizer'));cls.c=token_contract(cls.tok)
 def test_scripted_oracle_every_case(self):
  for case in h.cases():
   queue=[]
   for turn in case['turns']:
    if turn['expected_call']:queue.append([self.c['<|python_start|>']]+self.tok.encode(h.dump(turn['expected_call']))+[self.c['<|python_end|>']])
    queue.append(self.tok.encode('Mock test response.')+[self.c['<|assistant_end|>']])
   result=h.run_case(case,self.tok,lambda ids,n:queue.pop(0),2048,128)
   self.assertTrue(all(t['structural_pass'] for t in result['turns']),result)
   self.assertFalse(queue)
 def test_invalid_frame_blocks_followups(self):
  case=next(c for c in h.cases() if c['id']=='notes_workflow')
  result=h.run_case(case,self.tok,lambda ids,n:self.tok.encode('unterminated'),2048,128)
  self.assertEqual([r['status'] for r in result['turns']],['invalid_model_action']+['blocked_previous']*3)
 def test_duplicate_json_rejected(self):
  ids=[self.c['<|python_start|>']]+self.tok.encode('{"name":"notes","name":"tasks","arguments":{}}')+[self.c['<|python_end|>']]
  self.assertEqual(h.parse(self.tok,ids,self.c)['kind'],'invalid')
if __name__=='__main__':unittest.main()
