import sys,json,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from author_conversations_batched import normalize_envelope
class EnvelopeTest(unittest.TestCase):
 def test_string_normalization_preserves_exact_content(self):
  original=['A question?',' An answer.\nWith a newline.']
  text,change=normalize_envelope(json.dumps({'messages':original}));o=json.loads(text)
  self.assertEqual([m['content'] for m in o['messages']],original)
  self.assertEqual([m['role'] for m in o['messages']],['user','assistant']);self.assertIsNotNone(change)
 def test_mixed_or_extra_fields_not_silently_repaired(self):
  for o in [{'messages':['hello',{'role':'assistant','content':'hi'}]},{'messages':['a','b'],'extra':'x'}]:
   text=json.dumps(o);self.assertEqual(normalize_envelope(text),(text,None))
if __name__=='__main__':unittest.main()
