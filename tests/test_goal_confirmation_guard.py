import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from goal_confirmation_guard import authorize, sha, validate_completed_prefix

class ConfirmationGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.goal = self.root / 'goal'; self.goal.mkdir()
        self.cp = self.root / 'checkpoint'; self.cp.mkdir()
        (self.cp / 'model.safetensors').write_bytes(b'fixture-checkpoint')
        self.ev = self.root / 'evaluation'; self.ev.mkdir()
        (self.goal / 'authorization.json').write_text(json.dumps({'deadline_unix': 10000}))
        (self.ev / 'confirmation.jsonl').write_text('{}\n')
        (self.ev / 'development.jsonl').write_text(json.dumps({'id':'dev-1','tool_mode':True})+'\n')
        self.review = self.root / 'review.json'
        self.review.write_text(json.dumps({'checkpoint_sha256':sha(self.cp/'model.safetensors'),'cases':[{'id':'dev-1','conversation_pass':False,'specific_reason':'wrong answer'}]}))
        self.sel = self.root / 'selection.json'
        self.sel.write_text(json.dumps({'training_closed':True,'checkpoint_sha256':sha(self.cp/'model.safetensors'),'confirmation_sha256':sha(self.ev/'confirmation.jsonl'),'development_review':str(self.review),'development_review_sha256':sha(self.review)}))
        self.out = self.root/'output'
    def go(self, now=9000, out=None):
        return authorize(self.sel,self.cp,self.ev,out or self.out,self.goal,now)
    def test_weak_candidate_cannot_consume_early(self):
        with self.assertRaisesRegex(RuntimeError,'Too early'): self.go(100)
        self.assertFalse((self.goal/'confirmation-started.json').exists())
    def test_final_window_commits_once_and_allows_identical_resume(self):
        first=self.go(); self.assertEqual(first,self.go(9100))
        with self.assertRaisesRegex(RuntimeError,'different selection/output'): self.go(out=self.root/'different')
    def test_changed_checkpoint_rejected(self):
        (self.cp/'model.safetensors').write_bytes(b'changed')
        with self.assertRaisesRegex(RuntimeError,'checkpoint hash'): self.go()
    def test_review_edits_rejected(self):
        self.review.write_text('{}')
        with self.assertRaisesRegex(RuntimeError,'review changed'): self.go()
    def test_confirmation_pins_selected_decoding(self):
        from goal_decoding import policy
        chosen=policy(1.2,1.0)
        review=json.loads(self.review.read_text());review['decoding']=chosen;self.review.write_text(json.dumps(review))
        selection=json.loads(self.sel.read_text());selection.update(decoding=chosen,development_review_sha256=sha(self.review));self.sel.write_text(json.dumps(selection))
        receipt=authorize(self.sel,self.cp,self.ev,self.out,self.goal,9000,decoding=chosen)
        self.assertEqual(receipt['identity']['decoding'],chosen)
        with self.assertRaisesRegex(RuntimeError,'Selection decoding differs'):
            authorize(self.sel,self.cp,self.ev,self.out,self.goal,9100,decoding=policy())
    def test_mismatched_development_decoder_rejected(self):
        from goal_decoding import policy
        selection=json.loads(self.sel.read_text());selection['decoding']=policy(1.2,1.0);self.sel.write_text(json.dumps(selection))
        with self.assertRaisesRegex(RuntimeError,'Development review belongs to different decoding'):
            authorize(self.sel,self.cp,self.ev,self.out,self.goal,9000,decoding=policy(1.2,1.0))
        self.assertFalse((self.goal/'confirmation-started.json').exists())
    def test_deadline_and_stop_rejected(self):
        with self.assertRaisesRegex(RuntimeError,'deadline or STOP'): self.go(10000)
        (self.goal/'STOP').write_text('user stop')
        with self.assertRaisesRegex(RuntimeError,'deadline or STOP'): self.go()

class ConfirmationResumeTests(unittest.TestCase):
    def setUp(self):
        self.records = [{'id':'a','turns':[{'user':'First'},{'user':'Second'}]}, {'id':'b','turns':[{'user':'Third'}]}]
        self.row = {'id':'a','turns':[{'user':'First','student_reply':{'output':'A'}},{'user':'Second','student_reply':{'output':'B'}}]}
    def test_complete_prefix_is_resumable(self):
        self.assertEqual(validate_completed_prefix([self.row],self.records),1)
        self.assertEqual(validate_completed_prefix([],self.records),0)
    def test_skipped_conversation_rejected(self):
        with self.assertRaisesRegex(RuntimeError,'prefix mismatch'):
            validate_completed_prefix([{'id':'b','turns':[]}],self.records)
    def test_partial_conversation_rejected(self):
        self.row['turns'].pop()
        with self.assertRaisesRegex(RuntimeError,'Incomplete conversation'):
            validate_completed_prefix([self.row],self.records)
    def test_changed_prompt_rejected(self):
        self.row['turns'][0]['user']='Changed'
        with self.assertRaisesRegex(RuntimeError,'differs from frozen case'):
            validate_completed_prefix([self.row],self.records)

if __name__=='__main__': unittest.main()
