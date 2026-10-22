import sys,pathlib,json,hashlib,subprocess,importlib.util,random,sqlite3
B=pathlib.Path('/Users/navneetprabhakar/Documents/git/image/inference/restart/execution-v1');H=B/'gutenberg-four-custody-preparation-v3';O=B/'gutenberg-four-custody-audit-v3';sys.path.insert(0,str(H));import audit,checks,adapter_cases,memory_cases
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
results={}
for name,module in [('core',checks),('adapters',adapter_cases),('memory',memory_cases)]:results[name]=module.run()
results['lifecycle']=[]
for c in ['deadline','term','int','slot-setup-failure']:
 r=subprocess.run([sys.executable,str(H/'lifecycle_cases.py'),'--case',c],capture_output=True,check=True,text=True,timeout=10);results['lifecycle'].append(json.loads(r.stdout))
code='9ce0b186157e34694cab52236e45eb7b02c2a54677272574a7f9c4d0cb9558c5';profile='c3361e0da5aedabc9428ee97aea22928637b0a82b38fdf76a4b050f642232768'
assert sha(H/'code-pins.json')==code and sha(H/'profile.json')==profile
# Independently exercise actual entry point without --execute; verifies all819 pins and exact retained adapter inventory, not source-body pass.
r=subprocess.run([sys.executable,str(H/'audit.py'),'--code-pins-sha256',code,'--profile-sha256',profile],capture_output=True,text=True,timeout=90,check=True);assert r.stdout.strip()=='READY_NO_SCAN';results['actual_nonexecuting_entrypoint']=r.stdout.strip()
spec=importlib.util.spec_from_file_location('core_v2',B/'gutenberg-four-custody-preparation-v2/overlap_core.py');v2=importlib.util.module_from_spec(spec);spec.loader.exec_module(v2)
rng=random.Random(910234);universe=['t'+str(i) for i in range(40)];assertions=0
for _ in range(300):
 texts=[' '.join(rng.choice(universe) for _ in range(rng.randrange(0,100))) for _ in range(4)];old=v2.Index(texts);new=audit.core.Index(texts)
 for text in texts+[' '.join(rng.choice(universe) for _ in range(rng.randrange(0,350)))]:assert old.compare(text)==new.compare(text);assertions+=1
results['independent_full_v2_vs_v3_matcher_cases']=assertions
# Exact source adapter entries, required scopes and candidate identity unchanged.
assert json.loads((H/'body-sources.json').read_text())==json.loads((B/'gutenberg-four-custody-preparation-v2/body-sources.json').read_text())
assert (H/'candidates.json').read_bytes()==(B/'gutenberg-four-custody-preparation-v2/candidates.json').read_bytes();results['unchanged_all_adapters_and_candidates']=True
# Hold lookup query must be indexed; a query-plan check does not scan actual bodies.
p=B/'m2-intake/wikibooks-global-finalization-v3/finalized.sqlite3';db=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True)
sql='select p.page_id,p.revision_id,p.family,p.text_sha256,p.holds,p.active,f.holds from pages p join final_pages f on p.source_ordinal=f.source_ordinal where p.source_ordinal=?';plan=[list(x) for x in db.execute('explain query plan '+sql,(7,))];db.close();assert all('SEARCH' in x[3] for x in plan);results['actual_Wikibooks_indexed_query_plan']=plan
# Protected ancestor priority is independent from role data container implementation.
assert audit.core.disposition(True,True)=='PROTECTED_FAMILY_HOLD';assert audit.core.legacy_role(True,'development')=='current_development';results['protected_priority_and_eval_roles_preserved']=True
# Existing frozen output must not be modified by actual supervisor preflight refusal.
import tempfile,types
from unittest.mock import patch
with tempfile.TemporaryDirectory() as td:
 out=pathlib.Path(td)/'frozen';out.mkdir();f=out/'keep';f.write_bytes(b'original')
 with patch.object(audit,'OUT',out),patch.object(audit,'verify',side_effect=ValueError('synthetic_refusal')):
  try:audit.supervise(types.SimpleNamespace(code_pins_sha256=code,profile_sha256=profile))
  except ValueError:pass
  else:raise AssertionError('missing refusal')
 assert list(out.iterdir())==[f] and f.read_bytes()==b'original'
results['actual_supervisor_existing_output_preserved']=True
(O/'controls.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps({'status':'PASS_INDEPENDENT_NO_CORPUS_SCAN','full_matcher_cases':assertions,'controls_sha256':sha(O/'controls.json')}))
