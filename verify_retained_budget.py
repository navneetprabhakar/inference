import copy
import unittest
from cloud_training.campaign_budget import retained_cost

class RetainedBudgetTests(unittest.TestCase):
    def setUp(self):
        self.ledger={'cap_usd':100,'ancillary_reserve_usd':10,'allocations':[{'id':'old','reserved_usd':8.98,'state':'closed_verified_DELETED'}]}
    def test_full_lifetime_includes_protected_finish(self):
        r=retained_cost(self.ledger,hours=32,finish_hours=4)
        self.assertEqual(r['total_envelope_usd'],98.98)
        self.assertEqual(r['base_and_setup_hours_max'],28)
    def test_cannot_hide_finish_or_exceed_cap(self):
        for h,f in [(33,4),(32,3),(4,4),(float('nan'),4)]:
            with self.assertRaises(ValueError):retained_cost(self.ledger,hours=h,finish_hours=f)
        self.ledger['allocations'][0]['reserved_usd']=10.01
        with self.assertRaises(ValueError):retained_cost(self.ledger,hours=32,finish_hours=4)
    def test_no_second_gpu(self):
        self.ledger['allocations'][0]['state']='running'
        with self.assertRaises(ValueError):retained_cost(self.ledger,hours=32,finish_hours=4)

if __name__=='__main__':unittest.main()
