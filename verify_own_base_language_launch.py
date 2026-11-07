"""Small watchdog/accounting checks; no training or model allocation."""
import json,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import own_base_language_launch as launch

class Tests(unittest.TestCase):
    def test_finite_remaining_lease_and_original_calendar(self):
        spec=dict(lease_seconds=100,active_seconds=500,calendar_seconds=1000)
        budget=dict(charged_active_seconds=470,first_started_wall=10)
        self.assertEqual(launch.remaining_allowance(spec,budget,100),30)
        self.assertEqual(launch.remaining_allowance(spec,budget,1005),5)
        self.assertLess(launch.remaining_allowance(spec,budget,1011),0)
    def test_reserved_supervisor_budget_tamper(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'budget.json';value=dict(charged_active_seconds=100.,first_started_wall=10.)
            launch.write_budget(p,value);self.assertEqual(launch.read_budget(p),value)
            bad=json.loads(p.read_text());bad['charged_active_seconds']=0;p.write_text(json.dumps(bad))
            with self.assertRaises(ValueError):launch.read_budget(p)
    def test_owned_nonreturning_child_terminated(self):
        with tempfile.TemporaryDirectory() as td:
            ticket=launch.runtime.make_ticket(2.)
            with patch.object(launch.runtime,'group_rss',return_value=0):
                result=launch.runtime.supervise(lambda fd:[sys.executable,'-c','import time;time.sleep(10)'],Path(td),ticket=ticket,heartbeat_seconds=.2,grace_seconds=.2,max_rss_bytes=2**40)
            self.assertIsNotNone(result['watchdog_reason']);self.assertNotEqual(result['exit_code'],0);self.assertLess(result['seconds'],2.)

if __name__=='__main__':unittest.main(verbosity=2)
