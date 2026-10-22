"""Runtime combined-census refusal/throttle; synthetic only."""
from unittest.mock import patch
from pathlib import Path
import argparse,signal,json
import pilot
cases=[]
with patch.object(pilot,'clk',return_value=100),patch.object(pilot.shutil,'disk_usage',return_value=argparse.Namespace(free=10**12)):
 pilot.LAST_RESOURCE=0;pilot.LAST_COMBINED=0
 with patch.object(pilot,'size',side_effect=lambda p:64000000001 if p==pilot.ROOT else 0):
  try:pilot.guard(Path('/synthetic-owned-output'),99,285)
  except ValueError as e:assert str(e)=='runtime_combined_intake64GB';cases.append('runtime64GBrefuses')
  else:raise AssertionError('missing combined cap')
 pilot.LAST_RESOURCE=0;pilot.LAST_COMBINED=0;calls=[]
 def size(p):calls.append(p);return 1000
 with patch.object(pilot,'size',side_effect=size):
  pilot.guard(Path('/synthetic-owned-output'),99,285);pilot.guard(Path('/synthetic-owned-output'),99,285)
  assert calls.count(pilot.ROOT)==1;cases.append('combined_census5sec_throttle')
signal.setitimer(signal.ITIMER_REAL,0)
print(json.dumps({'status':'PASS_FOCUSED_SYNTHETIC_ONLY','controls':len(cases),'source_body_or_capture_reads':0,'cases':cases}))
