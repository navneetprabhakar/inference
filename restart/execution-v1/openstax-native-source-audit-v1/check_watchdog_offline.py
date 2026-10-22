"""Exercise actual supervisor timeout against a sleeping local dummy child only."""
import importlib.util,json,pathlib,subprocess,sys,time
from unittest.mock import patch
D=pathlib.Path(__file__).resolve().parent;S=D.parent/'openstax-native-source-preparation-v1'
spec=importlib.util.spec_from_file_location('review_watchdog',S/'acquire.py');a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
original=subprocess.Popen;launched=[]
def dummy_popen(argv,**kw):
 p=original([sys.executable,'-c','import time; time.sleep(30)'],**kw);launched.append(p);return p
start=time.monotonic();dest=D/'watchdog-dummy-run'
with patch.object(a,'DEST',dest),patch.object(a,'EXTERNAL_SECONDS',.25),patch.object(a.subprocess,'Popen',dummy_popen):
 try:a.execute()
 except SystemExit as e:assert e.code==1
assert len(launched)==1 and launched[0].poll() is not None
r=json.loads((dest/'supervisor-result.json').read_text());assert r['external_timeout'] and r['status']=='FAILED' and r['retry'] is False
out={'status':'PASS_REAL_OFFLINE_DUMMY_PROCESS_TIMEOUT','dummy_children':1,'child_terminated':True,'test_timeout_seconds':.25,'elapsed_seconds':time.monotonic()-start,'production_policy_or_code_modified':False,'actual_acquisition_worker_run':False,'network_requests':0}
(D/'watchdog-check.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
