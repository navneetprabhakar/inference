"""Synthetic adapters and extracted role-classification controls, never corpus scan."""
import pathlib,sys,tempfile,json,sqlite3,time,types,ast,collections,signal
from unittest.mock import patch
BASE=pathlib.Path('/Users/navneetprabhakar/Documents/git/image/inference/restart/execution-v1');P=BASE/'gutenberg-four-custody-preparation-v1';OUT=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(P));import sources,overlap_core as core,audit
results=[]
# A required body record is silently converted into no observation, no hold.
for name,obj in [('missing_body',{'source_id':'required-body','body':'meaningful candidate prose lives under unsupported schema'}),('null_text',{'source_id':'required-body','text':None}),('metadata_reference_only',{'file':'chapter01.txt','sha256':'registry-bound-elsewhere'})]:
 with tempfile.TemporaryDirectory() as t:
  p=pathlib.Path(t)/'candidates.jsonl';p.write_text(json.dumps(obj)+'\n');e={'path':str(p),'adapter':'jsonl_text_fields','required_current_candidate_body_coverage':True,'coverage_role':'CURRENT_OR_RETAINED_CANDIDATE_BODY'};observed=list(sources.stream(e,lambda:None));assert observed==[]
  results.append({'case':'required_JSONL_'+name,'yielded_observations':0,'yielded_coverage_holds':0,'record_count_in_file':1})
with tempfile.TemporaryDirectory() as t:
 p=pathlib.Path(t)/'rendered.sqlite3';db=sqlite3.connect(p);db.execute('create table rendered (data text)');db.execute('insert into rendered values (?)',(json.dumps({'text':None,'status':'expected body record'}),));db.commit();db.close();e={'path':str(p),'adapter':'sqlite_json_data','table':'rendered','columns':['data'],'required_current_candidate_body_coverage':True};assert list(sources.stream(e,lambda:None))==[];results.append({'case':'required_rendered_SQLite_missing_body','yielded_observations':0,'yielded_coverage_holds':0,'rows_in_table':1})
# Actual held role can be overwritten by current_train classification. Extract the
# real production loop's classifier statements, execute only those on one fixture.
tree=ast.parse((P/'audit.py').read_text());worker=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='worker')
loop=next(n for n in ast.walk(worker) if isinstance(n,ast.For) and isinstance(n.target,ast.Tuple) and [x.id for x in n.target.elts if isinstance(x,ast.Name)]==['ident','source','norm','held','families','reference'])
body=[]
for n in loop.body:
 if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='examine':break
 body.append(n)
code=compile(ast.fix_missing_locations(ast.Module(body=body,type_ignores=[])),'exact_production_role_classifier','exec');norm=' '.join('word'+str(i) for i in range(40));digest=core.sha(norm.encode());scope={'ident':17,'norm':norm,'held':1,'roles':{17:{'split':'train','normalized_sha256':digest,'family_id':'fixture'}},'core':core,'historical':{17:digest},'historical_seen':0,'seen_roles':collections.Counter()};exec(code,scope)
assert scope['role']=='current_train' and scope['historical_seen']==1
results.append({'case':'historical_held_and_M0_train_role_collision','held_flag':True,'historical_hash_bound':True,'M0_role':'train','actual_production_role':scope['role'],'is_treated_protected_by_examine':scope['role'] in ['historical_heldout','current_development','current_test','explicit_protected'],'scope':'Synthetic counterexample only; no assertion actual pinned registry contains this collision. Worker must reject contradictory role or preserve historical protection, not silently reclassify.'})
# Preflight has no armed external alarm; scale the monotonic clock so a finite
# 80ms mock blocking verify exceeds the declared570 logical seconds.
with tempfile.TemporaryDirectory() as t:
 root=pathlib.Path(t);out=root/'prior';out.mkdir();events=[];started=time.monotonic();scale=10000
 def verify(*a):events.append({'alarm_armed':signal.getitimer(signal.ITIMER_REAL)[0]>0});time.sleep(.08)
 with patch.object(audit,'ROOT',root),patch.object(audit,'OUT',out),patch.object(audit,'clk',lambda:time.monotonic()*scale),patch.object(audit,'verify',verify):
  try:audit.supervise(types.SimpleNamespace(code_pins_sha256='fixture',profile_sha256='fixture'))
  except ValueError:pass
  else:raise AssertionError('existing output must refuse')
 elapsed=(time.monotonic()-started)*scale;assert elapsed>570 and events==[{'alarm_armed':False}]
 results.append({'case':'blocked_verify_exceeds_external_limit_before_existingOUT_refusal','logical_elapsed_seconds':elapsed,'declared_external_seconds':570,'alarm_armed_during_verify':False,'clock_scaled_only_for_tiny_control':True,'actual_elapsed_seconds':elapsed/scale})
# Existing controls correctly handle optional aliases and protection precedence.
a={'adapter':'native_or_plain_UTF8_file','required_current_candidate_body_coverage':True};b={**a,'required_current_candidate_body_coverage':False};assert sources.alias_signature(a,'same')!=sources.alias_signature(b,'same');assert core.disposition(True,True)=='PROTECTED_FAMILY_HOLD';results.append({'case':'correct_required_alias_and_protected_ancestor_precedence','PASS':True})
(OUT/'counterexample-results.json').write_text(json.dumps({'status':'CONCRETE_FAILURES_REPRODUCED_NO_CORPUS_SCAN','cases':results,'network':0,'fullcorpus_scans':0,'models':0},indent=2)+'\n');print(json.dumps(results,indent=2))
