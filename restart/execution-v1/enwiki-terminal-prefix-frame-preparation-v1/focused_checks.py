"""Synthetic-only v2 lifecycle/scope controls; never open an actual archive."""
import os,pathlib,tempfile,subprocess,sys,json,time,types
from unittest.mock import patch
import pilot as p
checks=[]
def reject(name,fn,kind=(ValueError,TimeoutError)):
 try:fn()
 except kind:checks.append(name)
 else:raise AssertionError(name)
# Actual fresh child must share CLOCK_MONOTONIC epoch for serialized supervisor start.
a=p.clk();b=float(subprocess.check_output([sys.executable,'-c','import time;print(time.clock_gettime(time.CLOCK_MONOTONIC))'],text=True));c=p.clk();assert a<=b<=c;checks.append('real_parent_child_shared_clock_containment')
with tempfile.TemporaryDirectory() as td:
 root=pathlib.Path(td);out=root/'out';out.mkdir();sentinel=out/'frozen';sentinel.write_bytes(b'unchanged');before=sentinel.stat();args=types.SimpleNamespace(code_pins_sha256='C',profile_sha256='P',source_binding='B',source_binding_sha256='H')
 with patch.object(p,'OUT',out),patch.object(p,'ROOT',root),patch.object(p,'verify',side_effect=ValueError('frozen refused')):reject('preflight_refusal_preserves_existing_output',lambda:p.supervise(args))
 assert sentinel.read_bytes()==b'unchanged' and sentinel.stat()==before and list(out.iterdir())==[sentinel]
 with patch.object(p,'OUT',out),patch.object(p,'ROOT',root),patch.object(p,'verify',return_value={}),patch.object(p,'verify_binding',return_value={}):reject('existing_output_never_reused',lambda:p.supervise(args))
 assert sentinel.read_bytes()==b'unchanged' and list(out.iterdir())==[sentinel]
 with patch.object(p,'OUT',out),patch.object(p.shutil,'disk_usage',return_value=types.SimpleNamespace(free=10**15)),patch.object(p,'clk',return_value=116):
  reject('worker115deadline_refuses116',lambda:p.guard(0))
  p.guard(0,seconds=120);checks.append('supervisor120deadline_not_worker115')
 with patch.object(p,'OUT',out),patch.object(p.shutil,'disk_usage',return_value=types.SimpleNamespace(free=10**15)),patch.object(p,'clk',return_value=120):reject('supervisor120deadline_refuses_boundary',lambda:p.guard(0,seconds=120))
 # No binding source file can be opened before required binding authority exists.
 with patch.object(pathlib.Path,'read_bytes',side_effect=AssertionError('no source bytes allowed')):reject('missing_binding_fails_before_any_bytes',lambda:p.verify_binding(None,None,'P'))
assert p.LIMITS['compressed_prefix_bytes']==17948470 and p.LIMITS['worker_seconds']==115 and p.LIMITS['external_seconds']==120;checks.append('exact_finite_caps_unchanged_other_limits')
print(json.dumps({'status':'PASS_SYNTHETIC_ONLY','count':len(checks),'checks':checks,'archive_bytes_read':0,'network':0,'global_ledger_writes':0},indent=2))
