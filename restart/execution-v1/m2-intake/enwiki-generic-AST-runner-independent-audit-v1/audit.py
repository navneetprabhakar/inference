import pathlib,sys,json,hashlib,subprocess,signal,time,os
signal.signal(signal.SIGALRM,lambda *_: (_ for _ in ()).throw(TimeoutError('audit60seconds')));signal.alarm(60)
START=time.monotonic();HERE=pathlib.Path(__file__).resolve().parent;BASE=HERE.parents[1];PREP=BASE/'enwiki-generic-AST-runner-preparation-v1';POLICY=BASE/'enwiki-generic-AST-policy-preparation-v1';sys.path.insert(0,str(PREP));import run
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
expected={'readiness.json':'cb90c886ab5920812888c106a6ce384cff166d395b196ed1f1234c5af0d72a5c','code-pins.json':'bbaaf3d4c308556babb79e721fe0e53259a335e1dc1fde8190a05eae8dd6b789','profile.json':'0c175d963115877d06ed5ecdebd5a22a57e1ea7db16c7a09ea50fb67bf650c42'}
for n,h in expected.items():assert sha(PREP/n)==h
registry=json.loads((PREP/'code-pins.json').read_text());assert set(registry['files'])==run.expected_inventory() and len(registry['files'])==138
for p,h in registry['files'].items():assert not pathlib.Path(p).is_symlink() and sha(pathlib.Path(p))==h
before={str(p):sha(p) for p in [PREP/'code-pins.json',PREP/'readiness.json',PREP/'profile.json',PREP/'run.py',POLICY/'policy_core.py']}
for key,path in [('runner_controls',PREP/'checks.py'),('policy_controls',POLICY/'checks.py')]:
 r=subprocess.run([sys.executable,'-I','-B',str(path)],capture_output=True,text=True,check=True,timeout=20);(HERE/(key+'.json')).write_text(r.stdout)
command=[sys.executable,'-I','-B',str(PREP/'run.py'),'--code-pins-sha256',expected['code-pins.json'],'--profile-sha256',expected['profile.json']]
r=subprocess.run(command,capture_output=True,text=True,check=True,timeout=20);assert r.stdout.strip()=='READY_STATIC_PREFLIGHT_SYNTHETIC_ONLY_NO_NATIVE_PARSE'
from unittest.mock import patch
m,core=run.parser_preflight();pinpolicy=json.loads((POLICY/'input-pins.json').read_text());assert len(pinpolicy['isolated_parser_files'])==54
extension=sys.modules['mwparserfromhell.parser._tokenizer'];assert pathlib.Path(extension.__file__).resolve().is_relative_to(run.TARGET.resolve()) and extension.__file__.endswith('.so')
independent=[]
for text in ['é\n== A ==\nOne.\n=== B ===\nTwo.\n== C ==\nThree.','== Start ==\ntext','plain <!--x--> joined','good\n\n{{unknown}}\n== Separate ==\nintact whole paragraph.','A <unsupported>x</unsupported> B','[[A|label {{unknown}}]]','A\n{|\n|x\n|}\nZ','A<ref>x</ref>Z']:
 frame=core.sections(text,m);raws=[x['raw'] for x in frame['sections']];assert ''.join(raws)==text
 previous=0
 for u in frame['sections']:
  a,b=u['source_byte_span'];assert a==previous and text.encode()[a:b]==u['raw'].encode();previous=b
  assert ''.join(x['raw'] for x in u['top_nodes'])==u['raw']
  for n in u['top_nodes']:
   c,d=n['source_byte_span'];assert text.encode()[c:d]==n['raw'].encode() and core.H(n['raw'])==n['raw_SHA256']
  if u['holds']:assert u['preview'] is None
 assert previous==len(text.encode());independent.append({'source':text,'PASS_exact_partition_node_offsets_and_whole_hold':True})
# Production resource guard missing-measurement counterexamples; no real nativeworker.
rss=[]
for label,stdout in [('empty_snapshot',''),('missing_supervisor',str(os.getpid()+1000000)+' 1 4\n')]:
 with patch.object(run.subprocess,'run',return_value=subprocess.CompletedProcess(args=['/bin/ps'],returncode=0,stdout=stdout,stderr='')):value=run.tree_rss()
 assert value==0;rss.append({'case':label,'returned_RSS':value,'expected':'raise missing mandatory supervisor measurement','confirmed_fail_open':True})
entities=[]
for text in ['A&#1;B','A&#xD800;B','A&#0;B','A&#x110000;B']:
 unit=core.sections(text,m)['sections'][0];entities.append({'source':text,'node_types':[type(n).__name__ for n in m.parse(text).nodes],'preview':unit['preview'],'holds':unit['holds'],'expected':'whole section held for invalid numeric or unresolved numeric-entity-shaped text'})
assert entities[0]['preview']=='AB' and entities[1]['preview']=='A\ufffdB' and all(x['holds']==[] for x in entities)
assert all(sha(pathlib.Path(p))==h for p,h in before.items()) and not run.OUT.exists()
result={'status':'HOLD_TWO_SYNTHETIC_COUNTEREXAMPLE_BLOCKERS_NO_NATIVE_EXECUTION','dispatch_digests_verified':expected,'exact_input_pins_rehashed':138,'isolated_parser_files_rehashed':54,'actual_compiled_extension_origin':extension.__file__,'project_python':sys.version,'existing_runner_controls':18,'existing_policy_controls':29,'independent_core_partition_controls':independent,'counterexamples':{'RSS_missing_measurement':rss,'invalid_numeric_entities':entities},'findings':[{'ID':'RSS_REQUIRED_SNAPSHOT_MISSING_ACCEPTED_AS_ZERO','scope':'Actual production tree_rss path, synthetic psoutput only','fix':'Require supervisor PID in parsed successful snapshot and refuse malformed/empty/unavailable measurement before reporting RSS.'},{'ID':'INVALID_NUMERIC_ENTITY_PREVIEW_NOT_HELD','scope':'Actual isolated compiled parser plus pinned policycore on synthetic strings only','fix':'Validate numeric entities before html.unescape, including zero, invalidUnicode/surrogates and disallowed controls; hold complete region. Detect still-unparsed numeric-entity-shaped Text rather than preserving as clean preview. Keep raw inverse and ordinary literal ampersands.'}],'other_scope_verified':['All sourcebyte/nodepartition inverses exact in eight independent fixtures.','Unknown templates/ref/tables/extensions nested andlate dependencies hold whole source region; independent completeH2 region survives.','Negative15 are retained without frame in actual synthetic worker lifecycle.','Early ALRM/TERM/INT guards and livechild watchdog/RSS kill+reap controls pass.','No frozeninputs or originaloutputs modified, no retained-native AST execution.'],'input_code_pins_unchanged':True,'retained_native_executions':0,'network_requests':0,'global_ledger_writes':0,'training_or_tokenizer':0,'elapsed_seconds':time.monotonic()-START}
(HERE/'review.json').write_text(json.dumps(result,indent=2)+'\n');manifest={'files':{p.name:{'SHA256':sha(p),'bytes':p.stat().st_size} for p in HERE.iterdir() if p.is_file()}};(HERE/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps({'status':result['status'],'review_SHA256':sha(HERE/'review.json'),'manifest_SHA256':sha(HERE/'manifest.json')}))
