"""Terminal recovery receipt/ledger/PID/stat verification. Never reads archive bodies."""
from pathlib import Path
import hashlib,json,os,sqlite3,fcntl,stat,re
B=Path(__file__).resolve().parent;D=B/'m2-intake/enwiki-native-full-XML-20260801-v3';P=B/'enwiki-native-full-acquisition-preparation-v3';O=B/'enwiki-recovery-v3-terminal-independent-verification-v1'
h=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run():
 O.mkdir(exist_ok=False);w=json.loads((D/'worker-result.json').read_text());s=json.loads((D/'supervisor-result.json').read_text());owner=json.loads((D/'ownership.json').read_text());profile=json.loads((P/'profile.json').read_text());copy=json.loads((D/'prefix-copy.json').read_text());oldD=B/'m2-intake/enwiki-native-full-XML-20260801-v2';old=json.loads((oldD/'worker-result.json').read_text());oldS=json.loads((oldD/'supervisor-result.json').read_text());oldOwner=json.loads((oldD/'ownership.json').read_text())
 assert h(P/'code-pins.json')==owner['code_pins_sha256'] and h(P/'profile.json')==owner['profile_sha256'];pins=json.loads((P/'code-pins.json').read_text())['sha256'];assert all(h(q)==v for q,v in pins.items())
 assert w['status']=='TERMINAL_PARTIAL_XML_NO_RETRY' and s['status']=='PARTIAL_XML_NO_RETRY' and s['worker_exit_code']==1 and s['worker_receipt_SHA256']==h(D/'worker-result.json') and s['independent_final_file_verification'] is None and not w['published_final_exists'];assert not(D/'enwiki-20260801-pages-articles-multistream.xml.bz2').exists()
 partial=D/'assembled.partial';ps=partial.stat();prefix=w['complete_recorded_prefix'];assert w['partial_bytes']==ps.st_size==prefix['bytes']==17988844772 and prefix['network_bytes']==1061174874 and prefix['prefix_copied_bytes']==16927669898 and prefix['bytes']==prefix['prefix_copied_bytes']+prefix['network_bytes'];assert w['prefix_hash_covers_entire_partial'] and prefix['bytes']<profile['expected_bytes'] and prefix['network_bytes']<profile['recovery']['remaining_bytes'];assert all(re.fullmatch('[0-9a-f]{'+str(n)+'}',prefix[k]) for k,n in [('SHA256',64),('SHA1',40),('MD5',32),('network_SHA256',64)])
 assert copy['new_copy_prefix_SHA256']==prefix['prefix_SHA256']==old['complete_recorded_prefix']['SHA256'];before=(oldD/'archive.partial').stat();assert copy['old_file_identity']==[getattr(before,k) for k in ['st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns']]
 head=json.loads((D/'response-headers.json').read_text());raw=bytes.fromhex(head['prefix_hex']);assert hashlib.sha256(raw).hexdigest()==head['headers_SHA256'] and head['status']==206 and not head['prefix_only'];headers={}
 for line in raw.decode('latin1').splitlines():k,v=line.split(':',1);headers.setdefault(k.casefold(),[]).append(v.strip())
 assert headers['content-range']==['bytes 16927669898-26668484994/26668484995'] and headers['content-length']==['9740815097'] and headers['etag']==['"6a738a16-63590c983"'] and headers.get('content-encoding',[]) in [[],['identity']]
 absent=[]
 for d in [owner,oldOwner]:
  for k in ['supervisor_pid','worker_pid']:
   try:os.kill(d[k],0)
   except ProcessLookupError:absent.append(d[k])
   else:raise AssertionError('owned_PID_still_present')
 assert s['elapsed_seconds']<7200 and owner['shared_start']+s['elapsed_seconds']<=profile['recovery']['original_monotonic_deadline'] and s['peak_observed_process_tree_RSS_bytes']<=1000000000
 ledgerroot=B/'m2-intake/charges'
 with (ledgerroot/'job.lock').open('rb') as f:
  fcntl.flock(f,fcntl.LOCK_SH|fcntl.LOCK_NB);fcntl.flock(f,fcntl.LOCK_UN)
 db=sqlite3.connect((ledgerroot/'ledger.sqlite').as_uri()+'?mode=ro',uri=True);row=db.execute('select charge,state,actual_bytes,body_sha256 from attempts where key=?',(owner['ledger_key'],)).fetchone();assert row[1:] ==('failed',None,None);charge=json.loads(row[0]);assert charge=={'requests':1,'body_bytes':9740815098,'rows':0,'output_bytes':26700000000};rows=db.execute('select charge,state,actual_bytes from attempts').fetchall();totals={k:sum(json.loads(r[0])[k] for r in rows) for k in ['requests','body_bytes','rows','output_bytes']};states={state:sum(r[1]==state for r in rows) for state in set(r[1] for r in rows)};db.close()
 assert totals['body_bytes']<=80000000000 and totals['output_bytes']<=64000000000
 report={'status':'PASS_TERMINAL_FAILED_RECOVERY_METADATA_LEDGER_AND_PID_CUSTODY_NO_BODY_REHASH','worker_receipt_SHA256':h(D/'worker-result.json'),'supervisor_receipt_SHA256':h(D/'supervisor-result.json'),'code_input_pins_verified':len(pins),'assembly_bytes':ps.st_size,'copied_old_prefix_bytes_not_newnetwork':16927669898,'new_failed_response_bytes_observed':1061174874,'source_local_worker_hash_covers_whole_terminal_assembly':prefix['SHA256'],'hash_scope':'Worker incremental prefixcopy+newresponse receipt bound to code/metadata/stat. No independent17.99GBrehash performed; not publisherverified wholearchive.','all_owned_worker_supervisor_PIDs_absent':absent,'global_exclusive_writer_lock_released':True,'failed_reservation_retained':charge,'cumulative_reserved':totals,'ledger_states_as_observed':states,'both_attempt_failures_unchanged':True,'original_v2_prefix_stat_copy_chain_unchanged':True,'full_publisher_MD5_SHA1_verified':False,'published_final_archive_exists':False,'no_retry_or_resume_authority':True,'source_body_bytes_read':0,'network_or_ledger_writes':0,'new_admissions':0};(O/'verification.json').write_text(json.dumps(report,indent=2)+'\n');(O/'manifest.json').write_text(json.dumps({'files':{'verification.json':h(O/'verification.json')}},indent=2)+'\n');print(h(O/'verification.json'),h(O/'manifest.json'))
if __name__=='__main__':run()
