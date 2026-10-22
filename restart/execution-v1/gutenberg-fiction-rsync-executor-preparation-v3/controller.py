"""Finite serial controller; caller holds durable global IntakeLedger lock."""
import hashlib,json,os,stat,threading,time
from pathlib import Path
import transport,validate
RECEIVED=2500000;OUTPUT=800000000;BOOKS=300
clk=lambda:time.clock_gettime(time.CLOCK_MONOTONIC)
class PolicyStop(Exception):pass
def encode(obj):return (json.dumps(obj,ensure_ascii=True,sort_keys=True,separators=(',',':'))+'\n').encode()
def write(out,name,obj,check,cap=160000):
 b=encode(obj)
 if len(b)>cap:raise PolicyStop('metadata_file_cap')
 check(extra=len(b));p=Path(out)/name
 with p.open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
def finish_pending(ledger,key,raw=None):
 # Never turn a completed/unknown attempt into a new operation or refund.
 row=ledger.db.execute('SELECT state FROM attempts WHERE key=?',(key,)).fetchone()
 if row is None:raise PolicyStop('missing_precharge')
 if row[0]=='pending':ledger.finish(key,raw=raw)
 elif row[0] not in {'complete','failed'}:raise PolicyStop('invalid_ledger_terminal')
def inventory(out,check):
 entries=[];total=0
 for parent,dirs,files in os.walk(out,followlinks=False):
  for name in dirs:
   p=Path(parent)/name
   if p.is_symlink():raise PolicyStop('output_symlink')
  for name in files:
   p=Path(parent)/name;s=p.stat(follow_symlinks=False)
   if not stat.S_ISREG(s.st_mode):raise PolicyStop('output_special_file')
   rel=str(p.relative_to(out));total+=s.st_size
   if rel in {'result.json','inventory.json','controller.json'}:continue
   digest=hashlib.sha256()
   with p.open('rb') as f:
    for b in iter(lambda:f.read(1048576),b''):digest.update(b);check()
   if p.stat(follow_symlinks=False)!=s:raise PolicyStop('output_changed_during_hash')
   entries.append({'path':rel,'bytes':s.st_size,'SHA256':digest.hexdigest()})
 return {'artifacts':entries,'all_output_bytes_including_reserved_slots':total,'terminal_slots_excluded_from_hashes':['result.json','inventory.json','controller.json']}
