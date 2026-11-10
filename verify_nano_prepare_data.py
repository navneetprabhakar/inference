import unittest
from cloud_training.nano_prepare_data import finite_bestfit_rows

class PackingTests(unittest.TestCase):
    def test_largest_fit_then_shortest_crop(self):
        stats={}
        rows=list(finite_bestfit_rows([[[0,1,2],[0,3],[0,4,5,6,7,8]]],4,buffer_size=3,stats=stats))
        self.assertEqual(rows,[[0,1,2,0,3],[0,4,5,6,7]])
        self.assertEqual(stats['cropped_tokens'],1)
        self.assertEqual(stats['source_tokens'],11)

    def test_refill_before_each_choice(self):
        rows=list(finite_bestfit_rows([[[0,1],[0,2]],[[0,3,4]]],4,buffer_size=2))
        self.assertEqual(rows[0],[0,1,0,3,4])
        self.assertEqual(len(rows),1)

    def test_finite_tail_never_replays(self):
        stats={}
        rows=list(finite_bestfit_rows([[[0,1,2]]],4,buffer_size=1000,stats=stats))
        self.assertEqual(rows,[])
        self.assertEqual(stats['incomplete_tail_positions'],3)

    def test_empty_document_rejected(self):
        with self.assertRaises(ValueError):list(finite_bestfit_rows([[[]]],4))

if __name__=='__main__':unittest.main()
