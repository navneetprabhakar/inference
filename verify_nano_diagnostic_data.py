import json
from pathlib import Path
import tempfile
import unittest
from cloud_training.nano_diagnostic_data import choose,text_hash,fingerprint,user_hashes


class DiagnosticTests(unittest.TestCase):
    def row(self,user,answer='ok'):
        return {'messages':[{'role':'user','content':user},{'role':'assistant','content':answer}],'policies':None}

    def test_dev_and_quality_prompt_exclusion_normalizes_unicode_case_space(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'rows';rows=[self.row('ＢＬＵＥ   Notebook'),self.row('fresh question')]
            p.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            selected,rejected=choose(p,1,{text_hash('blue notebook')},set())
            self.assertEqual(selected,[rows[1]]);self.assertEqual(rejected,1)

    def test_duplicate_complete_conversations_cross_source_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'rows';a=self.row('one');b=self.row('two')
            p.write_text(json.dumps(a)+'\n'+json.dumps(b)+'\n')
            selected,rejected=choose(p,1,set(),{fingerprint(a)})
            self.assertEqual(selected,[b]);self.assertEqual(rejected,1)
            with self.assertRaisesRegex(ValueError,'Insufficient'):choose(p,3,set(),set())

    def test_known_bad_id_replaced_with_next_eligible(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'rows';a=self.row('bad');a['id']='known-bad';b=self.row('replacement');b['id']='replacement'
            p.write_text(json.dumps(a)+'\n'+json.dumps(b)+'\n')
            selected,rejected=choose(p,1,set(),set(),{'known-bad'})
            self.assertEqual(selected,[b]);self.assertEqual(rejected,1)

    def test_any_later_user_turn_protects_whole_session(self):
        row=self.row('first');row['messages'].append({'role':'user','content':'held out'})
        self.assertIn(text_hash('held out'),user_hashes(row))


if __name__=='__main__':unittest.main()
