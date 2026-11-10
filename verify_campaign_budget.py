import json,tempfile,unittest
from pathlib import Path
from cloud_training.campaign_budget import forecast,reserve

class BudgetTests(unittest.TestCase):
 def test_arithmetic_and_invalid(self):
  self.assertAlmostEqual(forecast(remaining_tokens=360000000,tokens_per_second=100000,overhead_fraction=.1)['remaining_compute_envelope_usd'],2.75)
  for x in (float('nan'),0,-1):
   with self.assertRaises(ValueError):forecast(remaining_tokens=1,tokens_per_second=x,overhead_fraction=0)
 def test_whole_campaign_not_just_lease(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'ledger.json';p.write_text(json.dumps({'cap_usd':100,'ancillary_reserve_usd':10,'allocations':[{'id':'past','reserved_usd':6,'state':'closed_verified_DELETED'}]}))
   too_large=forecast(remaining_tokens=10_000_000_000,tokens_per_second=50000,overhead_fraction=.1)
   with self.assertRaises(ValueError):reserve(p,'new',hours=1,projection=too_large,price_receipt='price',admission_receipt='data')
   affordable=forecast(remaining_tokens=10_000_000_000,tokens_per_second=120000,overhead_fraction=.1)
   v=reserve(p,'new',hours=12,projection=affordable,price_receipt='price',admission_receipt='data');self.assertEqual(v['remaining_unallocated_usd'],54)
   with self.assertRaises(ValueError):reserve(p,'parallel',hours=1,projection=affordable,price_receipt='price',admission_receipt='data')
 def test_finish_reserve_and_wrong_cap(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'ledger.json';p.write_text(json.dumps({'cap_usd':101,'ancillary_reserve_usd':10,'allocations':[]}))
   with self.assertRaises(ValueError):reserve(p,'new',hours=1,projection={'remaining_compute_envelope_usd':3},price_receipt='price',admission_receipt='data')
if __name__=='__main__':unittest.main()
