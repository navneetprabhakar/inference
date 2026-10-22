"""One offline, exact-selected-row native source capture. No network/model APIs."""
import argparse,hashlib,json,os,pathlib,re,shutil,signal,subprocess,sys,time
from lxml import etree
import capture_core as core
from xml.parsers.expat import ExpatError
HERE=pathlib.Path(__file__).resolve().parent;BASE=HERE.parent;ROOT=BASE/'m2-intake';SOURCE=ROOT/'enwiki-native-20row-ranges-20260801-v2';PREP=BASE/'enwiki-native-range-preparation-v2';OUT=ROOT/'enwiki-native-20row-capture-v1';FREE=53474836480
SLOTS={'result.json':65536,'supervisor.json':16384}
def clk():return time.clock_gettime(time.CLOCK_MONOTONIC)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def size(p):return sum(f.stat().st_size for f in p.rglob('*') if f.is_file())
def inventory():
 paths=[HERE/n for n in ['capture.py','capture_core.py','checks.py','code_guard.py','profile.json']]+[PREP/'selection-freeze.json',PREP/'profile.json',SOURCE/'worker-result.json',SOURCE/'supervisor-result.json',BASE/'disk-budget.json',pathlib.Path(etree.__file__)]
 paths += [SOURCE/f'range-{i:02d}-{suffix}.json' for i in range(20) for suffix in ['request','headers','receipt']]
 paths += [SOURCE/f'range-{i:02d}.bz2' for i in range(20)]
 return {str(p.resolve()) for p in paths}
def verify(code,prof):
 import code_guard;code_guard.verify(code)
 if sha(HERE/'profile.json')!=prof:raise ValueError('external_profile_pin')
 p=json.loads((HERE/'profile.json').read_text());w=json.loads((SOURCE/'worker-result.json').read_text());s=json.loads((SOURCE/'supervisor-result.json').read_text());plan=json.loads((PREP/'selection-freeze.json').read_text())
 if p['limits']!=core.LIMITS or p['source_output']!=str(SOURCE) or w['status']!='COMPLETE_BOUNDED_NATIVE_RANGE_DISCOVERY_NO_ADMISSION' or s['status']!='COMPLETE_NATIVE_RANGE_DISCOVERY_NO_ADMISSION' or s['worker_exit_code']!=0 or s['worker_receipt_sha256']!=sha(SOURCE/'worker-result.json') or len(w['completed_ranges'])!=20 or plan['selected_row_count']!=20:raise ValueError('exact_complete20_transport_chain')
 if w['publisher_XML_checksum_verified'] is not False or w['XML_parser_created'] is not False:raise ValueError('transport_scope')
 for i,(b,r) in enumerate(zip(plan['distinct_ranges'],w['completed_ranges'])):
  receipt=json.loads((SOURCE/f'range-{i:02d}-receipt.json').read_text())
  if receipt!=r or r['file']!=f'range-{i:02d}.bz2' or r['Range']!=b['Range'] or r['URL']!=plan['URL'] or r['bytes']!=b['bytes'] or r['local_SHA256']!=sha(SOURCE/r['file']) or r['selected_row_ordinals']!=b['selected_row_ordinals']:raise ValueError('source_range_receipt_identity')
 return plan,w

def terminal(name,obj):
 b=(json.dumps(obj,indent=2)+'\n').encode();n=SLOTS[name]
 if len(b)>n:raise ValueError('terminal_slot')
 with (OUT/name).open('r+b') as f:f.write(b+b' '*(n-len(b)));f.flush();os.fsync(f.fileno())
def write(name,data):
 b=data if isinstance(data,bytes) else (json.dumps(data,indent=2,ensure_ascii=False)+'\n').encode()
 if size(OUT)+len(b)>16000000-1048576:raise ValueError('evidence_prewrite_cap')
 if shutil.disk_usage(ROOT).free<FREE+len(b):raise ValueError('protected_disk_floor')
 with (OUT/name).open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
