import copy,hashlib,json,sqlite3,tempfile,fcntl,os
from pathlib import Path
import core,artifacts
N=0
def ok(v):
 global N;assert v;N+=1
def refuse(f):
 global N
 try:f()
 except (ValueError,KeyError,BlockingIOError):N+=1;return
 raise AssertionError('expected refusal')
profile={'expected_controller_PID':1234,'source_output':'/synthetic','producer_profile_SHA256':'a'*64,'producer_codepins_SHA256':'b'*64,'ledger_prefix':'pg-','records':[]}
binding={'status':'PARENT_COMPLETE_REAPED_PG300_RSYNC_BINDING','producer_exec_exit_code':0,'producer_reaped':True,'owned_processes_absent':True,'global_ledger_writer_lock_released':True,'controller_PID':1234,'producer_exec_session':53485,'source_output':'/synthetic','producer_profile_SHA256':'a'*64,'producer_codepins_SHA256':'b'*64,'terminal_SHA256':{n:'c'*64 for n in ['result.json','controller.json','inventory.json','ownership.json']}}
core.gate(profile,binding,lambda p:True);N+=1
for field,value in [('status','PARTIAL'),('producer_exec_exit_code',1),('producer_reaped',False),('owned_processes_absent',False),('global_ledger_writer_lock_released',False),('controller_PID',9999),('source_output','/wrong')]:
 b=copy.deepcopy(binding);b[field]=value;refuse(lambda:core.gate(profile,b,lambda p:True))
refuse(lambda:core.gate(profile,binding,lambda p:False))
rows=[];receipts=[]
for i in range(3):
 eid=i+1;r={'ordinal':i,'ebook_ID':eid,'source_relative_path':f'{eid}/pg{eid}.txt','source_row_SHA256':'d'*64,'family_component_ID':eid,'native_catalog_URL':f'https://example.invalid/{eid}'};rows.append(r);receipts.append({'ordinal':i,'ebook_ID':eid,'frozen_source_relative_path':r['source_relative_path'],'source_row_SHA256':r['source_row_SHA256'],'family_component_ID':eid,'native_catalog_URL':r['native_catalog_URL'],'charged_before_IO':True,'ledger_key':f'pg-body-{i:03}','result':{'status':core.COMPLETE,'can_continue':True},'native_transport':{'child_PID':100+i,'child_reaped':True,'received_bytes':10,'received_SHA256':'e'*64,'remote_started':True,'remote_start_monotonic':100+i*2}})
profile['records']=rows;res={'status':'COMPLETE_FINITE300_ATTEMPTS_RAW_DISCOVERY_NO_ADMISSION','planned':3,'attempted':3,'unattempted_frozen_ordinals':[],'completed':3,'independent_failed':0,'charged_attempts':3,'received_application_bytes':30,'actual_source_connections_started':3,'attempt_results':[{'ordinal':i,'ebook_ID':i+1,'status':core.COMPLETE,'receipt':f'attempt-{i:03}/receipt.json'} for i in range(3)]};control={'status':'COMPLETE_FINITE_PROFILE_TERMINAL_RAW_DISCOVERY_NO_ADMISSION','owned_children_controlled_reaped':True};own={'controller_PID':1234,'active_owned_PIDs':{}}
ok(core.attempts(profile,res,control,own,receipts,lambda p:True)['completed_raw_discovery']==3)
for field,value in [('child_reaped',False),('received_bytes',2500001),('remote_start_monotonic',101)]:
 rr=copy.deepcopy(receipts);rr[1]['native_transport'][field]=value;refuse(lambda:core.attempts(profile,res,control,own,rr,lambda p:True))
refuse(lambda:core.attempts(profile,res,control,own,receipts,lambda p:p!=101))
with tempfile.TemporaryDirectory() as tmp:
 d=Path(tmp).resolve();ld=d/'ledger';ld.mkdir();(ld/'job.lock').write_bytes(b'');contract={'version':1,'scope':'fixture','limits':{'requests':1000,'body_bytes':80000000000,'rows':100000000,'output_bytes':80000000000},'wall_seconds':100};profile['ledger_root']=str(ld);profile['ledger_contract']=contract;db=sqlite3.connect(ld/'ledger.sqlite');db.execute('CREATE TABLE job(identity TEXT,root TEXT,contract TEXT,deadline REAL)');db.execute('CREATE TABLE attempts(key TEXT,charge TEXT,state TEXT,actual_bytes INTEGER,body_sha256 TEXT)');db.execute('INSERT INTO job VALUES(?,?,?,?)',(core.digest(contract),str(ld),json.dumps(contract),9999999999));db.execute('INSERT INTO attempts VALUES(?,?,?,?,?)',('pg-output',json.dumps({'requests':0,'body_bytes':0,'rows':0,'output_bytes':800000000}),'complete',0,hashlib.sha256(b'').hexdigest()))
 for i in range(3):db.execute('INSERT INTO attempts VALUES(?,?,?,?,?)',(f'pg-body-{i:03}',json.dumps({'requests':1,'body_bytes':2500000,'rows':0,'output_bytes':0}),'complete',10,'e'*64))
 db.commit();before=(ld/'ledger.sqlite').read_bytes();snapshot=core.ledger(profile,receipts,lambda:None);ok(snapshot['owned_charged_body_bytes']==7500000);ok((ld/'ledger.sqlite').read_bytes()==before)
 fd=os.open(ld/'job.lock',os.O_RDONLY);fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);refuse(lambda:core.ledger(profile,receipts,lambda:None));fcntl.flock(fd,fcntl.LOCK_UN);os.close(fd)
 db.execute("UPDATE attempts SET state='pending' WHERE key='pg-body-001'");db.commit();refuse(lambda:core.ledger(profile,receipts,lambda:None));db.close()
 out=d/'source';out.mkdir();text=b'[EBook #1]\nComplete original text.\n';(out/'book.txt').write_bytes(text)
 for n in ['result.json','inventory.json','controller.json']:(out/n).write_bytes(b'{}')
 inv={'artifacts':[{'path':'book.txt','bytes':len(text),'SHA256':hashlib.sha256(text).hexdigest()}],'all_output_bytes_including_reserved_slots':len(text)+6};success={'book.txt':{'ebook_ID':1,'bytes':len(text),'SHA256':hashlib.sha256(text).hexdigest()}}
 a=artifacts.verify(out,inv,success,lambda:None);ok(a['raw_complete_file_diagnostics'][0]['strict_UTF8_whole_file']);ok(a['raw_complete_file_diagnostics'][0]['publisher_IDs_first16384bytes']==[1]);ok(not a['raw_complete_file_diagnostics'][0]['rights_originalEnglish_quality_clearance'])
 (out/'book.txt').write_bytes(b'X'*len(text));refuse(lambda:artifacts.verify(out,inv,success,lambda:None))
print(json.dumps({'status':'PASS_SYNTHETIC_ONLY','controls':N,'actual_PG_output_body_or_globalledger_reads':0}))
