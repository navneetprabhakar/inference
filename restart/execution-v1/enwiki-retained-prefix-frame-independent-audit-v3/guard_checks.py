"""Synthetic guard checks only; never actual intake census/source read."""
import sys,json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
S=Path(__file__).resolve().parent.parent/'enwiki-retained-prefix-frame-preparation-v3';sys.path.insert(0,str(S));import pilot
out=Path('/synthetic/own');now=[100.0];events=[]
def census(p):events.append(p);return 300000000 if p==out else 1000000000
def bad_custody():raise ValueError('changed source fixture')
with patch.object(pilot,'clk',lambda:now[0]),patch.object(pilot,'size',census),patch.object(pilot.shutil,'disk_usage',lambda p:SimpleNamespace(free=10**12)):
 pilot.LAST_COMBINED=None;pilot.guard(out,0,1000);base=len(events)
 try:pilot.guard(out,0,1000,custody=bad_custody)
 except ValueError as e:assert str(e)=='changed source fixture'
 else:raise AssertionError('cached combined census bypassed source custody')
 assert len(events)==base+1 # own cap still queried, cached root not rescanned.
 now[0]=104.99;pilot.guard(out,0,1000);assert events.count(pilot.ROOT)==1
 now[0]=105.0;pilot.guard(out,0,1000);assert events.count(pilot.ROOT)==2
 # Budget reserves remaining own allocation against global combined cap.
 now[0]=110.0
 with patch.object(pilot,'size',lambda p:300000000 if p==out else 62000000000):
  try:pilot.guard(out,0,1000)
  except ValueError:pass
  else:raise AssertionError('omitted2.7GB remaining output reserve')
print(json.dumps({'status':'PASS_INDEPENDENT_SYNTHETIC_GUARD','controls':3,'source_custody_even_during_cached_root':True,'exact5second_boundary':True,'remaining_output_reserve_in_global64GB':True,'retained_source_live_SQL_reads':0}))
