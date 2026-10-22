import ast,hashlib,json,os,pathlib,sqlite3,subprocess,sys,tempfile,textwrap,time
from unittest.mock import patch
D=pathlib.Path(__file__).resolve().parent;S=D.parent/'wikibooks-language-token-preparation-v1';sys.path.insert(0,str(S));import rules,screen,supervise,code_guard
h=lambda p:hashlib.file_digest(p.open('rb'),'sha256').hexdigest();EXPECTED='956058db22c406408243f347a3b5b8badd315dff87f7216f06b3339fbb64e77a';PROFILE='8f0c7233d2f0af5920e48f0874c1ed94a2e9169191ff26c7f8ecd1499d2b835e';assert h(S/'code-pins.json')==EXPECTED and h(S/'profile.json')==PROFILE and h(S/'readiness.json')=='523567ed78e57da2d2ddd13c18342699d8d79168c34f8bad60aa8996bf43f7c1';code_guard.verify(EXPECTED);inputs={str(p):h(p) for p in S.iterdir() if p.is_file()};profile=json.loads((S/'profile.json').read_text());assert profile['runtime']==screen.runtime();cases=[]
for item in profile['inputs']:assert h(pathlib.Path(item['path']))==item['sha256']
cases.append('all_exact_source_detector_tokenizer_review_and_runtime_pins_verified')
base=subprocess.run([sys.executable,str(S/'check_rules.py')],capture_output=True,text=True,check=True,timeout=60);(D/'baseline-controls.json').write_text(base.stdout);assert json.loads(base.stdout)['passed']==12
# Exercise exact production nested flush with only its transport/guard supplied
# by a tiny synthetic closure. No corpus rows or language model training.
source=(S/'screen.py').read_text();run=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='run');flush=next(n for n in ast.walk(run) if isinstance(n,ast.FunctionDef) and n.name=='flush');flush_source=textwrap.dedent(ast.get_source_segment(source,flush));ddl=next(n.args[0].value for n in ast.walk(run) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='executescript')
text1='a'*1024+'b'*40;text2='c'*39;tokenizer=rules.load_tokenizer(profile);batch=[]
for ordinal,text in enumerate([text1,text2],1):
 prepared=[]
 for meta,chunk in rules.windows(text):
  projected=rules.projection(chunk).encode();meta.update(raw_sha256=hashlib.sha256(chunk.encode()).digest(),projection_sha256=hashlib.sha256(projected).digest());prepared.append((meta,projected))
 batch.append({'ordinal':ordinal,'identity':(ordinal,ordinal+100,'one-family','synthetic',hashlib.sha256(text.encode()).hexdigest(),len(text),len(text.encode())),'tokens':len(tokenizer.encode(text,add_special_tokens=False).ids),'windows':prepared,'expected_scored':sum(m['scored'] for m,_ in prepared)})
prefix="""def fixture(batch,predictions):
 projection_bytes=0
 db=sqlite3.connect(':memory:');db.executescript(DDL)
 stats={'documents':0,'source_UTF8_bytes':0,'content_tokens':0,'scored_lines':0,'skipped_chunks':0,'all_windows':0,'batches':0}
 known={2:{'synthetic_known_hold':True}};profile={};start=clk();captured=[]
 def guard(extra=0):pass
 def infer(profile,data,remaining):captured.append(data);return predictions
"""
namespace={'sqlite3':sqlite3,'DDL':ddl,'rules':rules,'CAPS':screen.CAPS,'clk':screen.clk,'json':json};exec(prefix+textwrap.indent(flush_source,' ')+"\n flush()\n return db,stats,captured\n",namespace);fixture=namespace['fixture'];predictions=['__label__en 0.95','__label__en 0.9','__label__en 0.79','__label__en 0.92'];db,stats,captured=fixture(batch,predictions)
assert len(captured)==1 and len(captured[0].splitlines())==4;assert stats['documents']==2 and stats['scored_lines']==4 and stats['skipped_chunks']==1 and stats['all_windows']==5
assert db.execute('select source_ordinal,language_pass,known_discovery_hold from docs order by source_ordinal').fetchall()==[(1,0,0),(2,1,1)]
assert db.execute('select start,end,english_probability,policy_pass from windows where source_ordinal=1 and ordinal=2').fetchone()==(1024,1064,.79,0);cases.append('actual_flush_preserves_low_probability_eligible_short_tail_failure')
assert db.execute('select scored,skip_reason,label,raw_probability,policy_pass from windows where source_ordinal=2 and ordinal=1').fetchone()==(0,'fewer_than_40_alphabetic_characters',None,None,None);cases.append('actual_flush_exact_scored_and_explicit_skipped_line_coverage')
for ordinal,tokens,with_eos in db.execute('select source_ordinal,content_tokens,tokens_plus_one_EOS from docs'):assert tokens==batch[ordinal-1]['tokens'] and with_eos==tokens+1
assert 'text' not in [x[1] for x in db.execute('pragma table_info(docs)')];cases.append('actual_flush_pinned_content_counts_and_separate_single_EOS_no_fulltext_duplication')
assert json.loads(db.execute('select holds from docs where source_ordinal=2').fetchone()[0])==['known_discovery_review_hold_or_exclusion'];db.close();cases.append('actual_flush_known_review_hold_survives_raw_language_pass')
for malformed in [predictions[:-1],predictions+['__label__en 1.0']]:
 try:fixture(batch,malformed)
 except RuntimeError as e:assert str(e)=='classifier_window_line_count_mismatch'
 else:raise AssertionError('Classifier coverage mismatch accepted')
