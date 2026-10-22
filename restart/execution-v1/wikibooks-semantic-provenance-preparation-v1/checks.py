"""Actual production helper synthetic paths/rows; no retained body parsing/matching."""
import copy,hashlib,json,sqlite3
import semantic_provenance as s
def run():
 cases=[]
 def no(name,fn):
  try:fn()
  except (ValueError,KeyError):cases.append(name);return
  raise AssertionError(name)
 base={'adapter':'sqlite_json_data','table':'rendered','required_current_candidate_body_coverage':True,'coverage_role':'CURRENT'}
 entries=[dict(base,path='different-prefix/recovered'),dict(base,path='canonical/rendered')];canon=[{'path':'canonical/rendered','SHA256':'a'*64}];pins={e['path']:'a'*64 for e in entries}
 assigned=s.annotate(entries,canon,pins);assert all(e['semantic_coverage_role']==s.WB for e in assigned);assert s.alias_signature(assigned[0])==s.alias_signature(assigned[1]);cases.append('recovered_first_and_original_later_both_hash_bound_WB')
 reverse=s.annotate(entries[::-1],canon,pins);assert {e['path']:e['semantic_coverage_role'] for e in assigned}=={e['path']:e['semantic_coverage_role'] for e in reverse};cases.append('order_independent_semantic_assignment')
 for field,value in [('table','other'),('adapter','sqlite_text'),('required_current_candidate_body_coverage',False),('coverage_role','PROTECTED')]:
  changed=[{**entries[0],field:value},entries[1]];a=s.annotate(changed,canon,pins);assert a[0]['semantic_coverage_role']==s.GENERIC and s.alias_signature(a[0])!=s.alias_signature(a[1]);cases.append('different_'+field+'_not_role_alias')
 no('canonical_missing_refused',lambda:s.annotate(entries[:1],canon,pins));no('canonical_hash_changed_refused',lambda:s.annotate(entries,canon,{**pins,'canonical/rendered':'b'*64}))
 db=sqlite3.connect(':memory:');db.executescript('create table pages(source_ordinal integer primary key,page_id integer,revision_id integer,family text,text_sha256 text,holds text,active integer);create table final_pages(source_ordinal integer primary key,holds text);')
 text='A complete short reference definition.';digest=hashlib.sha256(text.encode()).hexdigest();db.execute('insert into pages values(1,7,9,?,?,?,1)',('family',digest,json.dumps(['prior_hold'])));db.execute('insert into final_pages values(1,?)',(json.dumps(['final_hold']),));meta={'source_ordinal':1,'page_id':7,'revision_id':9,'family':'family','family_id':'family'}
 proof=s.WBRoleProof(assigned[0],[1]);m=proof.observe(meta,text,db);assert m['current_global_finalizer_role']['prior_holds']==['prior_hold'] and m['current_global_finalizer_role']['global_final_holds']==['final_hold'];cases.append('actual_row_validation_preserves_prior_final_roles')
 no('uncompared_owner_cannot_discharge_alias',lambda:s.inherit_alias(assigned[1],assigned[0],proof.finish()));proof.note_compared(1);good=proof.finish();alias=s.inherit_alias(assigned[1],assigned[0],good);assert alias['validated_rows_inherited']==1;cases.append('complete_validated_compared_owner_alias_inheritance')
 for key,value in [('page_id',8),('revision_id',10),('family','wrong'),('family_id','wrong')]:no('bad_'+key+'_owner_refused',lambda key=key,value=value:s.WBRoleProof(assigned[0],[1]).observe({**meta,key:value},text,db))
 no('changed_body_SHA_refused',lambda:s.WBRoleProof(assigned[0],[1]).observe(meta,text+'bad',db));no('duplicate_owner_row_refused',lambda:proof.observe(meta,text,db));no('missing_owner_row_refused',lambda:s.WBRoleProof(assigned[0],[1]).finish());no('compare_before_role_validation_refused',lambda:s.WBRoleProof(assigned[0],[1]).note_compared(1))
 no('native_extracted_hash_contradiction_refused',lambda:s.WBRoleProof(assigned[0],[1]).observe({**meta,'extracted_text_sha256':'wrong'},text,db))
 no('non_WB_alias_proof_refused',lambda:s.inherit_alias({**assigned[1],'semantic_coverage_role':s.GENERIC},assigned[0],good))
 for key,value in [('complete_role_coverage',False),('complete_body_comparison',False),('owner_path','wrong'),('identity_set_SHA256',''),('all_prior_finalizer_holds_preserved',False)]:no('tampered_owner_'+key,lambda key=key,value=value:s.inherit_alias(assigned[1],assigned[0],{**good,key:value}))
 db.close();return {'status':'PASS','controls':len(cases),'cases':cases,'retained_bodies_parsed_or_matched':False}
if __name__=='__main__':print(json.dumps(run(),indent=2))
