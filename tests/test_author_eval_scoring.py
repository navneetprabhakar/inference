import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from author_eval_scoring import tool_trace

def call(name, arguments): return '<|tool_call|>'+json.dumps({'name':name,'arguments':arguments},separators=(',',':'))
def parser(text): return json.loads(text[len('<|tool_call|>'):])
def executor(value): return {'ok':value['arguments']['x']}
def generation(text): return {'output':text,'stop':'eos','generated_tokens':1,'repeated_4gram_fraction':0}
def record(): return {'messages':[{'role':'user','content':'x'}],'calls':[{'name':'demo','arguments':{'x':1}}],'expected_answer':'done','max_turns':4}

class ToolTraceTest(unittest.TestCase):
 def test_wrong_and_extra_calls_are_rejected(self):
  values=iter([generation(call('demo',{'x':2}))]); r=tool_trace(record(),lambda _:next(values),parser=parser,executor=executor)
  self.assertTrue(r['wrong_call']); self.assertFalse(r['success'])
  values=iter([generation(call('demo',{'x':1})),generation(call('demo',{'x':1}))]); r=tool_trace(record(),lambda _:next(values),parser=parser,executor=executor)
  self.assertTrue(r['extra_call']); self.assertFalse(r['success'])
 def test_early_final_and_valid_result_use(self):
  values=iter([generation('done')]); r=tool_trace(record(),lambda _:next(values),parser=parser,executor=executor)
  self.assertTrue(r['early_final']); self.assertFalse(r['success'])
  r={'messages':[{'role':'user','content':'result'}],'calls':[],'expected_answer':'done','max_turns':1}
  values=iter([generation('done')]); scored=tool_trace(r,lambda _:next(values),parser=parser,executor=executor)
  self.assertTrue(scored['success'])
 def test_malformed_and_turn_limit_are_retained_as_failures(self):
  values=iter([generation('<|tool_call|>{not json}')]); r=tool_trace(record(),lambda _:next(values),parser=parser,executor=executor)
  self.assertEqual(r['terminal_reason'],'invalid_tool_call'); self.assertFalse(r['success']); self.assertTrue(r['trace'][0]['rejected'])
  r=record(); r['max_turns']=1
  values=iter([generation(call('demo',{'x':1}))]); scored=tool_trace(r,lambda _:next(values),max_turns=6,parser=parser,executor=executor)
  self.assertEqual(scored['terminal_reason'],'turn_limit'); self.assertFalse(scored['success'])

if __name__ == '__main__': unittest.main()
