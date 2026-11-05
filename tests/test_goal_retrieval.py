import argparse,copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from tokenizers import Tokenizer
from evaluate_goal_retrieval import Retriever,main
from sft_common import ROOT,render,system

class RetrievalIntegrityTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tok=Tokenizer.from_file(str(ROOT/'data/sft-v3/tokenizer.json'))
  cls.retriever=Retriever(ROOT/'data/eight-hour-clean-expanded-v1/records.jsonl',cls.tok)
 def test_preserves_actual_history_and_returns_traceable_example(self):
  history=[{'role':'user','content':'Please use the calculation tool to add 23 and 17.'},{'role':'assistant','content':'<|tool_call|>{"name":"calculate","arguments":{"op":"add","a":23,"b":17}}'},{'role':'tool','content':'{"result":40}'}]
  messages=[{'role':'system','content':system(['calculate'])}]+history
  original=copy.deepcopy(messages);augmented,trace=self.retriever.augment(messages)
  self.assertEqual(messages,original)
  self.assertEqual(augmented[-len(history):],history)
  self.assertIsNotNone(trace['id'])
  self.assertEqual(trace['corpus_sha256'],self.retriever.sha)
  self.assertLessEqual(len(self.tok.encode(render(augmented,True)).ids),400)
 def test_long_history_is_not_truncated_for_example(self):
  messages=[{'role':'user','content':'Explain this note. '+('A long existing conversation. '*300)}]
  augmented,trace=self.retriever.augment(messages)
  self.assertEqual(augmented,messages)
  self.assertIsNone(trace['id'])
 def test_confirmation_is_rejected_before_any_decode(self):
  with self.assertRaisesRegex(RuntimeError,'development-only'):
   main(argparse.Namespace(split='confirmation'))
if __name__=='__main__':unittest.main()
