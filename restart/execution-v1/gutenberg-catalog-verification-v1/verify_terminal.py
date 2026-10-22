"""Independent terminal catalog/accounting/typed-field verification; no fetches."""
import collections,fcntl,hashlib,json,os,sqlite3,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;EXEC=HERE.parent;PREP=EXEC/'gutenberg-catalog-preparation-v1';sys.path.insert(0,str(PREP));import catalog as c
EXPECTED='2e9b21599cb0b15e6efb301c1e704884cc6a244db9233b650c84bf82aceec6ed';c.pins(EXPECTED);out=c.DEST
w=json.loads((out/'worker-result.json').read_text());s=json.loads((out/'supervisor-result.json').read_text());checks={};transferfile=out/'transfer-receipt.json';tr=json.loads(transferfile.read_text()) if transferfile.exists() else None
checks['reviewed_code_and_runtime_pins_unchanged']=True
checks['supervisor_terminal']=s['status'] in {'COMPLETE','FAILED'}
if tr:
 checks['compressed_archive_exact_transferhash_and_length']=c.file_sha(out/c.ARCHIVE)==tr['response_SHA256'] and (out/c.ARCHIVE).stat().st_size==tr['actual_response_bytes']<c.BODY_CAP
 checks['one_exact_request_TLS_noredirect_noretry']=tr['URL']==tr['effective_URL']==c.URL and tr['charged_before_IO'] and tr['strict_TLS_CERT_REQUIRED_hostname'] and not tr['redirect'] and not tr['retry']
conn=sqlite3.connect('file:'+str((c.ROOT/'charges/ledger.sqlite').resolve())+'?mode=ro',uri=True)
try:
 row=conn.execute('select charge,state,actual_bytes,body_sha256 from attempts where key=?',(c.KEY,)).fetchone();charge=json.loads(row[0])
 checks['exact_one_durable_attempt_and_conservative_reservation']=conn.execute('select count(*) from attempts where key=?',(c.KEY,)).fetchone()[0]==1 and charge['requests']==1 and charge['body_bytes']==160000000 and charge['output_bytes']==1000000000 and charge['rows']==150000
 if tr:checks['complete_transport_durable_ledger_truth']=row[1]=='complete' and row[2]==tr['actual_response_bytes'] and row[3]==tr['response_SHA256']
 ledger={'charge':charge,'state':row[1],'actual_bytes':row[2],'body_SHA256':row[3]}
finally:conn.close()
with (c.ROOT/'charges/job.lock').open('r+') as lock:
 try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:checks['global_ledger_released']=False
 else:checks['global_ledger_released']=True;fcntl.flock(lock,fcntl.LOCK_UN)
