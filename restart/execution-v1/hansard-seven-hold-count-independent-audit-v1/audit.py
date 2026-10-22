"""One read-only completed Hansard stored-count reconciliation; no source bodies."""
from pathlib import Path
import json,hashlib,sqlite3,os,datetime
B=Path(__file__).resolve().parents[1];O=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
paths={'current':B/'hansard-seven-hold-count-update-v1/counts.json','code':B/'hansard-seven-hold-count-update-v1/recount.py','prior':B/'m2-intake/hansard-current-semantic-rights-hold-diagnostics-v1/counts.json','uniform':B/'hansard-uniform20-team-review-progress-v2/review.json','byte':B/'hansard-byte10-parent-whole-review-progress-v1/review.json','proof':B/'hansard-language-token-terminal-parent-verification-v1/verification.json'}
j={k:json.loads(p.read_text()) for k,p in paths.items() if k!='code'};reported=j['current'];old=j['prior'];held4={x['text_SHA256'] for x in old['exact_semantic_holds']};targets=held4|{x['text_SHA256'] for x in j['uniform']['new_exact_semantic_hold_targets']}|{x['text_SHA256'] for x in j['byte']['reviews'] if x['all_exact_text_copies_current_review_hold']};assert len(held4)==4 and len(targets)==7
for path,h in reported['inputs_SHA256'].items():
 if path.endswith('screening.sqlite'):continue
 assert sha(Path(path))==h,path
sql=B/'m2-intake/hansard-two-complete-raw-language-M1-diagnostics-v1/screening.sqlite';ident=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns);before=ident(sql.stat());fd=os.open(sql,os.O_RDONLY|os.O_NOFOLLOW)
try:
 assert ident(os.fstat(fd))==before;h=hashlib.sha256()
 while True:
  b=os.read(fd,1048576)
  if not b:break
  h.update(b)
 assert h.hexdigest()==reported['inputs_SHA256'][str(sql)]==old['source_token_SQLite_SHA256']
 db=sqlite3.connect(sql.as_uri()+'?mode=ro&immutable=1',uri=True);db.execute('pragma query_only=ON');db.execute('pragma cache_size=-4096');rows=list(db.execute('select lower(hex(text_SHA256)),UTF8_bytes,content_tokens,language_pass,occurrences,explicit_hold_flags,rights_unclear_flags from texts order by text_SHA256'));db.close();assert len(rows)==15800
 def total(rr):return {'distinct_text_SHA':len(rr),'M1_content_tokens':sum(x[2] for x in rr),'UTF8_bytes':sum(x[1] for x in rr),'raw_occurrences':sum(x[4] for x in rr),'EOS_separate':len(rr),'usable_or_admitted':False}
 assert total(rows)==old['summaries']['all_distinct_not_usable']==reported['summaries']['all_distinct_not_usable']
 prior_selected=[x for x in rows if x[3] and x[0] not in held4];selected=[x for x in rows if x[3] and x[0] not in targets];selectedrights=[x for x in selected if x[6]==0]
 assert total(prior_selected)==old['summaries']['language_pass_after_all4_known_semantic_holds_not_usable']
 assert total(selected)==reported['summaries']['language_pass_after_all7_known_semantic_holds_not_usable'];assert total(selectedrights)==reported['summaries']['language_pass_after_all7_holds_and_localized_NI_London_flags_STILL_UNCLEARED']
 held=[{'text_SHA256':x[0],'UTF8_bytes_onecopy':x[1],'M1_content_tokens_onecopy':x[2],'language_pass':bool(x[3]),'raw_occurrences':x[4],'hold_all_exactcopies':True} for x in rows if x[0] in targets];assert held==reported['exact_semantic_holds'];assert all(x[0] in targets for x in rows if x[5])
 assert ident(os.fstat(fd))==ident(sql.stat())==before
finally:os.close(fd)
new=targets-held4;result={'status':'PASS_INDEPENDENT_COMPLETED_HANSARD_STORED_COUNT_AND_HOLD_UNION_AUDIT_NO_ADMISSION','UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'inputs_SHA256':{k:sha(p) for k,p in paths.items()},'source_SQLite_SHA256':h.hexdigest(),'source_SQLite_stat_before_after':list(before),'known_hold_union':{'old':len(held4),'new':len(new),'total':len(targets),'new_SHA256':sorted(new),'new_language_pass':sum(x[3] for x in rows if x[0] in new),'new_language_pass_tokens_removed':sum(x[2] for x in rows if x[0] in new and x[3])},'old4_baseline_exactly_reproduced':True,'all7_metadata_bindings_exact':True,'summaries':reported['summaries'],'rights_status':'ALL UNCLEARED, including localized rightsflag zero; diagnostics not admission.','code_review':'Set union is all-copy rawSHA; prior all-distinct and old4 conditional totals are asserted, all original explicit holds must remain in union; completed RO URI and unchanged stat preserve metadata. No tokenizer/body inference.','source_body_reads':0,'live_PressBooks_SQL_reads':0,'new_admitted_documents':0}
(O/'review.json').write_text(json.dumps(result,indent=2)+'\n');(O/'manifest.json').write_text(json.dumps({'SHA256':{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!='manifest.json'}},indent=2)+'\n')
for p in O.iterdir():p.chmod(0o444)
print(json.dumps({'review_SHA256':sha(O/'review.json'),'manifest_SHA256':sha(O/'manifest.json'),'known_holds':result['known_hold_union'],'language_after7':total(selected),'localized_rights_diagnostic':total(selectedrights)},indent=2))
