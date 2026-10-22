"""New census cadence only; actual synthetic guard, no retained source calls."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import json
import pilot
N=0
out=Path('/synthetic/own');now=[100.0];calls=[];custody=[]
def size(p):calls.append(p);return 1000 if p==out else 1000000
with patch.object(pilot,'clk',lambda:now[0]),patch.object(pilot,'size',size),patch.object(pilot.shutil,'disk_usage',lambda p:SimpleNamespace(free=10**12)):
 pilot.LAST_COMBINED=None
 for i in range(100):pilot.guard(out,0,1000,extra=10,custody=lambda:custody.append(1))
 assert calls.count(out)==100 and calls.count(pilot.ROOT)==1 and len(custody)==100;N+=1
 now[0]=104.999;pilot.guard(out,0,1000,custody=lambda:custody.append(1));assert calls.count(pilot.ROOT)==1;N+=1
 now[0]=105.0;pilot.guard(out,0,1000);assert calls.count(pilot.ROOT)==2;N+=1
 # A cached combined scan never skips local/disk/deadline checks.
 with patch.object(pilot,'size',lambda p:pilot.LIMITS['all_output_bytes']+1 if p==out else 1):
  try:pilot.guard(out,0,1000)
  except ValueError:pass
  else:raise AssertionError('local_cap_bypass')
  N+=1
 with patch.object(pilot.shutil,'disk_usage',lambda p:SimpleNamespace(free=pilot.FREE)):
  try:pilot.guard(out,0,1000)
  except ValueError:pass
  else:raise AssertionError('free_floor_bypass')
  N+=1
 try:pilot.guard(out,0,1)
 except TimeoutError:pass
 else:raise AssertionError('clock_bypass')
 N+=1
 now[0]=110
 with patch.object(pilot,'size',lambda p:1000 if p==out else 64000000000):
  try:pilot.guard(out,0,1000)
  except ValueError:pass
  else:raise AssertionError('combined_cap_bypass')
  N+=1
print(json.dumps({'status':'PASS_SYNTHETIC_ACTUAL_GUARD','controls':N,'same_caps':True,'source_or_live_SQL_reads':0}))
