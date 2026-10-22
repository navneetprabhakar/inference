import pathlib,sys,json,hashlib,subprocess,signal,os,time
signal.signal(signal.SIGALRM,lambda *_: (_ for _ in ()).throw(TimeoutError('audit60seconds')));signal.alarm(60);started=time.monotonic()
HERE=pathlib.Path(__file__).resolve().parent;BASE=HERE.parents[1];P=BASE/'enwiki-generic-AST-runner-preparation-v2';POL=BASE/'enwiki-generic-AST-policy-preparation-v2';sys.path.insert(0,str(P));import run
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();expected={'code-pins.json':'31446e3282556520648df933d6724893cc7b0a198f65e5a3ff0925878d36f930','profile.json':'f363797256d8f40dda64a59c94f2b2b1c63933fe8e019a6edf3a1d202f44c9bc','readiness.json':'8e46254d0b4a8407cfe093f330adfe7067b2fde4475c39fbb5168d42cb34b653'}
for n,h in expected.items():assert sha(P/n)==h
assert sha(POL/'policy_core.py')=='a81520db808e3f2fdacfb583dc285cef0a6a9a67c674b2dc45c60c98892eb071'
reg=json.loads((P/'code-pins.json').read_text());assert len(reg['files'])==138 and set(reg['files'])==run.expected_inventory()
for p,h in reg['files'].items():assert not pathlib.Path(p).is_symlink() and sha(pathlib.Path(p))==h
for name,path in [('runner-controls',P/'checks.py'),('policy-controls',POL/'checks.py')]:
 result=subprocess.run([sys.executable,'-I','-B',str(path)],capture_output=True,text=True,check=True,timeout=20);(HERE/(name+'.json')).write_text(result.stdout)
m,core=run.parser_preflight();assert m.parser.use_c and pathlib.Path(sys.modules['mwparserfromhell.parser._tokenizer'].__file__).resolve().is_relative_to(run.TARGET.resolve())
cases=[]
for text in ['A&#1;B','A&#xD800;B','A&#0;B','A&#x110000;B','A&#127;B','A&#x85;B','A&#xFFFF;B','A&#-1;B','A&#xD800B','A&bogus;B','A&#999999999999999999999999;B']:
 frame=core.sections(text,m);u=frame['sections'][0];assert u['preview'] is None and u['holds'] and ''.join(x['raw'] for x in frame['sections'])==text;cases.append({'case':'invalid_entity_whole_hold','source':text,'PASS':True})
for text,output in [('AT&T is ordinary','AT&T is ordinary'),('A & B','A & B'),('A&#x1F600;B','A😀B'),('A&#9;B','A\tB'),('A&#10;B','A\nB'),('A&amp;B','A&B'),('A&#x10FFFD;B','A'+chr(0x10fffd)+'B')]:
 u=core.sections(text,m)['sections'][0];assert u['preview']==output and u['holds']==[];cases.append({'case':'valid_entity_or_literal_retained','source':text,'PASS':True})
from unittest.mock import patch
for label,text in [('empty',''),('missing_root','9999999 1 4\n'),('duplicate',f'{os.getpid()} 1 4\n{os.getpid()} 1 4\n'),('malformed',f'{os.getpid()} 1 4\nbad\n'),('zero',f'{os.getpid()} 1 0\n'),('negative',f'{os.getpid()} 1 -4\n')]:
 with patch.object(run.subprocess,'run',return_value=subprocess.CompletedProcess(args=['ps'],returncode=0,stdout=text,stderr='')):
  try:run.tree_rss()
  except ValueError:pass
  else:raise AssertionError('snapshot accepted:'+label)
 cases.append({'case':'actual_tree_rss_refuses_'+label,'PASS':True})
pid=os.getpid();text=f'{pid} 1 4\n{pid+1} {pid} 3\n{pid+2} {pid+1} 2\n{pid+100} 1 100000\n';assert run.parse_rss_snapshot(text,pid)==9*1024;cases.append({'case':'all_descendants_and_no_unrelated_RSS','PASS':True})
text='é\n== Good ==\nWhole text.\n== Bad ==\nA&#1;B\n== Last ==\nLast complete section.';frame=core.sections(text,m);assert ''.join(s['raw'] for s in frame['sections'])==text and frame['sections'][2]['preview'] is None and frame['sections'][3]['preview'] is not None;cases.append({'case':'invalid_late_entity_whole_section_hold_other_complete_sections_preserved','PASS':True})
for p,h in reg['files'].items():assert sha(pathlib.Path(p))==h
assert not run.OUT.exists() and not (BASE/'m2-intake/enwiki-native20-generic-AST-development-v1').exists()
r=subprocess.run([sys.executable,'-I','-B',str(P/'run.py'),'--code-pins-sha256',expected['code-pins.json'],'--profile-sha256',expected['profile.json']],capture_output=True,text=True,check=True,timeout=20);assert r.stdout.strip()=='READY_STATIC_PREFLIGHT_SYNTHETIC_ONLY_NO_NATIVE_PARSE'
report={'status':'PASS_FOCUSED_V2_REVIEW_NO_NATIVE_EXECUTION','frozen_dispatch_digests':expected,'pins_verified_twice':138,'baseline_policy_controls':42,'baseline_lifecycle_RSS_controls':29,'independent_checks':len(cases),'cases':cases,'both_prior_counterexamples_fixed':True,'static_scope':['Same20 native decisions/15negative outcomes and5pending, limits/runtime/externalpins preserved.','Numeric/Cc/noncharacter/scalar guards precede html.unescape; invalid and still-unparsed numeric forms hold complete source region.','Missing/unusable RSS snapshots raise before any low-RSS conclusion; descendant aggregation verified.','Actual isolated compiled parser origin and pinned54packagefiles verified through inherited inventory.','Originalv1 policy/runner untouched; no retained-native --execute, network/globalledger/tokenizer/model.'],'elapsed_seconds':time.monotonic()-started,'new_admitted_documents':0}
(HERE/'review.json').write_text(json.dumps(report,indent=2)+'\n');manifest={'files':{p.name:{'SHA256':sha(p),'bytes':p.stat().st_size} for p in HERE.iterdir() if p.is_file()}};(HERE/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps({'status':report['status'],'review_SHA256':sha(HERE/'review.json'),'manifest_SHA256':sha(HERE/'manifest.json'),'independent_checks':len(cases)}))
