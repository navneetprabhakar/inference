"""Read-only independent terminal checks; writes one new verification receipt."""
import hashlib,json,sqlite3,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
OUT=HERE.parent/'m2-intake/wikibooks-complete-identity-frame-v1'
checks=[]
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def check(b,name):
 assert b,name
 checks.append(name)
w=json.loads((OUT/'worker-result.json').read_text());s=json.loads((OUT/'supervisor-result.json').read_text());st=w['stats']
check(w['status']=='COMPLETE_IDENTITY_FRAME_NO_ADMISSION' and s['status']==w['status'] and s['worker_exit_code']==0,'worker_and_supervisor_terminal_agree')
check(st['gzip_eof_crc_verified'] and st['tar_end_blocks_verified'],'full_gzip_CRC_and_tar_EOF_receipts')
check(s['worker_result_sha256']==sha(OUT/'worker-result.json'),'supervisor_binds_exact_worker_receipt')
check(w['inventory_sha256']==sha(OUT/'inventory.sqlite3'),'independent_database_hash')
for n,h in json.loads((HERE/'code-pins.json').read_text())['sha256'].items():check(sha(HERE/n)==h,'final_code_pin_'+n)
d=sqlite3.connect('file:'+str((OUT/'inventory.sqlite3').resolve())+'?mode=ro',uri=True)
check(d.execute('pragma integrity_check').fetchone()[0]=='ok','independent_SQLite_integrity')
n,total=d.execute("select count(*),sum(json_extract(data,'$.record_bytes')) from records").fetchone()
check(n==st['encountered_records']==st['reconciled_stored_records'] and total==st['record_bytes'],'independent_record_count_and_byte_reconciliation')
held=oversize=0;members={};minordinal=1;locs={}
for ordinal,member,line,page,rev,payload in d.execute('select * from records order by ordinal'):
 r=json.loads(payload)
 assert ordinal==minordinal;minordinal+=1
 assert r['member_ordinal']==member and r['line']==line and r['archive_sha256']==w['archive_sha256']
 assert r['member_uncompressed_byte_offset']>=locs.get(member,0)
 locs[member]=r['member_uncompressed_byte_offset']+r['record_bytes']
 assert len(r['record_sha256'])==64 and r['record_bytes']>0 and r['training_admitted'] is False
 for key in ['html','wikitext']:
  h=r.get(key+'_sha256')
  if h is not None:assert len(h)==64 and r[key+'_UTF8_bytes']>=0
 held+=bool(r['identity_holds']);oversize+=r.get('hold')=='oversize_record_not_parsed'
 members[member]=members.get(member,0)+1
check(held==st['identity_held_records'] and oversize==st['oversize_records'],'all_rows_locations_source_hash_shape_and_hold_counts')
check(n<500000 and st['actual_decoded_bytes']<=12000000000 and len(st['members'])<=64,'record_decoded_member_bounds')
check(s['elapsed_seconds']<900 and s['peak_observed_process_tree_RSS_bytes']<=1000000000,'supervisor_elapsed_and_observed_RSS_bounds')
check(sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())<1000000000,'all_terminal_artifacts_output_bound')
check(all(x['new_admitted_documents']==0 and x['new_admitted_tokens']==0 for x in [w,s]),'zero_admission')
dups=d.execute('select page_id,count(*) from records where page_id is not null group by page_id having count(*)>1 order by count(*) desc,page_id').fetchall()
d.close()
r={'status':'PASS_COMPLETE_IDENTITY_FRAME_ONLY','check_count':len(checks),'checks':checks,'records':n,'record_bytes':total,'identity_held_records':held,'oversize_records':oversize,'records_by_member':members,'duplicate_page_ID_groups':len(dups),'duplicate_page_ID_excess_rows':sum(c-1 for _,c in dups),'duplicate_page_ID_example_groups':dups[:20],'inventory_sha256':sha(OUT/'inventory.sqlite3'),'worker_result_sha256':sha(OUT/'worker-result.json'),'supervisor_result_sha256':sha(OUT/'supervisor-result.json'),'new_admitted_documents':0,'new_admitted_tokens':0,'limitations':'No quality, eligibility, deduplication, rights-clearance or token-weight claim. Archive EOF/CRC from pinned reader receipt; independently rechecked SQLite and every compact identity row, not a second archive extraction.'}
p=OUT/'independent-terminal-verification.json'
with p.open('x') as f:f.write(json.dumps(r,indent=2)+'\n')
print(json.dumps(r,indent=2))
