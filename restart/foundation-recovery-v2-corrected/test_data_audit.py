"""CPU-only audit fixtures; never resumes the terminal experiment."""
import unittest,sys,sqlite3
import numpy as np
from d0_dedupe import shingles,sketch,jaccard,DSU,words
from common import ROOT,read,sha
class DataAudit(unittest.TestCase):
 def test_shingle_jaccard_independent_tuples(self):
  a='one two three four five six seven eight nine ten eleven twelve';b=a+' thirteen';wa=words(a);wb=words(b)
  sa={tuple(wa[i:i+5]) for i in range(len(wa)-4)};sb={tuple(wb[i:i+5]) for i in range(len(wb)-4)}
  self.assertAlmostEqual(jaccard(shingles(a),shingles(b)),len(sa&sb)/len(sa|sb))
 def test_near_retrieval_control(self):
  a=' '.join('word'+str(i) for i in range(40));b=a.rsplit(' ',1)[0]+' changed';x=shingles(a);y=shingles(b)
  self.assertGreaterEqual(jaccard(x,y),.8);sx=sketch(x);sy=sketch(y)
  self.assertTrue(any(np.array_equal(sx[i:i+4],sy[i:i+4]) for i in range(0,64,4)))
  self.assertEqual(jaccard(x,shingles('other entirely separate independent sentence words here')),0)
 def test_connected_family_transitivity(self):
  d=DSU(4);d.union(0,1);d.union(1,2);self.assertEqual(d.find(0),d.find(2));self.assertNotEqual(d.find(0),d.find(3))
 def test_supply_stop_independent_bound(self):
  n=read(ROOT/'D0/dedup.json')['native_content_tokens'];upper=min(sum(n.values())-2000000,2*(n['everyday']+n['procedural']),int(n['everyday']/.15),int(n['procedural']/.15))
  self.assertEqual(upper,9734693);self.assertLess(n['everyday'],1500000)
 def test_sample_once_and_fail_denominator(self):
  a=read(ROOT/'D0/fresh-sample.json');self.assertEqual(len(a['draws']),100);self.assertEqual(len({d['h'] for d in a['draws']}),100)
  self.assertEqual(sha(ROOT/'D0/fresh-sample.json'),read(ROOT/'D0/semantic-review.json')['sample_sha256'])
  s=read(ROOT/'D0/semantic-review.json');self.assertEqual(s['unread_draws'],94);self.assertLess(s['uniform_best_possible_pass'],48)
 def test_zero_training_ledger(self):
  d=sqlite3.connect(ROOT/'work.sqlite');self.assertEqual(d.execute("select coalesce(sum(positions),0) from work where kind like 'training%'").fetchone()[0],0)
if __name__=='__main__':unittest.main()
