import json,sys,tempfile,unittest
from pathlib import Path
import numpy as np
import mlx.core as mx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from train_continuation import FreshCorpus,learning_rate
from prepare_continuation import Near,fingerprint,english
class ContinuationTest(unittest.TestCase):
    def test_resume_no_replay_and_source_counts(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);np.arange(512*20+1,dtype=np.uint16).tofile(p/'train.bin');(p/'manifest.json').write_text(json.dumps({'source_ranges':{'fineweb':[0,512*10],'wikipedia':[512*10,512*15],'pressbooks':[512*15,512*20]}}))
            c=FreshCorpus(p);c.batch(256);restored=FreshCorpus(p,c.state());seen=set(c.order[:c.cursor].tolist())
            for _ in range(9):
                before=c.cursor;a=c.batch();b=restored.batch();self.assertTrue(bool(mx.array_equal(a,b)))
                positions=set(c.order[before:c.cursor].tolist());self.assertFalse(positions&seen);seen|=positions
            self.assertEqual(sum(c.source_counts.values()),256+9*1024)
            with self.assertRaises(RuntimeError):c.batch()
    def test_schedule_continuous_at_stage_boundary(self):
        self.assertAlmostEqual(learning_rate(100000000),3e-5);self.assertAlmostEqual(learning_rate(102000000),1e-4);self.assertAlmostEqual(learning_rate(300000000),1e-5)
        self.assertLess(abs(learning_rate(200000000)-learning_rate(200000001)),1e-10)
    def test_near_index_and_language_filter(self):
        n=Near();n.add(123456789);self.assertTrue(n.contains(123456789^7));self.assertFalse(n.contains((1<<64)-1));self.assertEqual(fingerprint('the cat sat on the mat'),fingerprint('THE CAT SAT ON THE MAT'))
        self.assertFalse(english('abc xyz '*100))
if __name__=='__main__':unittest.main()
