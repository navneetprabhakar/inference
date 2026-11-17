"""Run each distinct test implementation once; avoid imported/inherited duplicates."""
import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
modules='verify_nano_recovery_gate verify_nano_recovery_controller verify_nano_recovery_tasks verify_nano_fit_probe verify_nano_sft verify_nano_sft_data verify_nano_fit_contract verify_nano_fit_readiness verify_nano_quality_gate verify_nano_retention verify_nano_checkpoint verify_nano_serve verify_nano_optimizer_capture verify_nano_update_trace verify_nano_qualification_schedule verify_nano_qualification_worker verify_nano_package verify_nano_quality'.split()
alltests=unittest.TestLoader().loadTestsFromNames(modules)
def flatten(s):
 for t in s:
  if isinstance(t,unittest.TestSuite):yield from flatten(t)
  else:yield t
seen=set();tests=[]
for t in flatten(alltests):
 f=getattr(type(t),t._testMethodName)
 if f not in seen:tests.append(t);seen.add(f)
result=unittest.TextTestRunner(verbosity=1).run(unittest.TestSuite(tests))
raise SystemExit(not result.wasSuccessful())
