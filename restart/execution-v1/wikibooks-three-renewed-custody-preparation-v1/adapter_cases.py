"""Actual adapters/production role classifier tiny collision controls."""
import hashlib,json,pathlib,sqlite3,tempfile
import sources,overlap_core
sha=lambda b:hashlib.sha256(b).hexdigest()
def run():
 checks=[]
 with tempfile.TemporaryDirectory() as tmp:
  root=pathlib.Path(tmp);p=root/'required.jsonl';values=[{}, {'text':None}, {'unknown_body':'not a recognized field'}, {'html':'wrong field for required plaintext'}];p.write_text(''.join(json.dumps(v)+'\n' for v in values));entry={'path':str(p),'adapter':'jsonl_text_fields','required_current_candidate_body_coverage':True};rows=list(sources.stream(entry,lambda:None));assert len(rows)==4 and all(t is None and m.get('coverage_hold') for i,t,m in rows);checks.append({'check':'actual_required_JSONL_missing_null_unknown_wrong_bodyfield_emits4holds','PASS':True})
  dbpath=root/'data.sqlite';db=sqlite3.connect(dbpath);db.execute('create table rendered (data text)');db.executemany('insert into rendered values (?)',[(json.dumps(v),) for v in values]+[(None,)]);db.commit();db.close();entry={'path':str(dbpath),'adapter':'sqlite_json_data','table':'rendered','columns':['data'],'required_current_candidate_body_coverage':True};rows=list(sources.stream(entry,lambda:None));assert len(rows)==5 and all(t is None and m.get('coverage_hold') for i,t,m in rows);checks.append({'check':'actual_required_SQLiteJSON_missing_null_unknown_fields_and_NULLstorage_emit5holds','PASS':True})
  body=root/'chapter.txt';text=b'Synthetic already scheduled required candidate body.';body.write_bytes(text);manifest=root/'chapters.jsonl';record={'file':'chapter.txt','sha256':sha(text),'bytes':len(text),'family_id':'same-work','split':None,'training_admitted':False};manifest.write_text(json.dumps(record)+'\n');entry={'path':str(manifest),'adapter':'jsonl_external_text_manifest','required_current_candidate_body_coverage':True};rows=list(sources.stream(entry,lambda:None,required_paths={str(body.resolve())}));assert len(rows)==1 and rows[0][1] is None and rows[0][2]['body_reference_alias'] and not rows[0][2].get('coverage_hold');checks.append({'check':'actual_metadata_manifest_reconciles_already_scheduled_exact_body_no_new_hold','PASS':True})
  rows=list(sources.stream(entry,lambda:None,required_paths=set()));assert rows[0][2].get('coverage_hold');checks.append({'check':'metadata_reference_to_unscheduled_body_is_real_coveragehold','PASS':True})
  body.write_bytes(text+b'changed');rows=list(sources.stream(entry,lambda:None,required_paths={str(body.resolve())}));assert rows[0][2].get('coverage_hold');checks.append({'check':'metadata_reference_hash_or_size_tamper_is_coveragehold','PASS':True})
  p.write_text('{}\n');entry={'path':str(p),'adapter':'jsonl_text_fields','required_current_candidate_body_coverage':False};assert list(sources.stream(entry,lambda:None))==[];checks.append({'check':'optional_raw_metadata_row_does_not_create_new_clearance_obligation','PASS':True})
 try:overlap_core.legacy_role(True,'train')
 except ValueError:checks.append({'check':'actual_production_legacy_role_rejects_historicalheld_M0train_contradiction','PASS':True})
 else:raise AssertionError('historical_protection_was_overwritten')
 assert overlap_core.legacy_role(True,None)=='historical_heldout' and overlap_core.legacy_role(False,'train')=='current_train' and overlap_core.legacy_role(True,'test')=='current_test';checks.append({'check':'production_valid_legacy_train_and_both_protected_roles_preserved','PASS':True})
 return {'status':'PASS_ACTUAL_ADAPTER_AND_ROLE_PATH_SYNTHETIC_ONLY','count':len(checks),'checks':checks,'retained_corpus_scan':False}
if __name__=='__main__':print(json.dumps(run(),indent=2))
