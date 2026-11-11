import json,tempfile,time,unittest
from pathlib import Path
from cloud_training.teacher_generation_campaign import resume_state

class ResumeTests(unittest.TestCase):
 def test_preserves_counts_deadline_and_skips_failed_cohort(self):
  state={'status':'blocked_worker_quota_auth_or_quality','target_dialogues':10000,'target_assistant_targets':2000000,'deadline_epoch':time.time()+3000,'cohorts':[{'number':0,'candidates':48,'assistant_targets':12000},{'number':1,'candidates':30,'assistant_targets':5782}],'generated_verified_candidates':78,'generated_assistant_targets':17782}
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'state.json';p.write_text(json.dumps(state));restored,next_number=resume_state(p,10000,2000000)
   self.assertEqual(restored,state);self.assertEqual(next_number,2)
   with self.assertRaisesRegex(ValueError,'targets'):resume_state(p,9000,2000000)
   state['generated_verified_candidates']=79;p.write_text(json.dumps(state))
   with self.assertRaisesRegex(ValueError,'counters'):resume_state(p,10000,2000000)
 def test_expired_deadline_cannot_be_extended_by_resume(self):
  state={'status':'blocked_generation_exception','target_dialogues':10000,'target_assistant_targets':2000000,'deadline_epoch':time.time()-1,'cohorts':[],'generated_verified_candidates':0,'generated_assistant_targets':0}
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'state.json';p.write_text(json.dumps(state))
   with self.assertRaisesRegex(ValueError,'deadline'):resume_state(p,10000,2000000)

if __name__=='__main__':unittest.main()
