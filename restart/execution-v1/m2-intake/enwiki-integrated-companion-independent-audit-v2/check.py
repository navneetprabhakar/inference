from pathlib import Path
import sys,json,hashlib,subprocess
B=Path(__file__).resolve().parents[2];P=B/'enwiki-integrated-companion-preparation-v2';O=Path(__file__).resolve().parent
H=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
expected={'code-pins.json':'27f9bee4ce57ea7ee4bfc981f549abe6c7545e60da7679a87922d6ba6eb1b4b0','profile.json':'9438114c10b5f45caed25f3f3a7d1feb5b06c142cc1084acfa3ea77209ba19d2','readiness.json':'0eed03c33a6106db9b5a066f0a46132325fbebfe3b5987e53ee2ccb92767b712','manifest.json':'f60ec6d07f1808197a184fda6dd8739ec99092da1229cd0a78ee396c5d15b2cb'}
for f,h in expected.items():assert H(P/f)==h
for f,h in json.loads((P/'manifest.json').read_text())['files'].items():assert H(P/f)==h
pins=json.loads((P/'code-pins.json').read_text())['files']
for f,h in pins.items():assert H(Path(f))==h
sys.path[:0]=[str(P),str(B/'tool-dependencies/mwparserfromhell-0.7.2'),str(B/'enwiki-generic-AST-policy-preparation-v4'),str(B/'enwiki-page-local-reference-preparation-v1'),str(B/'enwiki-structural-companion-policy-preparation-v1')]
import integrated_core as c,mwparserfromhell as m,policy_core as l,reference_core as r,rules
cases=[]
for s in ['X[[file:A.png]]Y','X[[category:Example]]Y','[[ File:A.png]]','[[:File:A.png]]','[[FILE :A.png]]','[[File_:A.png]]','[[File: A.png]]','[[MODULE:X]]','[[:Unknown:X]]','A<ref name="x">A</ref>\n== B ==\nB<ref name="x">B</ref>']:
 q=c.develop_page(s,m,l,r,rules);assert all(x['provisional_prose_preview'] is None for x in q['sections']);cases.append({'source':s,'held':True})
for s in ['[[file:A.png|Caption {{unknown}}]]','[[cAtEgOrY:History]]']:
 q=c.develop_page(s,m,l,r,rules);assert q['sections'][0]['semantic_companion_holds'];assert q['exact_raw_metadata_companions'][0]['raw']==s;cases.append({'source':s,'raw_companion_and_hold':True})
s='Read [[The Real North Korea: Life and Politics]].';q=c.develop_page(s,m,l,r,rules);assert q['sections'][0]['provisional_prose_preview']=='Read The Real North Korea: Life and Politics.';cases.append({'source':s,'literal_booktitle_preserved':True})
results={}
for script in ['core_checks.py','checks.py']:
 z=subprocess.run([sys.executable,'-I','-B',str(P/script)],capture_output=True,text=True,timeout=20);assert z.returncode==0,(z.stdout,z.stderr);v=json.loads(z.stdout);results[script]=v;(O/(script+'.result.json')).write_text(json.dumps(v,indent=2)+'\n')
z=subprocess.run([sys.executable,'-I','-B',str(P/'run.py'),'--code-pins-sha256',expected['code-pins.json'],'--profile-sha256',expected['profile.json']],capture_output=True,text=True,timeout=20);assert z.returncode==0 and 'READY_STATIC_PREFLIGHT' in z.stdout
x={'status':'PASS_INDEPENDENT_SYNTHETIC_AND_STATIC_ONLY_NO_SAVED_SOURCE_APPLICATION','preparation':str(P),'reviewed_top_pins':expected,'all_manifest_and_registry_pins_verified':True,'registry_count':len(pins),'reproduced_core_controls':results['core_checks.py']['checks'],'reproduced_actual_runner_controls':results['checks.py']['checks'],'independent_cases':cases,'static_preflight':z.stdout.strip(),'review_findings':'Parent namespace bypass fixed narrowly; literal book-title colons retained. No further concrete blocker in full core and production diff review. Metadata semantic values retained as unrendered companions with separate independence holds; ref holds always win; unknown/table semantics yield whole-region hold. No template execution or strip_code.','preserved_limitations':['Immutable reference v1 opaque-reference context guard conservatively holds all page bindings, potentially overholding legitimate independent reference sections; reported not missing-definition proof.','Prose previews remain provisional with semantic-companion/source/factual/rights/language/leakage gates; zero admission.'],'runtime_limits':'Same60external55worker/5MB/1GB; early preflight alarm, no-overwrite, pin propagation, kill/reap synthetic controls reproduced.','new_native_policy_applications':0}
(O/'review.json').write_text(json.dumps(x,indent=2)+'\n');(O/'manifest.json').write_text(json.dumps({'files':{p.name:H(p) for p in O.iterdir() if p.is_file() and p.name!='manifest.json'}},indent=2)+'\n');print('review',H(O/'review.json'));print('manifest',H(O/'manifest.json'))
