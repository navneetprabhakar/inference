import pathlib,sys,json,tempfile,time,types,ast,hashlib
from unittest.mock import patch
BASE=pathlib.Path('/Users/navneetprabhakar/Documents/git/image/inference/restart/execution-v1');PREP=BASE/'enwiki-native-full-acquisition-preparation-v2';OUT=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(PREP));import archive as a
checks=[]
def refuse(fn,error):
 try:fn()
 except error:return
 raise AssertionError('not_refused')
def no_ledger(*x,**y):raise AssertionError('no_ledger_cleanup_or_child_permitted')
args=types.SimpleNamespace(code_pins_sha256='x',profile_sha256='y')
# Exercise actual existing-output guard after successful mocked pins/TLS imports.
with tempfile.TemporaryDirectory() as td:
 root=pathlib.Path(td);out=root/'existing';out.mkdir();prior=out/'supervisor-result.json';prior.write_bytes(b'IMMUTABLE');before=prior.read_bytes()
 with patch.object(a,'ROOT',root),patch.object(a,'OUT',out),patch.object(a,'verify',return_value={}),patch.object(a,'dependencies',return_value=(no_ledger,None,None)),patch.object(a,'cleanup',no_ledger),patch.object(a.subprocess,'Popen',no_ledger):refuse(lambda:a.supervise(args),ValueError)
 assert prior.read_bytes()==before and list(out.iterdir())==[prior] and not (root/'charges').exists();checks.append('actual_existing_OUT_guard_after_validated_preflight_preserves_allbytes_no_ledger')
# Path traversal for symlink/disk inventory itself can block: watchdog already active.
with tempfile.TemporaryDirectory() as td:
 root=pathlib.Path(td);out=root/'never';real=pathlib.Path.rglob
 def traversal(p,pattern):
  if p==root:time.sleep(2);raise AssertionError('no_alarm')
  return real(p,pattern)
 before={s:a.signal.getsignal(s) for s in [a.signal.SIGTERM,a.signal.SIGINT,a.signal.SIGALRM]};start=a.clk()
 with patch.object(a,'ROOT',root),patch.object(a,'OUT',out),patch.object(a,'EXTERNAL',.04),patch.object(a,'verify',return_value={}),patch.object(a,'dependencies',return_value=(no_ledger,None,None)),patch.object(pathlib.Path,'rglob',traversal),patch.object(a,'cleanup',no_ledger):refuse(lambda:a.supervise(args),RuntimeError)
 assert .02<a.clk()-start<.5 and not out.exists() and not (root/'charges').exists();assert a.signal.getitimer(a.signal.ITIMER_REAL)==(0.,0.) and all(a.signal.getsignal(s)==v for s,v in before.items());checks.append('blocked_symlink_inventory_interrupted_shared_alarm_no_mutations_handlers_restored')
# Setup work consumes the same external clock; never rearmed after each stage.
with tempfile.TemporaryDirectory() as td:
 root=pathlib.Path(td);out=root/'never';events=[]
 def verify(*x):events.append('verify');time.sleep(.02)
 def deps():events.append('TLS');time.sleep(.02);return no_ledger,None,None
 def disk(*x):events.append('disk');time.sleep(2)
 start=a.clk()
 with patch.object(a,'ROOT',root),patch.object(a,'OUT',out),patch.object(a,'EXTERNAL',.07),patch.object(a,'verify',verify),patch.object(a,'dependencies',deps),patch.object(a.shutil,'disk_usage',disk),patch.object(a,'cleanup',no_ledger):refuse(lambda:a.supervise(args),RuntimeError)
 assert events==['verify','TLS','disk'] and .05<a.clk()-start<.2 and not out.exists();checks.append('verify_TLS_elapsed_time_counts_toward_same_deadline_no_reset')
# Precisely scope production drift; every unchanged function body remains identical.
old=ast.parse((BASE/'enwiki-native-full-acquisition-preparation-v1/archive.py').read_text());new=ast.parse((PREP/'archive.py').read_text())
funcs=lambda tree:{n.name:ast.dump(n,include_attributes=False) for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
x,y=funcs(old),funcs(new);assert x.keys()==y.keys() and [n for n in x if x[n]!=y[n]]==['supervise'];checks.append('only_supervise_function_changed_source_stream_TLS_ledger_hash_logic_identical')
oldp=json.loads((BASE/'enwiki-native-full-acquisition-preparation-v1/profile.json').read_text());newp=json.loads((PREP/'profile.json').read_text());assert oldp['limits']==newp['limits'] and oldp['storage']==newp['storage'] and oldp['URL']==newp['URL'] and all(oldp[k]==newp[k] for k in ['expected_bytes','publisher_MD5','publisher_SHA1','transport','publication','forced_stop']);checks.append('all_source_checksums_transport_numerical_storage_caps_unchanged')
pins=json.loads((PREP/'readiness.json').read_text());a.verify(pins['code_pins_SHA256'],pins['profile_SHA256']);a.dependencies();checks.append('actual_external_registry_profile_runtime_import_trust_preflight')
assert hashlib.sha256((PREP/'independent-check-results.json').read_bytes()).hexdigest()==pins['independent_check_results_SHA256'];checks.append('reused_report_script_emitted_byteidentical_original_pinned_report')
result={'status':'PASS_FOCUSED_INDEPENDENT_NO_NETWORK','count':len(checks),'checks':checks,'HTTP_requests':0,'global_ledger_mutations':0,'fullsource_dispatches':0,'note':'Reused independent-checks.py unconditionally rewrote its original report path; content was byte-identical to the preexisting readiness-pinned SHA256, verified here. No other preparation files changed.'}
(OUT/'focused-results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
