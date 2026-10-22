"""Exact v3 static binding and actual terminal gate probes, synthetic files only."""
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
import hashlib,json,os,sys,tempfile,copy,signal
import runner,core
N=0
P='dd697043d80eef1e49178d76b2ad527655f6e9449815cf502eb11fe010f89d91'
C='db0ac3c36a72384459b15d9645f8c0494645795408a47057e4f7085b40cce9ac'
def must(fn):
 global N
 try:fn()
 except Exception:N+=1;return
 raise AssertionError('refusal expected')
with tempfile.TemporaryDirectory() as t:
 root=Path(t);profile={'producer_profile_SHA256':P,'producer_codepins_SHA256':C,'limits':{'worker_seconds':3600,'external_seconds':3660,'RSS_bytes':1000000000,'output_bytes':16000000},'python':str(Path(sys.executable).resolve()),'input_paths':[]}
 for f in ['core.py','runner.py','checks.py','focused_checks.py','contract.json','binding-template.json']:(root/f).write_text('synthetic bounded metadata')
 def install(p):
  (root/'profile.json').write_text(json.dumps(p));pins={str(root/f):runner.sha(root/f) for f in ['core.py','runner.py','checks.py','focused_checks.py','profile.json','contract.json','binding-template.json']};(root/'code-pins.json').write_text(json.dumps({'SHA256':pins}));return SimpleNamespace(profile_sha256=runner.sha(root/'profile.json'),code_pins_sha256=runner.sha(root/'code-pins.json'))
 with patch.object(runner,'HERE',root):
  a=install(profile);assert runner.verify(a)['producer_profile_SHA256']==P;N+=1
  bad=copy.deepcopy(profile);bad['producer_profile_SHA256']='51723b60b60c23c9894bb0c92778513a5e7df5315fcb01f09e79683201b6ba8a';a=install(bad);must(lambda:runner.verify(a))
  bad=copy.deepcopy(profile);bad['producer_codepins_SHA256']='86a08a0ea827163bc3607c8df34307036eae82acc8c173d5a69327ec68973885';a=install(bad);must(lambda:runner.verify(a))
 folder=root/'producer';folder.mkdir();p={'producer_output':str(folder),'producer_profile_SHA256':P,'producer_codepins_SHA256':C}
 required=['frame.sqlite','original-header.xml','header-receipt.json','codec.json','header-summary.json','group-receipts.jsonl','exceptions.jsonl','result.json','supervisor.json','ownership.json']
 for name in required:(folder/name).write_text('{}')
 own={'worker_PID':112233,'supervisor_PID':112234,'profile_SHA256':P,'codepins_SHA256':C};(folder/'ownership.json').write_text(json.dumps(own))
 result={'status':'COMPLETE_RETAINED_PREFIX_FRAGMENT_FRAME_NO_ADMISSION','profile_SHA256':P,'codepins_SHA256':C,'whole_publisher_archive_verified':False};(folder/'result.json').write_text(json.dumps(result))
 sup={'status':'COMPLETE_RETAINED_PREFIX_FRAGMENT_NO_ADMISSION','worker_exit_code':0,'result_SHA256':runner.sha(folder/'result.json')};(folder/'supervisor.json').write_text(json.dumps(sup))
 binding={'status':'PARENT_REVIEWED_COMPLETE_TERMINAL_METADATA_BINDING','producer_reaped':True,'producer_exec_exit_code':0,'producer_owned_PIDs_absent':True,'producer_profile_SHA256':P,'producer_codepins_SHA256':C,'files':{n:{'stat':runner.ident(folder/n),'SHA256':runner.sha(folder/n)} for n in required}}
 bp=root/'binding.json'
 def args(b):bp.write_text(json.dumps(b));return SimpleNamespace(binding=str(bp),binding_sha256=runner.sha(bp))
 def absent(*a):raise ProcessLookupError
 with patch.object(runner.os,'kill',absent):
  assert runner.bound(args(binding),p)[1]==result;N+=1
  for field,value in [('producer_reaped',False),('producer_exec_exit_code',1),('producer_owned_PIDs_absent',False),('producer_profile_SHA256','x'*64),('producer_codepins_SHA256','x'*64)]:
   bad=copy.deepcopy(binding);bad[field]=value;must(lambda bad=bad:runner.bound(args(bad),p))
 with patch.object(runner.os,'kill',lambda *a:None):must(lambda:runner.bound(args(binding),p))
 with patch.object(runner.os,'kill',absent):
  (folder/'codec.json').write_text('{"changed":true}');must(lambda:runner.bound(args(binding),p))
 signal.setitimer(signal.ITIMER_REAL,0)
print(json.dumps({'status':'PASS_FOCUSED_V3_BINDING_SYNTHETIC_ONLY','controls':N,'producer_or_live_SQL_reads':0,'source_body_reads':0}))
