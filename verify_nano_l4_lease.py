import datetime as dt,unittest
from cloud_training.nano_l4_lease import plan
class LeaseTests(unittest.TestCase):
 def args(self):return dict(project='forge-project',zone='us-central1-a',name='forge-english-qualify',image='projects/deeplearning-platform-release/global/images/pinned-image',service_account='worker@forge-project.iam.gserviceaccount.com',bootstrap='/tmp/verified.sh',now=dt.datetime(2026,11,14,tzinfo=dt.timezone.utc),hours=1)
 def test_stop_preserves_disk_and_bounds_cost(self):
  r=plan(**self.args());a=r['create_argv']
  self.assertIn('--instance-termination-action=STOP',a);self.assertIn('--no-boot-disk-auto-delete',a)
  self.assertIn('--termination-time=2026-11-14T01:00:00Z',a);self.assertNotIn('--boot-disk-auto-delete',a);self.assertLess(r['compute_envelope_usd']+r['reserve_usd'],10)
 def test_same_rate_verified_regions_keep_envelope(self):
  for zone in ('us-east1-b','us-east4-c','us-west1-a'):
   a=self.args();a['zone']=zone;r=plan(**a)
   self.assertEqual(r['compute_envelope_usd'],plan(**self.args())['compute_envelope_usd'])
 def test_cumulative_cost_cannot_reset(self):
  a=self.args();a.update(hours=6,prior_reserved_usd=1)
  with self.assertRaises(ValueError):plan(**a)
 def test_rejects_unpriced_region_and_unbounded_time(self):
  for changes in [dict(zone='asia-south1-a'),dict(zone='us-central1-f'),dict(hours=7),dict(hours=float('nan')),dict(hours=True),dict(prior_reserved_usd=-1)]:
   a=self.args();a.update(changes)
   with self.assertRaises(ValueError):plan(**a)
if __name__=='__main__':unittest.main()
