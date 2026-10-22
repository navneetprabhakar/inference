import hashlib,json,os,pathlib,sqlite3,subprocess,sys,tempfile
from unittest.mock import patch
D=pathlib.Path(__file__).resolve().parent;S=D.parent/'wikibooks-residual-render-preparation-v2';V1=S.with_name('wikibooks-residual-render-preparation-v1');sys.path.insert(0,str(S));import launch as j;import code_guard as g;import profile as p;import supervisor as s;import render_shard as r
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();EXPECTED='e080aba6067325530745bf06610dec8d5e5c64c40d711b220a7aaa41762a2e66';assert h(S/'code-pins.json')==EXPECTED and h(S/'readiness.json')=='71346ca09d2aed933f2cc731d5331ea877a8be64b4b557e0d065ec902d3afb87';inputs={str(x):h(x) for x in S.iterdir() if x.is_file()};g.verify(EXPECTED);cases=[]
def refuse(fn):
 try:fn()
 except ValueError:return
 raise AssertionError('expected refusal')
assert len(g.REQUIRED)==16 and (S/'effective-inputs.json').read_bytes()==(V1/'effective-inputs.json').read_bytes();cases.append('exact16_inventory_and_unchanged_effective_profile')
for name in ['profile.py','aggregate.py','extraction_core.py','dom_renderer.py','shared_clock.py','baseline-v3-holds.json']:assert (S/name).read_bytes()==(V1/name).read_bytes()
assert j.GLOBAL_SECONDS==930 and j.GLOBAL_RSS==4000000000 and j.rc.CAPS['seconds']==900 and j.rc.CAPS['output_bytes']==1000000000;cases.append('source_selection_renderer_reservations_and_caps_unchanged')
with tempfile.TemporaryDirectory() as td:
 t=pathlib.Path(td);(t/'code-pins.json').write_text(json.dumps({'sha256':{}}));refuse(lambda:g.verify(EXPECTED,t));refuse(lambda:g.verify(h(t/'code-pins.json'),t));cases.append('original_empty_registry_exploit_refused_with_original_and_recomputed_digest')
with patch.dict(os.environ,{'WIKIBOOKS_CODE_PINS_SHA256':'0'*64}):
 refuse(j.verify_pins);refuse(j.rc.check_pins);cases.append('root_and_inherited_child_reject_wrong_external_digest')
with tempfile.TemporaryDirectory() as td,patch.object(j,'ROOT',pathlib.Path(td)/'never-created'):
 refuse(lambda:j.run(S/'effective-inputs.json',h(S/'effective-inputs.json'),'0'*64));assert not j.ROOT.exists();cases.append('root_refuses_before_first_mutation')
for module,argv,target in [(s,['supervisor','--archive','x','--output','x','--shard','1','--code-pins-sha256','0'*64],'supervise'),(r,['worker','--archive','x','--output','x','--shard','1','--supervisor-pid','1','--start-monotonic','1','--code-pins-sha256','0'*64],'render')]:
 with patch.object(sys,'argv',argv),patch.object(module,target,side_effect=AssertionError('must not mutate')):refuse(module.main)
 cases.append(target+'_CLI_digest_refusal_before_mutation')
with patch.dict(os.environ,{'WIKIBOOKS_CODE_PINS_SHA256':EXPECTED,'WIKIBOOKS_EFFECTIVE_PROFILE':str(S/'effective-inputs.json'),'WIKIBOOKS_EFFECTIVE_PROFILE_SHA256':h(S/'effective-inputs.json')}):
 actual=p.load();assert len(actual['jobs_loaded'])==8;cases.append('actual_effective_source_and_supplement_pins_still_validate')
 # Capture exact attempted supervisor and worker argv, aborting before process creation.
 captured=[]
 def intercept(cmd,**kwargs):captured.append(cmd);raise RuntimeError('OFFLINE_CAPTURE_STOP')
 with tempfile.TemporaryDirectory() as td,patch.object(j,'ROOT',pathlib.Path(td)),patch.object(j.subprocess,'Popen',side_effect=intercept):
  try:j.run_wave(1,j.shared_clock())
  except RuntimeError as error:assert str(error)=='OFFLINE_CAPTURE_STOP'
 assert captured[-1][-2:]==['--code-pins-sha256',EXPECTED];cases.append('actual_launcher_Popen_argv_forwards_parent_digest_no_process_created')
 with tempfile.TemporaryDirectory() as td,patch.object(s.aggregate,'reserve',return_value={}),patch.object(s.aggregate,'finish',return_value=None),patch.object(s,'check_processed_reservation',return_value=None),patch.object(s.subprocess,'Popen',side_effect=intercept):
  out=pathlib.Path(td)/'output'
  try:s.supervise(pathlib.Path('fixture'),out,1)
  except RuntimeError as error:assert str(error)=='OFFLINE_CAPTURE_STOP'
 assert captured[-1][-2:]==['--code-pins-sha256',EXPECTED];cases.append('actual_supervisor_Popen_argv_forwards_same_digest_no_process_created')
# Run narrow changed-path guard and inherited residual controls; no old process audit repeated.
counts={}
for name in ['check_code_guard.py','check_profile.py','check_worker.py']:
 runner="import sys;sys.path.insert(0,"+repr(str(S))+");exec(compile(open("+repr(str(S/name))+",'rb').read(),"+repr(str(S/name))+",'exec'),{'__name__':'__main__','__file__':"+repr(str(S/name))+"})"
 out=subprocess.run([sys.executable,'-c',runner],capture_output=True,text=True,check=True,timeout=60);(D/(name+'.stdout')).write_text(out.stdout);counts[name]=json.loads(out.stdout)['passed']
assert counts=={'check_code_guard.py':14,'check_profile.py':16,'check_worker.py':10};assert all(h(pathlib.Path(n))==v for n,v in inputs.items());result={'status':'PASS_FOCUSED_REVIEW_PRIOR_BLOCKER_FIXED_NO_NEW_CONFIRMED_ISSUE','external_codepins_SHA256':EXPECTED,'readiness_SHA256':inputs[str(S/'readiness.json')],'effective_profile_SHA256':inputs[str(S/'effective-inputs.json')],'independent_cases':cases,'narrow_controls':counts,'prior11_process_cleanup_controls_reused_not_repeated':True,'source_and_policy_drift':False,'preparation_inputs_unchanged':True,'input_SHA256':inputs,'no_actual_residual_process_created':True,'network_requests':0,'global_ledger_writes':0};(D/'review.json').write_text(json.dumps(result,indent=2)+'\n');(D/'manifest.json').write_text(json.dumps({x.name:h(x) for x in D.iterdir() if x.is_file() and x.name!='manifest.json'},indent=2)+'\n');print(json.dumps({'status':result['status'],'independent_cases':len(cases),'narrow_controls':counts,'manifest_SHA256':h(D/'manifest.json')}))
