import unittest,json,pathlib,sqlite3
from filter import reasons
P=pathlib.Path(__file__).resolve().parent
class FilterRegression(unittest.TestCase):
 def test_previous_semantic_failures_are_rejected_without_id_rules(self):
  c=sqlite3.connect(f'file:{P.parent}/corpus-audit-v1/audit.sqlite?mode=ro',uri=True)
  js=[json.loads(x) for x in (P.parent/'semantic-review-v1/judgments.jsonl').read_text().splitlines()]
  for j in js:
   if j['source']=='FineWeb' and j['label'] in ['fail','major']:
    t,n=c.execute('select text,tokens from docs where id=?',(j['audit_id'],)).fetchone()
    with self.subTest(id=j['audit_id']):self.assertTrue(reasons(t,n))
 def test_clean_prose_can_survive(self):
  c=sqlite3.connect(f'file:{P.parent}/corpus-audit-v1/audit.sqlite?mode=ro',uri=True)
  t,n=c.execute('select text,tokens from docs where id=148699').fetchone()
  self.assertEqual(reasons(t,n),[])
 def test_complete_sentences_do_not_hide_shortcode(self):
  t=('The river flows past a village where people gather near the bridge.\n'
     'The bridge carries travelers across the valley in every season. [button]')
  self.assertIn('link_markup_or_encoding',reasons(t,150))
if __name__=='__main__':unittest.main()