def worker(a):
 plan,w=verify(a.code_pins_sha256,a.profile_sha256);start=float(a.start);decisions=[];blocks=[];total=0
 if os.getppid()!=a.supervisor_pid:raise ValueError('parent_identity')
 def check():
  if clk()-start>=55:raise TimeoutError('work55seconds')
 try:
  write('all20-frozen-index-selection.json',plan)
  for i,(block,receipt) in enumerate(zip(plan['distinct_ranges'],w['completed_ranges'])):
   check();rows=[r for r in plan['selected_rows'] if r['row_ordinal'] in block['selected_row_ordinals']];progress={'decoded_bytes':0};context={'range':receipt,'index_selected_rows_in_block':len(rows),'other_pages_are_transport_context_not_quality_sample':True}
   try:
    decoded,eof=core.decode((SOURCE/receipt['file']).read_bytes(),100000000-total,check,progress);total+=progress['decoded_bytes'];progress['decoded_bytes']=0
    context.update(eof);context['decoded_SHA256']=core.sha(decoded);pages,spans=core.page_spans(decoded);context['strict_XML_pages_co_read']=len(pages)
    for row in rows:
     matches=[]
     for page,span in zip(pages,spans):
      ns=etree.QName(page).namespace;tag=('{'+ns+'}id') if ns else 'id';ids=page.findall(tag)
      if len(ids)==1 and ids[0].text==str(row['page_ID_observed']):matches.append((page,span))
     if len(matches)!=1:
      decisions.append({'selected_index_row':row,'source_range':receipt,'status':'HELD_NATIVE_DISCOVERY','holds':['missing_or_duplicate_selected_direct_page_ID'],'matching_page_count':len(matches),'native_revision':None,'source_text':None});continue
     page,span=matches[0];meta,text=core.fields(page,span,decoded,row);meta['source_range']=receipt;stem='row-'+str(row['row_ordinal']);native=decoded[span[0]:span[1]]
     # A selected unit that cannot fit is retained as a hold; no replacement.
     required=len(native)+(len(text) if text is not None else 0)+len(json.dumps(meta,ensure_ascii=False).encode())+4096
     if size(OUT)+required>16000000-1048576:
      meta['holds'].append('selected_native_evidence_output_capacity_hold');meta['status']='HELD_NATIVE_DISCOVERY';meta['native_evidence_preserved']=False
     else:
      write(stem+'.native-page.xml',native)
      if text is not None:write(stem+'.source-text.utf8',text)
      meta['native_evidence_preserved']=True;meta['native_XML_file']=stem+'.native-page.xml';meta['source_text_file']=stem+'.source-text.utf8' if text is not None else None
     write(stem+'.json',meta);decisions.append(meta)
   except (ValueError,etree.XMLSyntaxError, ExpatError) as e:
    total+=progress['decoded_bytes'];context['hold']=type(e).__name__+':'+str(e)[:1000]
    for row in rows:decisions.append({'selected_index_row':row,'source_range':receipt,'status':'HELD_NATIVE_DISCOVERY','holds':['range_BZ2_XML_or_decoded_capacity_failure'],'diagnostic':context['hold']})
   blocks.append(context)
  if len(decisions)!=20 or sorted(d['selected_index_row']['row_ordinal'] for d in decisions)!=sorted(r['row_ordinal'] for r in plan['selected_rows']):raise ValueError('exact20_no_replacement_decision_reconciliation')
  verify(a.code_pins_sha256,a.profile_sha256)
  write('all20-native-decisions.json',decisions);write('block-diagnostics.json',blocks)
  terminal('result.json',{'status':'COMPLETE_SELECTED_NATIVE_SOURCE_DISCOVERY_NO_ADMISSION','selected_rows':20,'decisions':len(decisions),'held_rows':sum(bool(d.get('holds')) for d in decisions),'pending_quality_rights_review_rows':sum(not bool(d.get('holds')) for d in decisions),'decoded_bytes_including_failed_attempts':total,'block_count':len(blocks),'elapsed_seconds':clk()-start,'source_inputs_unchanged':True,'source_fullarchive_publisher_checksum_verified':False,'no_namespace_invention':True,'all_other_pages_are_transport_context_only':True,'new_admitted_documents':0,'new_admitted_tokens':0,'network_requests':0,'models_initialized':0,'decisions_SHA256':sha(OUT/'all20-native-decisions.json')})
 except BaseException as e:
  terminal('result.json',{'status':'TERMINAL_PARTIAL_NATIVE_CAPTURE_NO_RETRY','error':type(e).__name__+':'+str(e)[:1500],'completed_decisions':len(decisions),'decoded_bytes':total,'new_admitted_documents':0,'new_admitted_tokens':0});raise

