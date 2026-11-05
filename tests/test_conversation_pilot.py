import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from prepare_conversation_pilot import clean_episode,quality_reason

class ConversationPreparationTest(unittest.TestCase):
 def test_only_complete_boundary_turns_removed(self):
  original=[{'role':'user','content':'Hey!'}, {'role':'assistant','content':'Hello!'}, {'role':'user','content':'How do I organize my shelf?'}, {'role':'assistant','content':'Start with one section.'}, {'role':'user','content':'What should I keep there?'}, {'role':'assistant','content':'Keep the things you use regularly.'}, {'role':'user','content':'Thanks!'}]
  before=copy.deepcopy(original);clean,edits=clean_episode(original)
  self.assertEqual(original,before);self.assertEqual(clean,original[2:6]);self.assertEqual(len(edits),2)
 def test_substantive_first_turn_not_removed(self):
  ms=[{'role':'user','content':'Hello, how can I sort my books?'},{'role':'assistant','content':'Choose a simple grouping.'},{'role':'user','content':'Would sorting by author work?'},{'role':'assistant','content':'Yes, if that helps you find them.'}]
  clean,edits=clean_episode(ms);self.assertEqual(clean,ms);self.assertEqual(edits,[])
 def test_persona_and_loops_screened(self):
  base=[{'role':'user','content':'Tell me about cats.'},{'role':'assistant','content':'My cat is sleeping on my chair.'}]
  self.assertEqual(quality_reason(base),'possible_invented_persona')
  base[1]['content']='You can keep all your books here. You can keep all your books here.'
  self.assertEqual(quality_reason(base),'repeated_sixword_phrase')
 def test_incomplete_and_system_roles_rejected(self):
  for ms in [[{'role':'user','content':'Hello'}],[{'role':'system','content':'Do something'},{'role':'assistant','content':'Okay'}]]:
   self.assertIsNone(clean_episode(ms)[0])
if __name__=='__main__':unittest.main()