def execute(profile,out,ledger,check,transfer=transport.transfer,pace=None):
 out=Path(out);records=profile['records'];prefix=profile['ledger_prefix'];results=[];consecutive=0;received_total=0;remote_attempts=0;last_start=None;fatal=None;states=[{'ordinal':i,'ebook_ID':r['ebook_ID'],'state':'UNATTEMPTED'} for i,r in enumerate(records)];main_thread=threading.get_ident()
 if len(records)>300:raise PolicyStop('frozen_record_cap')
 try:
  for i,row in enumerate(records):
   check();eid=row['ebook_ID'];relative=transport.path_for(eid)
   if row['ordinal']!=i or row['source_relative_path']!=relative:raise PolicyStop('exact_manifest_order_and_path')
   attempt=f'attempt-{i:03}';attemptdir=out/attempt;key=prefix+f'body-{i:03}';charged=False;receipt=None;rawprotocol=None;result=None
   try:
    ledger.reserve(key,requests=1,body_bytes=RECEIVED);charged=True;states[i]['state']='CHARGED_BEFORE_SOURCE_IO'
    # Charge before even the owned loopback listener/files; source upstream connects at mostonce.
    check(extra=2600000);attemptdir.mkdir();stage=attemptdir/'raw';stage.mkdir();filelist=attemptdir/'file.declaration';filelist.write_bytes(relative.encode()+b'\0')
    if last_start is not None:
     remain=max(0,2-(clk()-last_start))
     if pace:pace(remain)
     elif remain:time.sleep(remain)
    check();last_start=clk();deadline=last_start+55;remote_attempts+=1;states[i]['state']='SOURCE_TRANSFER_ENTERED_PENDING_RECEIPT'
    def callback(pid=None):
     # Relay/DNS runs in owned thread; NEVER access SQLite or resource subprocesses there.
     if clk()>=deadline:raise transport.IndependentTimeout('per_file_absolute_deadline')
     if pid is not None:check(pid=pid,register_only=True,role='native' if threading.get_ident()==main_thread else 'resolver')
     if threading.get_ident()==main_thread:check()
    callback.release=lambda pid:check(pid=pid,unregister_only=True)
    receipt,rawprotocol=transfer(eid,filelist,stage,deadline,callback)
    received_total+=receipt['received_bytes']
    if received_total>750000000 or receipt['received_bytes']>RECEIVED or len(rawprotocol)!=receipt['received_bytes']:raise PolicyStop('exact_received_total_cap')
    result=validate.result(stage,eid,receipt)
    if result['status']=='COMPLETE_RAW_DISCOVERY_NOT_ADMITTED':finish_pending(ledger,key,rawprotocol)
    else:finish_pending(ledger,key,None)
   except transport.IndependentTimeout as exc:
    receipt=getattr(exc,'transport_receipt',{'remote_started':False,'received_bytes':0});received_total+=receipt.get('received_bytes',0);result={'status':'INDEPENDENT_SOURCE_TIMEOUT_NO_RETRY','can_continue':True};finish_pending(ledger,key,None)
   except BaseException as exc:
    receipt=getattr(exc,'transport_receipt',receipt);result={'status':'FATAL_PROFILE_STOP_NO_RETRY','error_class':type(exc).__name__,'error':str(exc)[:1000]}
    if charged:finish_pending(ledger,key,None)
    fatal=exc
   # Raw failed native files and any temporary regularfiles remain in own staging; no deletion.
   states[i]['state']=result['status']
   states[i]['new_charge_recorded']=charged
   report={'ordinal':i,'ebook_ID':eid,'frozen_source_relative_path':relative,'native_catalog_URL':row['native_catalog_URL'],'source_row_SHA256':row['source_row_SHA256'],'family_component_ID':row['family_component_ID'],'ledger_key':key,'charged_before_IO':charged,'source_trust':'official_documented_native_UNENCRYPTED_rsync_no_TLS_or_publisherSHA','native_transport':receipt,'result':result,'source_current_version_equals_catalog_claimed':False,'new_admitted_documents':0}
   if receipt and receipt.get('remote_start_monotonic') is not None:last_start=receipt['remote_start_monotonic']
   if not attemptdir.exists():
    results.append(report)
    raise fatal or PolicyStop('attempt_setup_failed')
   check();write(out,attempt+'/receipt.json',report,check);results.append(report)
   if fatal is not None:raise fatal
   consecutive,advance=validate.next_state(consecutive,result)
   if not advance:raise PolicyStop('three_consecutive_independent_source_failures')
  return {'status':'COMPLETE_FINITE300_ATTEMPTS_RAW_DISCOVERY_NO_ADMISSION','planned':len(records),'attempted':len(results),'completed':sum(r['result']['status']=='COMPLETE_RAW_DISCOVERY_NOT_ADMITTED' for r in results),'independent_failed':sum(r['result']['status']!='COMPLETE_RAW_DISCOVERY_NOT_ADMITTED' for r in results),'unattempted_frozen_ordinals':[],'received_application_bytes':received_total,'charged_attempts':remote_attempts,'actual_source_connections_started':sum(bool(r['native_transport'] and r['native_transport'].get('remote_started')) for r in results),'attempt_results':[{'ordinal':r['ordinal'],'ebook_ID':r['ebook_ID'],'status':r['result']['status'],'receipt':f"attempt-{r['ordinal']:03}/receipt.json"} for r in results],'new_admitted_documents':0,'new_admitted_tokens':0}
 except BaseException as exc:
  exc.profile_partial={'planned':len(records),'attempted_with_saved_receipts':len(results),'received_application_bytes_reported':received_total,'consecutive_independent_failures':consecutive,'attempt_results':[{'ordinal':r['ordinal'],'ebook_ID':r['ebook_ID'],'status':r['result']['status']} for r in results],'per_planned_record_states':states,'unattempted_ordinals':[x['ordinal'] for x in states if x['state']=='UNATTEMPTED'],'charges_retained_no_refunds':True}
  raise