try:os.kill(s['worker_pid'],0)
except ProcessLookupError:checks['worker_gone']=True
else:checks['worker_gone']=False
checks['observed_resource_bounds']=s['elapsed_seconds']<600 and s['peak_observed_process_tree_RSS_bytes']<=1000000000 and c.size()<1000000000
success=s['status']=='COMPLETE' and w['status']=='COMPLETE_CATALOG_ARCHIVE_IDENTITY_AND_BOUNDED_METADATA_INVENTORY_NO_ADMISSION'
report={'status':'PASS_VERIFIED_COMPLETE_CATALOG_METADATA_ONLY' if success else 'VERIFIED_TERMINAL_FAILURE_NO_RETRY_NO_COMPLETE_FRAME','checks':checks,'ledger':ledger,'worker_status':w['status'],'supervisor_status':s['status'],'supervisor_elapsed_seconds':s['elapsed_seconds'],'peak_observed_process_tree_RSS_bytes':s['peak_observed_process_tree_RSS_bytes'],'new_admitted_documents':0,'new_admitted_tokens':0,'book_bodies_fetched':0}
if success:
 st=w['stats'];checks['full_tar_end_bzip2_CRC_EOF_receipts']=st['full_tar_EOF_verified'] and st['full_bzip2_CRC_EOF_verified'] and st['archive_identity_inventory_complete']
 checks['database_hash_and_worker_supervisor_binding']=c.file_sha(out/'catalog.sqlite3')==w['database_SHA256'] and c.file_sha(out/'worker-result.json')==s['worker_result_SHA256'] and w['manifest_SHA256']==s['manifest_SHA256']==EXPECTED
 db=sqlite3.connect('file:'+str((out/'catalog.sqlite3').resolve())+'?mode=ro',uri=True)
 try:
  checks['independent_SQLite_integrity']=db.execute('pragma integrity_check').fetchone()[0]=='ok'
  n,total=db.execute('select count(*),sum(bytes) from members').fetchone();records=db.execute('select count(*) from records').fetchone()[0]
  checks['independent_allmember_record_byte_reconciliation']=n==st['members'] and total==st['member_body_bytes'] and records==st['parsed_ebook_records']
  duplicate=db.execute('select count(*) from (select ebook_ID from records group by ebook_ID having count(*)>1)').fetchone()[0];checks['duplicate_ID_count_reproduced']=duplicate==st['duplicate_ebook_ID_groups']
  counts=collections.Counter();languages=collections.Counter();held=collections.Counter();roles=collections.Counter();format_mime=collections.Counter();creator_deaths=collections.Counter();unmapped=collections.Counter();memberholds=collections.Counter();sample=[]
  for ordinal,name,bytes_,bodyhash,payload in db.execute('select * from members order by ordinal'):
   m=json.loads(payload);assert m['ordinal']==ordinal and m['name']==name and m['size']==bytes_ and m['body_SHA256']==bodyhash and len(bodyhash)==64
   if m['hold']:memberholds[m['hold']]+=1
  for member,eid,payload,rawhash,membername in db.execute('select records.member,records.ebook_ID,records.data,members.body_hash,members.name from records join members on members.ordinal=records.member order by records.member'):
   r=json.loads(payload);assert r['ebook_ID']==eid and r['member']==membername and r['member_RDF_SHA256']==rawhash and r['training_admitted'] is False and r['book_body_fetched'] is False
   assert r['original_English_composition']=='UNVERIFIED' and r['edition_and_jurisdiction_rights']=='UNVERIFIED'
   english=r['languages']==['en'] and r['types']==['Text'];assert english==r['metadata_English_Text_view'];counts['records']+=1;counts['English_Text_metadata_only']+=english
   languages['|'.join(r['languages']) or 'MISSING']+=1
   for hold in r['holds']:held[hold]+=1
   for field in r['unmapped_book_fields']:unmapped[field['qualified_name']]+=1
   if not r['languages']:counts['language_missing']+=1
   if not r['types']:counts['type_missing']+=1
   if not r['formats']:counts['formats_missing']+=1
   if not r['subjects']:counts['subjects_missing']+=1
   if not r['contributors_and_all_roles']:counts['contributors_missing']+=1
   for person in r['contributors_and_all_roles']:
    roles[person['role_qualified_name']]+=1
    if person['role_qualified_name']=='{'+c.parse_rdf.DCT+'}creator':
     counts['creator_agents']+=1;counts['creator_agents_stable_ID']+=person['stable_agent_ID'] is not None;counts['creator_agents_birthdate_present']+=bool(person['birthdates']);counts['creator_agents_deathdate_present']+=bool(person['deathdates'])
     for date in person['deathdates']:creator_deaths[date]+=1
   for fmt in r['formats']:
    counts['format_entries']+=1;counts['formats_extent_present']+=fmt['extent_bytes'] is not None
    for mime in fmt['MIME_values']:format_mime[mime]+=1
   for field in r['excluded_description_summary_fields']:
    assert 'text' not in field and len(field['original_text_SHA256'])==64;counts['excluded_summary_description_fields']+=1
   if len(sample)<10:sample.append({'ebook_ID':eid,'titles':r['titles'],'languages':r['languages'],'types':r['types'],'holds':r['holds'],'member_SHA256':rawhash})
  checks['all_saved_member_and_record_bindings_and_summary_exclusion']=counts['records']==records
  checks['English_and_missingness_counts_reproduced']=counts['English_Text_metadata_only']==st['English_Text_metadata_rows'] and counts['language_missing']==st['rows_with_missing_language_metadata'] and counts['type_missing']==st['rows_with_missing_type_metadata']
  report.update({'stats':st,'typed_field_counts':dict(counts),'catalog_language_set_counts':dict(languages),'record_hold_counts':dict(held),'member_hold_counts':dict(memberholds),'contributor_role_counts':dict(roles),'format_MIME_counts':dict(format_mime),'unmapped_book_field_counts':dict(unmapped),'first_ten_metadata_record_diagnostics_not_sample':sample,'no_population_or_token_yield_claim':True})
 finally:db.close()
else:
 report['failure_reason']=w.get('error');report['compressed_archive_preserved']=bool(tr);report['catalog_frame_complete']=False
 dbpath=out/'catalog.sqlite3'
 if dbpath.exists():
  db=sqlite3.connect('file:'+str(dbpath.resolve())+'?mode=ro',uri=True)
  try:
   checks['partial_SQLite_integrity']=db.execute('pragma integrity_check').fetchone()[0]=='ok'
   membercount,memberbytes=db.execute('select count(*),sum(bytes) from members').fetchone();recordcount=db.execute('select count(*) from records').fetchone()[0]
   report['partial_retained_counts_not_population']={'members':membercount,'member_body_bytes':memberbytes,'parsed_metadata_records':recordcount,'English_counts_deliberately_not_computed_without_full_EOF':True}
   report['partial_database_SHA256']=c.file_sha(dbpath)
  finally:db.close()
assert all(checks.values()),checks
report['check_count']=len(checks)
raw=(json.dumps(report,indent=2)+'\n').encode()
# Preserve the capped originalrun unchanged; verification evidence is separate.
with (HERE/'independent-terminal-verification.json').open('xb') as f:f.write(raw)
print(json.dumps({'status':report['status'],'checks':len(checks),'report_SHA256':c.sha(raw),'typed_field_counts':report.get('typed_field_counts'),'failure':report.get('failure_reason')},indent=2))
