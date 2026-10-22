"""Closure-only synthetic codepath/role/match/lifecycle controls. No retained scan."""
import copy,json,os,pathlib,signal,sqlite3,sys,tempfile,time
import closure
def run():
 cases=[]
 def no(name,fn):
  try:fn()
  except (ValueError,KeyError,TimeoutError):cases.append(name);return
  raise AssertionError(name)
 source="def worker():\n for e in entries:\n  for x in source_stream(e):\n   examine(x)\n expected_wb=get_expected()\n if wb_seen!=expected_wb:\n  raise ValueError('current_Wikibooks_finalized_body_coverage_gap')\n"
 proof=closure.postloop_proof(source,'line 7, in worker\ncurrent_Wikibooks_finalized_body_coverage_gap');assert proof['unique_postloop_raise_line']==7;cases.append('actual_AST_sequential_all_adapter_loop_proof')
 no('traceback_wrong_line_refused',lambda:closure.postloop_proof(source,'line 6, in worker\n'+closure.ERROR))
 inside="def worker():\n for e in entries:\n  if failed:\n   raise ValueError('current_Wikibooks_finalized_body_coverage_gap')\n";no('failure_inside_adapter_loop_refused',lambda:closure.postloop_proof(inside,'line 4, in worker\n'+closure.ERROR))
 before="def worker():\n if failed:\n  raise ValueError('current_Wikibooks_finalized_body_coverage_gap')\n for e in entries:\n  examine(e)\n";no('failure_before_loop_refused',lambda:closure.postloop_proof(before,'line 3, in worker\n'+closure.ERROR))
 no('nonunique_failure_refused',lambda:closure.postloop_proof(source+" raise ValueError('current_Wikibooks_finalized_body_coverage_gap')\n",'line 7, in worker\n'+closure.ERROR))
 base={'path':'a','adapter':'sqlite_json_data','table':'rendered','required_current_candidate_body_coverage':True,'coverage_role':'CURRENT_OR_RETAINED_CANDIDATE_BODY'};entries=[base,{**base,'path':'b'}];pins={'a':'same','b':'same'}
 assert closure.old_role_alias_proof(entries,pins)['unique_old_alias_groups']==1;cases.append('old_signature_same_required_implies_same_actual_frame_role')
 no('old_signature_cannot_inherit_protected_role',lambda:closure.old_role_alias_proof([base,{**base,'path':'b','coverage_role':'explicit_protected'}],pins))
 no('missing_required_flag_type_refused',lambda:closure.old_role_alias_proof([{**base,'required_current_candidate_body_coverage':1}],pins))
 no('required_generic_role_mismatch_refused',lambda:closure.old_role_alias_proof([{**base,'required_current_candidate_body_coverage':False}],pins))
 core=closure.load('closure_fixture_core',closure.OLD/'overlap_core.py')
 with tempfile.TemporaryDirectory(prefix='WB-closure-synthetic-') as t:
  root=pathlib.Path(t);main=' '.join('word'+str(i) for i in range(80));parent='source introduction '+main+' final note';printtext='printed material '+parent+' appendix'
  mainfile=root/'main.txt';parentfile=root/'parent.txt';mainfile.write_text(main);parentfile.write_text(parent)
  c={'source_ordinal':61485,'page_id':7,'revision_id':9,'family_ID':'family','file':str(mainfile),'text_SHA256':core.sha(main.encode()),'captured_raw_source_ancestor':{'path':str(parentfile),'SHA256':core.sha(parent.encode())}}
  sourcefile=root/'synthetic.sqlite3';db=sqlite3.connect(sourcefile);db.execute('create table rendered(source_ordinal integer primary key,page_id integer,revision_id integer,family text,data text)')
  final=sqlite3.connect(':memory:');final.executescript('create table pages(source_ordinal integer primary key,page_id integer,revision_id integer,family text,text_sha256 text,holds text,active integer,title text);create table final_pages(source_ordinal integer primary key,holds text);')
  for ordinal,page,text,title,holds in [(61485,7,parent,'Reference',[]),(30857,8,printtext,'Reference/Print version',['print_or_aggregate_page'])]:
   obj={'canonical_source_ordinal':ordinal,'page_id':page,'revision_id':9,'family_id':'family','extracted_text_sha256':core.sha(text.encode()),'title':title,'url':'https://en.wikibooks.org/wiki/Synthetic','text':text};db.execute('insert into rendered values(?,?,?,?,?)',(ordinal,page,9,'family',json.dumps(obj)));final.execute('insert into pages values(?,?,?,?,?,?,?,?)',(ordinal,page,9,'family',core.sha(text.encode()),json.dumps(holds),1,title));final.execute('insert into final_pages values(?,?)',(ordinal,json.dumps(holds)))
  db.commit();db.close();index=core.Index([main]);records=[]
  for identity,text,metadata,role in [(str(mainfile)+'#file',main,{},'CURRENT_OR_RETAINED_CANDIDATE_BODY'),(str(sourcefile)+'#parent:text',parent,{'source_ordinal':61485},'CURRENT_OR_RETAINED_CANDIDATE_BODY'),(str(sourcefile)+'#print:text',printtext,{'source_ordinal':30857},'CURRENT_OR_RETAINED_CANDIDATE_BODY')]:
   norm=core.normalized(text);records.append({'candidate_source_ordinal':61485,'source_identity':identity,'source_metadata':metadata,'source_role':role,'source_normalized_sha256':core.sha(norm.encode()),'candidate_current_SHA256':c['text_SHA256'],'match':index.compare(norm)[0],'disposition':'OLD_DIAGNOSTIC'})
  roles=[{'path':str(sourcefile),'semantic_coverage_role':'CURRENT_WIKIBOOKS_FINALIZED_RENDERED'}];fresh=closure.match_reproof([c],records,core,final,roles);assert fresh[0]['new_source_role_bound_disposition'].startswith('EXACT_REGISTERED') and fresh[1]['new_source_role_bound_disposition'].startswith('EXACT_REGISTERED');assert fresh[2]['new_source_role_bound_disposition']=='BODY_MATCH_REQUIRES_CUSTODY_REVIEW' and fresh[2]['same_conservative_family_body_match_pending_parent_adjudication'] and fresh[2]['currently_held_print_or_aggregate_source'];cases.append('actual_match_reproof_preserves_printaggregate_distinct_from_exact_parent')
  protected=copy.deepcopy(records[:1]);protected[0]['source_role']='explicit_protected';assert closure.match_reproof([c],protected,core,final,roles)[0]['new_source_role_bound_disposition']=='PROTECTED_FAMILY_HOLD';cases.append('protected_precedence_over_exact_current_alias')
  bad=copy.deepcopy(records);bad[0]['source_normalized_sha256']='wrong';no('saved_source_normalization_tamper_refused',lambda:closure.match_reproof([c],bad,core,final,roles))
  bad=copy.deepcopy(records);bad[0]['match']={};no('saved_match_payload_tamper_refused',lambda:closure.match_reproof([c],bad,core,final,roles))
  final.close()
  out=root/'worker';code="import pathlib,json,sys;p=pathlib.Path(sys.argv[1])/'result.json';b=json.dumps({'status':'COMPLETE_SYNTHETIC'}).encode();p.write_bytes(b+b' '*(32768-len(b)))";rss=closure.supervisor.tree_rss;roots=[]
  def rooted(pid):assert pid==os.getpid();roots.append(pid);return rss(pid)
  closure.supervisor.tree_rss=rooted
  try:closure.supervisor.supervise(out,lambda start:[sys.executable,'-B','-c',code,str(out)])
  finally:closure.supervisor.tree_rss=rss
  assert roots and json.loads((out/'supervisor.json').read_text())['child_reaped'];cases.append('actual_new_supervisor_synthetic_child_root_RSS_ownership_reap')
  for name,sig in [('deadline',signal.SIGALRM),('TERM',signal.SIGTERM)]:
   out=root/name
   def fail():signal.raise_signal(sig)
   no('actual_'+name+'_preflight_armed_before_any_job_output',lambda:closure.supervisor.supervise(out,lambda start:[],preflight=fail));assert not out.exists()
 # Module's sibling import must resolve to reviewed helper, not a new implementation.
 sys.path.insert(0,str(closure.HELPER));semanticchecks=closure.load('semantic_fixture_checks',closure.HELPER/'checks.py');helper_result=semanticchecks.run()
 return {'status':'PASS','controls':len(cases),'cases':cases,'shared_semantic_controls':helper_result['controls'],'no_retained_role_delta_or_match_reproof_executed':True}
if __name__=='__main__':print(json.dumps(run(),indent=2))