cases.append('actual_flush_missing_and_extra_classifier_predictions_refused')
# New registry/CLI flow cannot mutate outputs before wrong digest rejection.
with tempfile.TemporaryDirectory() as td:
 p=pathlib.Path(td);(p/'code-pins.json').write_text(json.dumps({'sha256':{}}))
 for digest in [EXPECTED,h(p/'code-pins.json')]:
  try:code_guard.verify(digest,p)
  except ValueError:pass
  else:raise AssertionError('Empty inventory accepted')
cases.append('external_registry_and_exact_inventory_original_exploit_refused')
with tempfile.TemporaryDirectory() as td:
 p=pathlib.Path(td)/'never-created'
 try:supervise.run(S/'profile.json',p,'0'*64,PROFILE)
 except ValueError:assert not p.exists()
 else:raise AssertionError('wrong code pin accepted')
cases.append('supervisor_code_pin_refusal_before_output')
with patch.object(sys,'argv',['screen','--profile',str(S/'profile.json'),'--profile-sha256',PROFILE,'--output','x','--start-shared-monotonic','1','--supervisor-pid','1','--code-pins-sha256','0'*64]),patch.object(screen,'run',side_effect=AssertionError('Must not run')):
 try:screen.main()
 except ValueError:pass
 else:raise AssertionError('worker wrong code pin accepted')
cases.append('worker_code_pin_refusal_before_mutation')
# Exact frozen cohort counts from finalized metadata only; no source text pass.
f=sqlite3.connect(pathlib.Path(profile['finalizer']['path']).as_uri()+'?mode=ro',uri=True);assert f.execute("select count(*),sum(p.utf8_bytes) from pages p join final_pages f on f.source_ordinal=p.source_ordinal where f.holds='[]'").fetchone()==(27585,111989353);known=json.loads(pathlib.Path(profile['discovery_holds']['path']).read_text())['records'];assert len(known)==20 and sum(x['post_finalizer_candidate'] for x in known)==6
for x in known:assert f.execute('select text_sha256 from pages where source_ordinal=?',(x['source_ordinal'],)).fetchone()[0]==x['text_sha256']
f.close();cases.append('actual_frozen_cohort_denominator_and_twenty_review_identities_six_candidate_holds')
assert all(h(pathlib.Path(n))==v for n,v in inputs.items());code_guard.verify(EXPECTED);result={'status':'PASS_FOCUSED_LANGUAGE_TOKEN_PREPARATION_NO_CONFIRMED_BLOCKER','codepins_SHA256':EXPECTED,'profile_SHA256':PROFILE,'readiness_SHA256':inputs[str(S/'readiness.json')],'baseline_controls':12,'independent_cases':cases,'exact_production_flush_lifted_without_body_changes':True,'no_actual_corpus_text_pass':True,'all_source_and_preparation_inputs_unchanged':True,'input_SHA256':inputs,'scope':'Language gate is whole plus1024Unicodechunks >=40alphabetics including eligible tails; scores and skips preserved. Raw language pass, known-review holds and eventual acceptance remain distinct. Counts are provisional M1content plusEOS only, no fitting/training.','network_requests':0,'training_operations':0};(D/'review.json').write_text(json.dumps(result,indent=2)+'\n');(D/'manifest.json').write_text(json.dumps({p.name:h(p) for p in D.iterdir() if p.is_file() and p.name!='manifest.json'},indent=2)+'\n');print(json.dumps({'status':result['status'],'baseline_controls':12,'independent_cases':len(cases),'manifest_SHA256':h(D/'manifest.json')}))