def kill(child):
 if child.poll() is None:
  try:os.killpg(child.pid,signal.SIGKILL)
  except ProcessLookupError:pass
 child.wait(timeout=3)
def supervise(a):
 start=clk();verify(a.code_pins_sha256,a.profile_sha256)
 if OUT.exists():raise ValueError('existing_output_no_retry')
 import shutil
 if shutil.disk_usage(ROOT).free<FREE+16000000:raise ValueError('free_weights_scratch_reserves')
 OUT.mkdir()
 for name,n in SLOTS.items():
  with (OUT/name).open('xb') as f:f.write(b' '*n);f.flush();os.fsync(f.fileno())
 child=None;peak=0;reason=None
 def stop(s,f):raise RuntimeError('external_signal_'+str(s))
 old={s:signal.signal(s,stop) for s in [signal.SIGTERM,signal.SIGINT]}
 try:
  with (OUT/'worker.log').open('xb') as log:child=subprocess.Popen([sys.executable,str(HERE/'capture.py'),'--worker','--supervisor-pid',str(os.getpid()),'--start',str(start),'--code-pins-sha256',a.code_pins_sha256,'--profile-sha256',a.profile_sha256],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  write('ownership.json',{'supervisor_pid':os.getpid(),'worker_pid':child.pid,'shared_start':start,'profile_sha256':a.profile_sha256,'code_pins_sha256':a.code_pins_sha256})
  while child.poll() is None:
   if clk()-start>=55:reason='work55second_cap';break
   ps=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=1);rows=[tuple(map(int,l.split())) for l in ps.stdout.splitlines() if len(l.split())==3];owned={os.getpid()}
   if os.getpid() not in {p for p,q,r in rows}:raise RuntimeError('supervisor_missing_process_snapshot')
   while True:
    more=owned|{p for p,q,r in rows if q in owned}
    if more==owned:break
    owned=more
   rss=sum(r*1024 for p,q,r in rows if p in owned);peak=max(peak,rss)
   if rss>1000000000:reason='RSS1GB';break
   if size(OUT)>16000000 or shutil.disk_usage(ROOT).free<FREE:reason='evidence_or_free_cap';break
   time.sleep(.5)
  if reason:kill(child)
  else:child.wait(timeout=3)
  text=(OUT/'result.json').read_text();r=json.loads(text) if text.strip() else {};ok=child.returncode==0 and reason is None and r.get('status')=='COMPLETE_SELECTED_NATIVE_SOURCE_DISCOVERY_NO_ADMISSION' and clk()-start<60
  terminal('supervisor.json',{'status':'COMPLETE_NATIVE_SOURCE_CAPTURE_NO_ADMISSION' if ok else 'PARTIAL_NATIVE_SOURCE_CAPTURE_NO_RETRY','reason':reason,'worker_exit_code':child.returncode,'elapsed_seconds':clk()-start,'peak_observed_process_tree_RSS_bytes':peak,'output_bytes':size(OUT),'result_sha256':sha(OUT/'result.json'),'new_admitted_documents':0,'new_admitted_tokens':0});return 0 if ok else 1
 except BaseException as e:
  if child is not None:kill(child)
  terminal('supervisor.json',{'status':'PARTIAL_NATIVE_SOURCE_CAPTURE_NO_RETRY','reason':type(e).__name__+':'+str(e)[:1500],'elapsed_seconds':clk()-start,'new_admitted_documents':0});raise
 finally:
  for s,h in old.items():signal.signal(s,h)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--execute',action='store_true');ap.add_argument('--worker',action='store_true');ap.add_argument('--supervisor-pid',type=int);ap.add_argument('--start');ap.add_argument('--code-pins-sha256',required=True);ap.add_argument('--profile-sha256',required=True);a=ap.parse_args()
 if a.worker:worker(a)
 elif a.execute:raise SystemExit(supervise(a))
 else:verify(a.code_pins_sha256,a.profile_sha256);print('PINNED_CAPTURE_PREPARED_NO_NATIVE_PARSE')
