"""Actual production owner lifecycle functions with hostile synthetic row/role variants."""
import json,sqlite3,tempfile,pathlib
import audit,semantic_provenance as semantic

def run():
 passed=[]
 def no(name,fn):
  try:fn()
  except ValueError:passed.append(name);return
  raise AssertionError(name)
 with tempfile.TemporaryDirectory() as t:
  path=pathlib.Path(t)/'canonical.sqlite3';db=sqlite3.connect(path);db.execute('create table rendered(source_ordinal integer)');db.executemany('insert into rendered values(?)',[(1,),(2,)]);db.commit();db.close()
  e={'path':'recovered-first','adapter':'sqlite_json_data','table':'rendered','required_current_candidate_body_coverage':True,'coverage_role':'CURRENT','physical_source_SHA256':'a'*64,'semantic_coverage_role':semantic.WB,'WB_canonical_paths':[str(path)]}
  final=sqlite3.connect(':memory:');final.executescript('create table pages(source_ordinal integer,page_id integer,revision_id integer,family text,text_sha256 text,holds text,active integer);create table final_pages(source_ordinal integer,holds text);')
  for i in [1,2]:final.execute('insert into pages values(?,?,?,?,?,?,?)',(i,10+i,20+i,'family',audit.core.sha(('text'+str(i)).encode()),'["prior"]',1));final.execute('insert into final_pages values(?,?)',(i,'["final"]'))
  meta=lambda i:{'source_ordinal':i,'page_id':10+i,'revision_id':20+i,'family':'family','family_id':'family'}
  p=audit.prepare_WB_owner(e,{1,2});assert p.expected=={1,2};passed.append('actual_canonical_SQL_derives_full_owner_not_subset')
  no('canonical_ordinal_outside_finalizer_refused',lambda:audit.prepare_WB_owner(e,{1}))
  calls=[];audit.compare_WB_row(p,meta(1),'text1',final,lambda m:calls.append(m)or True);assert calls[0]['current_global_finalizer_role']['global_final_holds']==['final'];passed.append('actual_compare_receives_validated_prior_final_roles')
  no('missing_row_completion_refused',lambda:audit.complete_WB_owner(p,set()))
  q=audit.prepare_WB_owner(e,{1,2});calls=[];no('bad_revision_refused_before_matcher',lambda:audit.compare_WB_row(q,{**meta(1),'revision_id':0},'text1',final,lambda m:calls.append(m)or True));assert not calls;passed.append('bad_identity_no_matcher_call')
  no('required_body_hold_cannot_be_compared',lambda:audit.compare_WB_row(q,meta(1),'text1',final,lambda m:None));assert not q.compared;passed.append('hold_never_marks_compared')
  no('held_owner_cannot_discharge_alias',lambda:semantic.inherit_alias({**e,'path':'original-later'},e,q.finish()))
  audit.compare_WB_row(p,meta(2),'text2',final,lambda m:True);seen=set();receipt=audit.complete_WB_owner(p,seen);assert seen=={1,2};passed.append('union_from_actual_compared_rows')
  inherited=semantic.inherit_alias({**e,'path':'original-later'},e,receipt);assert inherited['validated_rows_inherited']==2;passed.append('recovered_first_original_later_fullproof_inheritance')
  no('duplicate_canonical_owner_union_refused',lambda:audit.complete_WB_owner(p,{1}))
  for key,value in [('coverage_role','PROTECTED'),('required_current_candidate_body_coverage',False),('table','other'),('semantic_coverage_role',semantic.GENERIC)]:no('alias_semantic_change_'+key,lambda key=key,value=value:semantic.inherit_alias({**e,'path':'other',key:value},e,receipt))
  final.close()
 return {'status':'PASS_ACTUAL17_PRODUCTION_SEMANTIC_OWNER_LIFECYCLE_NO_CORPUS_SCAN','checks':len(passed),'cases':passed}
if __name__=='__main__':print(json.dumps(run(),indent=2))
