import json,pathlib,tempfile,subprocess,sys,os,hashlib
from unittest.mock import patch
import supervise as s
import code_guard as g
checks=[]
assert s.decision(895,0,0,10**12)=='elapsed_time_cap_cleanup_reserve';checks.append('900second_deadline_contains5second_cleanup_reserve')
assert s.decision(0,1_000_000_001,0,10**12)=='observed_process_tree_RSS_cap';checks.append('1GB_process_tree_RSS')
assert s.decision(0,0,1_000_000_000-s.f.TERMINAL+1,10**12)=='output_byte_cap';checks.append('output_reserves_terminal_slot')
assert s.decision(0,0,0,s.f.CAPS['free_floor_bytes']+s.f.CAPS['weights_bytes']-1)=='free_floor_weights_reserve';checks.append('weights_and_free_floor')
assert s.tree('1 0 10\n2 1 20\n3 2 30\n4 0 40',1)==60*1024;checks.append('whole_descendant_RSS')
p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'],start_new_session=True)
try:s.kill(p);assert p.poll() is not None;checks.append('actual_separate_session_terminated_and_reaped')
finally:
 if p.poll() is None:p.kill();p.wait()
with tempfile.TemporaryDirectory() as td:
 p=pathlib.Path(td)
 for name in g.REQUIRED:(p/name).write_text('fixture '+name)
 registry=p/'code-pins.json';registry.write_text(json.dumps({'sha256':{name:g.sha(p/name) for name in g.REQUIRED}}));pin=g.sha(registry);g.verify(pin,p);checks.append('explicit_external_registry_exact_inventory')
 for name,data in [('empty',{}),('missing',{n:g.sha(p/n) for n in g.REQUIRED if n!='finalize.py'}),('extra',dict({n:g.sha(p/n) for n in g.REQUIRED},extra='0'*64))]:
  registry.write_text(json.dumps({'sha256':data}))
  try:g.verify(g.sha(registry),p)
  except ValueError:checks.append(name+'_registry_rejected')
  else:raise AssertionError(name)
 try:g.verify('0'*64,p)
 except ValueError:checks.append('wrong_external_registry_digest')
 else:raise AssertionError('digest')
 with patch.object(g,'verify',side_effect=ValueError('pin')):
  try:s.run(p/'absent',p/'must-not-exist','0'*64,'0'*64)
  except ValueError:assert not (p/'must-not-exist').exists();checks.append('supervisor_guard_before_output')
  else:raise AssertionError('guard')
print(json.dumps({'passed':len(checks),'checks':checks},indent=2))
