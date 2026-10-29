import copy,unittest
import repair
class BindingTests(unittest.TestCase):
 def test_html_encoding(self):self.assertTrue(repair.body_equal('<p>"A" &amp; B</p>\n\n<p>C</p>','<p>&quot;A&quot; &#38; B</p>\n<p>C</p>'))
 def test_word_mutation(self):self.assertFalse(repair.body_equal('<p>do not eat</p>','<p>do eat</p>'))
 def test_link_mutation(self):self.assertFalse(repair.body_equal('<p><a href="a">x</a></p>','<p><a href="b">x</a></p>'))
 def test_inline_space(self):self.assertFalse(repair.body_equal('<p>A <b>B</b></p>','<p>A<b>B</b></p>'))
 def test_paragraph_loss(self):self.assertFalse(repair.body_equal('<p>A</p><p>B</p>','<p>AB</p>'))
 def test_double_encoding(self):self.assertFalse(repair.body_equal('<p>&amp;lt;x&amp;gt;</p>','<p>&lt;x&gt;</p>'))
 def test_timestamp_tie(self):self.assertEqual(repair.latest([{'body':'old','creation_date':1,'revision_number':1},{'body':'new','creation_date':1,'revision_number':2}],'body')['body'],'new')
 def test_tag_only(self):self.assertTrue(repair.noncontent({'tags':['a'],'revision_type':'single_user'}))
 def test_unknown(self):self.assertFalse(repair.noncontent({'revision_type':'single_user'}))
 def test_vote_with_body(self):self.assertTrue(repair.content_event({'revision_type':'vote_based','body':'x'}));self.assertFalse(repair.noncontent({'revision_type':'vote_based','body':'x'}))
 def test_content_license_and_binding(self):
  r=repair.read(repair.P/'private/provenance-candidates.json')[0];pair=None
  import gzip,json
  for f in (repair.A/'private/primary').glob('*-pairs.jsonl.gz'):
   for line in gzip.open(f,'rt'):
    x=json.loads(line)
    if (x['site'],x['question']['question_id'])==(r['site'],r['question_id']):pair=x
  hist=repair.read(repair.A/'private/revision-index.json');self.assertIsNone(repair.bind(pair,r,hist)[0])
  wrong=copy.deepcopy(pair);wrong['answer']['question_id']+=1
  with self.assertRaises(AssertionError):repair.bind(wrong,r,hist)
  wrong=copy.deepcopy(pair);wrong['answer']['answer_id']+=1
  with self.assertRaises(AssertionError):repair.bind(wrong,r,hist)
  wrong=copy.deepcopy(pair);wrong['site']='wrong'
  with self.assertRaises(AssertionError):repair.bind(wrong,r,hist)
  for field in ['content_license','user']:
   bad=copy.deepcopy(hist);key=r['site']+':'+str(r['question_id']);e=next(e for e in bad[key] if repair.content_event(e));e.pop(field,None)
   self.assertEqual(repair.bind(pair,r,bad)[0],'unresolved_content_license_or_contributor')
  self.assertEqual(repair.bind(pair,r,{})[0],'missing_complete_history')
if __name__=='__main__':unittest.main()
