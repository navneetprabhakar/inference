"""Fresh-process actual SFT loop control tests with mocked numerical/I/O work."""
import json,subprocess,sys,unittest
from cloud_training.nano_qualification_schedule import restart_branches,validate_restart_branches

def run(**kwargs):
    return json.loads(subprocess.check_output([sys.executable,'-m','reports.english-first-v1.check_loop',json.dumps(kwargs)],text=True))

class QualificationTests(unittest.TestCase):
    def test_rejects_old_observation_schedule(self):
        b=restart_branches();b['uninterrupted']['eval_every_updates']=5
        with self.assertRaises(ValueError):validate_restart_branches(b)
    def test_fresh_process_split_matches_stop_and_best(self):
        for losses in ([3.,3.3,3.3],[3.,2.8,2.7],[3.,2.8,3.1]):
            whole=run(updates=2,losses=losses)
            first=run(updates=1,losses=losses)
            resumed=run(updates=1,losses=losses,state=first)
            for key in ('step','guard','best_dev','best_step','reason'):self.assertEqual(whole[key],resumed[key],key)
            self.assertEqual(whole['observed'],first['observed']+resumed['observed'])
    def test_old_schedule_reproduces_mismatch(self):
        whole=run(updates=2,losses=[3.,3.3,3.3],cadence=5)
        first=run(updates=1,losses=[3.,3.3,3.3],cadence=5)
        resumed=run(updates=1,losses=[3.,3.3,3.3],cadence=5,state=first)
        self.assertNotEqual(whole['guard'],resumed['guard'])
    def test_signal_does_not_insert_unscheduled_observation(self):
        losses=[3.,3.3,3.3]
        first=run(updates=2,losses=losses,cadence=5,signal_at=1)
        self.assertEqual(first['observed'],[])
        self.assertEqual(first['reason'],'lease_or_signal')
        resumed=run(updates=1,losses=losses,cadence=5,state=first)
        whole=run(updates=2,losses=losses,cadence=5)
        for key in ('guard','best_step','best_dev'):self.assertEqual(whole[key],resumed[key])
if __name__=='__main__':unittest.main()
