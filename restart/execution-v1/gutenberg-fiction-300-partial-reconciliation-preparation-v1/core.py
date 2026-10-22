"""Read-only terminal verification. No networking or IntakeLedger construction."""
import collections,fcntl,hashlib,json,os,re,sqlite3,stat
from pathlib import Path

COMPLETE='COMPLETE_RAW_DISCOVERY_NOT_ADMITTED'
RECOGNIZED={COMPLETE,'INDEPENDENT_SOURCE_MISSING_NO_RETRY','INDEPENDENT_SOURCE_OVERSIZE_SKIPPED_NO_RETRY','INDEPENDENT_SOURCE_TIMEOUT_NO_RETRY'}
def require(v,m):
 if not v:raise ValueError(m)
def digest(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def gate(profile,binding,absent):
 require(binding['status']=='PARENT_PARTIAL_REAPED_PG300_RSYNC_RECONCILIATION_BINDING','parent_complete_binding')
 require(binding['producer_exec_exit_code']==1 and binding['producer_reaped'] is True and binding['owned_processes_absent'] is True and binding['global_ledger_writer_lock_released'] is True,'parent_reaped_released')
 require(binding['controller_PID']==profile['expected_controller_PID'] and binding['producer_exec_session']==53485,'exact_parent_process_binding')
 require(binding['source_output']==profile['source_output'] and binding['producer_profile_SHA256']==profile['producer_profile_SHA256'] and binding['producer_codepins_SHA256']==profile['producer_codepins_SHA256'],'exact_source_policy_binding')
 require(absent(binding['controller_PID']),'controller_still_alive')
 for n in ['result.json','controller.json','inventory.json','ownership.json']:require(re.fullmatch('[0-9a-f]{64}',binding['terminal_SHA256'][n]) is not None,'external_terminal_SHA')

def attempts(profile,result,control,ownership,receipts,absent):
 rows=profile['records'];require(result['status']=='PARTIAL_FINITE_PROFILE_NO_RETRY_NO_ADMISSION' and result['error_class']=='PolicyStop' and result['error']=='output_changed_during_hash' and result['partial'] is None and control['status']=='PARTIAL_FINITE_PROFILE_PRESERVED_NO_RETRY' and control['charges_retained'] is True,'exact_original_failure_preserved')
 require(control['owned_children_cleanup_returned'] is True and not ownership['active_owned_PIDs'] and absent(ownership['controller_PID']),'no_active_ownership')
 require(len(rows)==len(receipts),'exact_planned_attempts')
 successes=0;received=0;connections=0;consecutive=0;laststart=None;knownpids=set();summary=[]
 for i,(r,receipt) in enumerate(zip(rows,receipts)):
  eid=r['ebook_ID'];expected=f'{eid}/pg{eid}.txt';require(r['ordinal']==i and r['source_relative_path']==expected,'frozen_manifest')
  require((receipt['ordinal'],receipt['ebook_ID'],receipt['frozen_source_relative_path'],receipt['source_row_SHA256'],receipt['family_component_ID'],receipt['native_catalog_URL'])==(i,eid,expected,r['source_row_SHA256'],r['family_component_ID'],r['native_catalog_URL']),'receipt_frozen_source_identity')
  require(receipt['charged_before_IO'] is True and receipt['ledger_key']==profile['ledger_prefix']+f'body-{i:03}','charged_attempt_key')
  status=receipt['result']['status'];require(status==COMPLETE and receipt['result']['can_continue'] is True,'finite_recognized_outcome')
  native=receipt['native_transport'];require(isinstance(native,dict) and native.get('child_reaped') is True,'native_child_reaped')
  child=native.get('child_PID')
  if child is not None:require(type(child)==int and child>0,'native_PID');knownpids.add(child)
  n=native['received_bytes'];require(type(n)==int and 0<=n<=2500000 and re.fullmatch('[0-9a-f]{64}',native['received_SHA256']) is not None,'received_protocol_bound_hash')
  received+=n;connections+=bool(native['remote_started'])
  start=native.get('remote_start_monotonic')
  if native['remote_started']:
   require(isinstance(start,(int,float)) and start>0 and (laststart is None or start-laststart>=2),'serial_source_pacing');laststart=start
  if status==COMPLETE:successes+=1;consecutive=0
  else:consecutive+=1;require(consecutive<3,'three_failures_cannot_be_complete')
  expected_summary={'ordinal':i,'ebook_ID':eid,'status':status,'receipt':f'attempt-{i:03}/receipt.json'}
  summary.append({'ordinal':i,'ebook_ID':eid,'status':status,'received_application_bytes':n,'native_child_PID':child})
 require(successes==len(rows) and connections==len(rows) and received<=750000000,'independently_derived_complete300_receipt_accounting')
 require(all(absent(p) for p in knownpids),'native_PID_currently_alive_or_reused_refuse')
 return {'planned':len(rows),'completed_raw_discovery':successes,'recognized_independent_failures':len(rows)-successes,'received_application_bytes':received,'source_connections_started':connections,'all_known_native_PIDs_absent':True,'attempts':summary,'historical_resolver_identity_limit':'Individual resolver stamps not retained after ownership release; producer cleanup and external parent owned-tree proof inherited, not reconstructed.'}

def ledger(profile,receipts,check):
 """Acquire existing lock SH/RO only; fail busy, never construct a writer."""
 root=Path(profile['ledger_root']);lock=root/'job.lock';dbp=root/'ledger.sqlite'
 require(not lock.is_symlink() and not dbp.is_symlink() and lock.is_file() and dbp.is_file(),'existing_regular_ledger_paths')
 fd=os.open(lock,os.O_RDONLY|os.O_NOFOLLOW);db=None
 try:
  fcntl.flock(fd,fcntl.LOCK_SH|fcntl.LOCK_NB)
  db=sqlite3.connect(dbp.as_uri()+'?mode=ro',uri=True,isolation_level=None);db.execute('PRAGMA query_only=ON');db.execute('BEGIN');db.set_progress_handler(lambda:(check() or 0),10000)
  job=db.execute('SELECT identity,root,contract,deadline FROM job').fetchall();require(len(job)==1 and job[0][1]==str(root) and json.loads(job[0][2])==profile['ledger_contract'] and job[0][0]==digest(profile['ledger_contract']),'existing_global_contract')
  got=db.execute('SELECT key,charge,state,actual_bytes,body_sha256 FROM attempts WHERE substr(key,1,?)=? ORDER BY key',(len(profile['ledger_prefix']),profile['ledger_prefix'])).fetchall();by={r[0]:r for r in got};require(len(by)==len(receipts)+1,'exact_owned_ledger_key_count')
  out=by.pop(profile['ledger_prefix']+'output');require(json.loads(out[1])=={'requests':0,'body_bytes':0,'rows':0,'output_bytes':800000000} and out[2:] == ('failed',None,None),'output_allocation_terminal_no_refund')
  states=collections.Counter()
  for i,r in enumerate(receipts):
   check();a=by.pop(profile['ledger_prefix']+f'body-{i:03}');require(json.loads(a[1])=={'requests':1,'body_bytes':2500000,'rows':0,'output_bytes':0},'full_precharges_retained')
   if r['result']['status']==COMPLETE:require(a[2:] == ('complete',r['native_transport']['received_bytes'],r['native_transport']['received_SHA256']),'successful_protocol_ledger_receipt')
   else:require(a[2:]==('failed',None,None),'failed_conservative_no_refund')
   states[a[2]]+=1
  require(not by,'unknown_ledger_attempt')
  totals={k:0 for k in ['requests','body_bytes','rows','output_bytes']}
  for raw, in db.execute('SELECT charge FROM attempts'):
   check()
   for k,v in json.loads(raw).items():totals[k]+=v
  require(all(totals[k]<=profile['ledger_contract']['limits'][k] for k in totals),'global_limits')
  return {'status':'READ_ONLY_TRANSACTION_SHARED_LOCK_AFTER_WRITER_RELEASE','owned_requests':len(receipts),'owned_charged_body_bytes':len(receipts)*2500000,'owned_charged_output_bytes':800000000,'owned_body_terminal_states':dict(states),'original_output_allocation_state':'failed_full_charge_retained','asof_global_conservative_totals':totals,'global_deadline_epoch':job[0][3],'writer_or_refund_performed':False,'plaintext_SHA_is_not_protocol_SHA':True}
 finally:
  if db is not None:db.close()
  fcntl.flock(fd,fcntl.LOCK_UN);os.close(fd)
