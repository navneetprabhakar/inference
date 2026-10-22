"""Independent post-terminal raw-source/ledger/spacing/frame verification."""
import fcntl,hashlib,json,os,sqlite3,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;EXEC=HERE.parent;PREP=EXEC/'openstax-native-source-preparation-v2'
sys.path.insert(0,str(PREP));import acquire as a
EXPECTED_PINS='cc88641ad05d1a121bc628655fb2c237a679443e79cc28896e45fc0aea4a3459'
policy,pin=a.pins(EXPECTED_PINS);out=a.DEST
checks={};w=json.loads((out/'worker-result.json').read_text());s=json.loads((out/'supervisor-result.json').read_text());pre=json.loads((out/'preflight.json').read_text());frame=(out/'source-frame.json').read_bytes()
checks['terminal_worker_supervisor_complete']=w['status']=='COMPLETE162_NATIVE_SOURCE_FILES_NOT_CLEARED_OR_ADMITTED' and s['status']=='COMPLETE' and s['worker_exit_code']==0 and not s['external_timeout'] and s['elapsed_seconds']<600 and w['elapsed_seconds']<570
checks['exact_parent_reviewed_manifest_main_worker_binding']=pre['parent_reviewed_code_pins_SHA256']==EXPECTED_PINS and pre['code_pins']==pin
checks['supervisor_worker_result_hash']=s['worker_result_SHA256']==a.sha((out/'worker-result.json').read_bytes())
checks['complete_exact_native_source_frame']=a.sha(frame)==a.EXPECTED_POLICY_SHA==w['source_frame_SHA256'] and json.loads(frame)==policy
conn=sqlite3.connect('file:'+str((a.ROOT/'charges/ledger.sqlite').resolve())+'?mode=ro',uri=True);receipts=[];actual=[];charged=[];request_starts=[];artifacts=[]
try:
 for index,item in enumerate(policy['items']):
  mid=item['module_ID'];source=out/(mid+'.cnxml');raw=source.read_bytes();rfile=out/f'response-{index:03d}.receipt.json';qfile=out/f'request-{index:03d}.json';r=json.loads(rfile.read_text());q=json.loads(qfile.read_text());receipts.append(r)
  assert len(raw)==item['expected_bytes']==r['body_bytes'] and a.git_blob(raw)==item['expected_Git_blob_SHA1']==r['Git_blob_SHA1'] and a.sha(raw)==r['body_SHA256'] and r['expected_source_match'],('source mismatch',mid)
  assert r['module_ID']==mid and r['native_path']==item['native_path'] and r['collection_appearances']==item['collection_appearances'] and r['url']==r['effective_URL']==q['url']==item['url'],('sourceidentity',mid)
  assert r['strict_TLS_certificate_hostname_validation'] and not r['redirect'] and r['charged_before_IO'] and q['charged_before_IO'] and q['pre_IO_reservation_shared_clock']<=r['request_start_shared_clock'],('requestguard',mid)
  assert r['license_and_quality_review']=='PENDING_NOT_CLEARED' and not r['training_admitted']
  key=f'openstax-worldhistory-2024-native162-v1-{mid}';assert r['key']==q['key']==key
  row=conn.execute('select charge,state,actual_bytes,body_sha256 from attempts where key=?',(key,)).fetchone();charge=json.loads(row[0]);assert row[1]=='complete' and row[2]==len(raw) and row[3]==a.sha(raw)
  assert charge['requests']==charge['rows']==1 and charge['body_bytes']==item['body_cap']==item['expected_bytes']+1 and charge['output_bytes']==(a.CAP if index==0 else 0)
  actual.append(row[2]);charged.append(charge);request_starts.append(r['request_start_shared_clock']);artifacts.append({'module_ID':mid,'bytes':len(raw),'raw_SHA256':a.sha(raw),'Git_blob_SHA1':a.git_blob(raw),'receipt_SHA256':a.sha(rfile.read_bytes()),'request_SHA256':a.sha(qfile.read_bytes())})
 checks['all162_exact_bytes_Gitblobs_localSHA_and_receipts']=len(artifacts)==162
 checks['exact162_complete_durable_ledger_attempts_no_retry']=conn.execute("select count(*) from attempts where key like 'openstax-worldhistory-2024-native162-v1-%'").fetchone()[0]==162
finally:conn.close()
checks['exact_byte_request_row_output_totals']=sum(actual)==w['actual_response_bytes']==5565778 and sum(x['body_bytes'] for x in charged)==w['reserved_response_bytes']==5565940 and sum(x['requests'] for x in charged)==sum(x['rows'] for x in charged)==162 and sum(x['output_bytes'] for x in charged)==32000000
spacing=[b-a_ for a_,b in zip(request_starts,request_starts[1:])]
checks['actual_request_starts_serial_at_least1second']=len(spacing)==161 and min(spacing)>=1
checks['receipt_list_hash_matches_worker']=a.sha(json.dumps(receipts,sort_keys=True).encode())==w['receipt_manifest_SHA256']
checks['exact162_files_no_partial_or_failure_artifacts']=len(list(out.glob('*.cnxml')))==162 and not list(out.glob('*.partial')) and not list(out.glob('*failure*'))
checks['three_shared_appearances_not_duplicate_source_downloads']=sum(len(i['collection_appearances']) for i in policy['items'])==165 and len({i['module_ID'] for i in policy['items']})==162
checks['aggregate_output_bound']=a.output_size()<a.CAP
checks['zero_admission_or_clearance']=w['new_admitted_documents']==w['new_admitted_tokens']==w['models_initialized']==0 and not w['rights_and_quality_clearance']
with (a.ROOT/'charges/job.lock').open('r+') as lock:
 try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:checks['global_ledger_released']=False
 else:checks['global_ledger_released']=True;fcntl.flock(lock,fcntl.LOCK_UN)
try:os.kill(s['worker_pid'],0)
except ProcessLookupError:checks['worker_gone']=True
else:checks['worker_gone']=False
assert all(checks.values()),checks
manifest=(''.join(json.dumps(x,sort_keys=True)+'\n' for x in artifacts)).encode();report={'status':'PASS_COMPLETE162_RAW_NATIVE_SOURCE_ACQUISITION_ONLY','checks':checks,'check_count':len(checks),'source_files':162,'collection_appearances':165,'actual_response_body_bytes':sum(actual),'conservative_reserved_body_bytes':sum(x['body_bytes'] for x in charged),'minimum_actual_request_start_spacing_seconds':min(spacing),'supervisor_elapsed_seconds':s['elapsed_seconds'],'worker_elapsed_seconds':w['elapsed_seconds'],'raw_source_manifest_SHA256':a.sha(manifest),'worker_result_SHA256':a.sha((out/'worker-result.json').read_bytes()),'supervisor_result_SHA256':a.sha((out/'supervisor-result.json').read_bytes()),'new_admitted_documents':0,'new_admitted_tokens':0,'scope':'Complete exact162-file byte/sourceidentity acquisition; no modulelicense/objectrights, language/semantic/factual/dedup/protected/split/token clearance.'}
a.ensure_output(len(manifest)+len(json.dumps(report).encode())+10000)
for name,data in [('independent-raw-source-manifest.jsonl',manifest),('independent-terminal-verification.json',(json.dumps(report,indent=2)+'\n').encode())]:
 with (out/name).open('xb') as f:f.write(data)
print(json.dumps(report,indent=2));print('REPORT_SHA256',a.sha((out/'independent-terminal-verification.json').read_bytes()))
