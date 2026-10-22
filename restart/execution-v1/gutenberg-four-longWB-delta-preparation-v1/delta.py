"""One finite4vs29 custody delta; exact source bytes, existing fixed matcher only."""
import argparse,hashlib,importlib.util,json,os,pathlib,signal,subprocess,sys,time
HERE=pathlib.Path(__file__).resolve().parent;SLOT=16384;OUT=HERE.parent/'m2-intake/gutenberg-four-longWB-delta-v1';LIMITS={'external_seconds': 30, 'worker_seconds': 27, 'output_bytes': 8000000, 'observed_RSS_bytes': 1000000000}
def clk():return time.clock_gettime(time.CLOCK_MONOTONIC)
def sha(p):
 with pathlib.Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def inventory():
 p=json.loads((HERE/'profile.json').read_text());return {str(HERE/n) for n in ['delta.py','controls.py','profile.json']}|set(p['inputs_SHA256'])
def verify(code,profile):
 if sha(HERE/'code-pins.json')!=code or sha(HERE/'profile.json')!=profile:raise ValueError('external_code_or_profile_pin')
 p=json.loads((HERE/'profile.json').read_text());m=json.loads((HERE/'code-pins.json').read_text())
 if set(m['SHA256'])!=inventory() or m['runtime']!={'python':sys.version,'executable':str(pathlib.Path(sys.executable).resolve())}:raise ValueError('inventory_runtime')
 if p['limits']!=LIMITS or p['candidate_ids']!=[3028,34616,2521,8530] or p['source_ordinal_order']!=[59666,26355,54103,76283] or p['max_measured_normalized_words']!=240742 or p['total_measured_text_bytes']!=5470414 or p['total_measured_normalized_words']!=880003 or p['output']!=str(OUT):raise ValueError('fixed_profile')
 for f,h in m['SHA256'].items():
  if pathlib.Path(f).is_symlink() or sha(f)!=h:raise ValueError('pinned_input_changed:'+f)
 for f,h in p['inputs_SHA256'].items():
  if sha(f)!=h:raise ValueError('profile_input_pin')
 return p

def load_core(p):
 spec=importlib.util.spec_from_file_location('delta_frozen_core',p['matcher']);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def size():return sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())
def write(name,obj):
 raw=(json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode()
 if size()+len(raw)>8000000-2*SLOT:raise ValueError('output_prewrite8MB')
 with (OUT/name).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
def terminal(name,obj):
 raw=(json.dumps(obj,indent=2)+'\n').encode()
 if len(raw)>SLOT:raise ValueError('terminal_bound')
 with (OUT/name).open('r+b') as f:f.write(raw+b' '*(SLOT-len(raw)));f.flush();os.fsync(f.fileno())
def kill(c):
 try:os.killpg(c.pid,signal.SIGKILL)
 except ProcessLookupError:pass
 c.wait(timeout=1)
def main(a):
 start=clk();child=None;created=False;peak=0;reason=None
 def stop(sig,frame):raise TimeoutError('external30seconds_or_signal')
 old={s:signal.signal(s,stop) for s in [signal.SIGALRM,signal.SIGINT,signal.SIGTERM]};signal.setitimer(signal.ITIMER_REAL,max(.001,30-(clk()-start)))
 try:
  verify(a.code_pins_sha256,a.profile_sha256)
  if OUT.exists() or OUT.is_symlink():raise ValueError('existing_output_no_rerun')
  OUT.mkdir();created=True
  for n in ['result.json','supervisor.json']:
   with (OUT/n).open('xb') as f:f.write(b' '*SLOT)
  with (OUT/'worker.log').open('xb') as log:child=subprocess.Popen([sys.executable,str(HERE/'delta.py'),'--worker','--parent-pid',str(os.getpid()),'--start',str(start),'--code-pins-sha256',a.code_pins_sha256,'--profile-sha256',a.profile_sha256],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  write('ownership.json',{'parent_pid':os.getpid(),'worker_pid':child.pid,'start':start})
  while child.poll() is None:
   if clk()-start>=27:reason='worker27seconds';break
   ps=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=1);rows=[tuple(map(int,l.split())) for l in ps.stdout.splitlines() if len(l.split())==3];owned={os.getpid()}
   if os.getpid() not in {x[0] for x in rows}:raise ValueError('missing_RSS_observation')
   while True:
    more=owned|{pid for pid,ppid,rss in rows if ppid in owned}
    if more==owned:break
    owned=more
   peak=max(peak,sum(rss*1024 for pid,ppid,rss in rows if pid in owned))
   if peak>1000000000:reason='observed_RSS1GB';break
   if size()>8000000:reason='output8MB';break
   time.sleep(.025)
  if reason:kill(child)
  else:child.wait(timeout=1)
  raw=(OUT/'result.json').read_text();r=json.loads(raw) if raw.strip() else {};ok=child.returncode==0 and reason is None and r.get('status')=='COMPLETE_EXACT4_VS4_LONGWB_DELTA_NOT_ADMISSION' and clk()-start<30
  terminal('supervisor.json',{'status':'COMPLETE_DELTA_NO_ADMISSION' if ok else 'PARTIAL_NO_RETRY_NO_ZERO_CLAIM','reason':reason,'worker_exit_code':child.returncode,'elapsed_seconds':clk()-start,'peak_observed_process_tree_RSS_bytes':peak,'output_bytes':size(),'result_SHA256':sha(OUT/'result.json')});print(json.dumps(r));return 0 if ok else 1
 except BaseException as e:
  if child is not None:kill(child)
  if created:
   n=OUT/'supervisor.json'
   if not n.exists():n.write_bytes(b' '*SLOT)
   terminal('supervisor.json',{'status':'PARTIAL_NO_RETRY_NO_ZERO_CLAIM','error':type(e).__name__+':'+str(e)[:1000]})
  raise
 finally:
  if child is not None and child.poll() is None:kill(child)
  signal.setitimer(signal.ITIMER_REAL,0)
  for s,h in old.items():signal.signal(s,h)

def extract_bound(db,roles,r,core):
 import sqlite3
 ordinal=r['source_ordinal'];size=db.execute('select length(cast(data as blob)) from rendered where source_ordinal=?',(ordinal,)).fetchone()
 if size is None or size[0]!=r['source_data_UTF8_bytes'] or size[0]>16000000:raise ValueError('exact_source_JSON_length')
 row=db.execute('select page_id,revision_id,family,data from rendered where source_ordinal=?',(ordinal,)).fetchone();page,rev,family,data=row
 if hashlib.sha256(data.encode()).hexdigest()!=r['source_data_SHA256']:raise ValueError('raw_SQLite_JSON_hash')
 obj=json.loads(data);text=obj['text'];raw=text.encode();norm=core.normalized(text)
 role=roles.execute('select p.page_id,p.revision_id,p.family,p.text_sha256,p.holds,p.active,f.holds from pages p join final_pages f on p.source_ordinal=f.source_ordinal where p.source_ordinal=?',(ordinal,)).fetchone()
 if role is None:raise ValueError('finalizer_role_missing')
 actual={'page_id':role[0],'revision_id':role[1],'family':role[2],'text_sha256':role[3],'prior_holds':json.loads(role[4]),'active':role[5],'global_final_holds':json.loads(role[6])}
 if actual!=r['all_prior_current_role_and_global_holds'] or page!=obj['page_id'] or page!=r['source_outer_page_id'] or rev!=obj['revision_id'] or rev!=r['source_outer_revision_id'] or family!=obj['family_id'] or family!=r['source_family'] or obj['title']!=r['title'] or obj['url']!=r['url']:raise ValueError('outer_payload_finalizer_identity_holds')
 if hashlib.sha256(raw).hexdigest()!=r['text_SHA256'] or actual['text_sha256']!=r['text_SHA256'] or len(raw)!=r['text_UTF8_bytes'] or hashlib.sha256(norm.encode()).hexdigest()!=r['normalized_SHA256'] or len(norm.encode())!=r['normalized_UTF8_bytes'] or len(norm.split())!=r['normalized_words']:raise ValueError('exact_text_projection_binding')
 if r['normalized_words']>240742:raise ValueError('fixed_newprofile_wordbound')
 return norm,actual

def worker(a):
 results=[]
 try:
  import sqlite3
  p=verify(a.code_pins_sha256,a.profile_sha256);core=load_core(p);cs=json.loads(pathlib.Path(p['candidate_manifest']).read_text());rs=p['source_rows']
  if [r['source_ordinal'] for r in rs]!=[59666,26355,54103,76283] or len(rs)!=4 or [c['ebook_ID'] for c in cs]!=[3028,34616,2521,8530] or os.getppid()!=a.parent_pid:raise ValueError('exact4sources4candidates_parent')
  idx=core.Index([pathlib.Path(c['file']).read_bytes().decode('utf8') for c in cs]);roles=sqlite3.connect(pathlib.Path(p['finalized_DB']).as_uri()+'?mode=ro',uri=True);roles.execute('pragma cache_size=-2048');roles.execute('pragma query_only=ON')
  try:
   for r in rs:
    if clk()-a.start>=27:raise TimeoutError('worker27seconds')
    db=sqlite3.connect(pathlib.Path(r['source_path']).as_uri()+'?mode=ro',uri=True);db.execute('pragma cache_size=-2048');db.execute('pragma query_only=ON')
    try:norm,actual=extract_bound(db,roles,r,core)
    finally:db.close()
    hits=idx.compare(norm);results.append({'source_binding':r,'role_and_all_holds_preserved':actual,'source_JSON_and_text_hash_inverse_verified':True,'candidate_comparisons':[{'candidate_ebook_ID':c['ebook_ID'],'candidate_text_SHA256':c['text_SHA256'],'candidate_family_component_ID':c['family_component_ID'],'match':hits.get(i,{}),'disposition':'BODY_MATCH_REQUIRES_CUSTODY_REVIEW' if i in hits else 'NO_MATCH_UNDER_EXACT_FROZEN_LITERAL_POLICIES_ONLY'} for i,c in enumerate(cs)]});del norm
  finally:roles.close()
  if len(results)!=4:raise ValueError('complete4required')
  verify(a.code_pins_sha256,a.profile_sha256);write('comparisons.json',{'status':'COMPLETE_EXACT4_VS4_LONGWB_DELTA_NOT_ADMISSION','profile_SHA256':a.profile_sha256,'candidates':cs,'documents':results,'scope':p['scope']});terminal('result.json',{'status':'COMPLETE_EXACT4_VS4_LONGWB_DELTA_NOT_ADMISSION','required_longWB_bodies':4,'candidate_document_pairs':16,'matched_pairs':sum(bool(c['match']) for d in results for c in d['candidate_comparisons']),'comparisons_SHA256':sha(OUT/'comparisons.json'),'elapsed_seconds':clk()-a.start,'new_admitted_documents':0})
 except BaseException as e:terminal('result.json',{'status':'PARTIAL_NO_RETRY_NO_ZERO_CLAIM','documents_completed':len(results),'error':type(e).__name__+':'+str(e)[:1000]});raise
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--worker',action='store_true');ap.add_argument('--parent-pid',type=int);ap.add_argument('--start',type=float);ap.add_argument('--code-pins-sha256',required=True);ap.add_argument('--profile-sha256',required=True);a=ap.parse_args()
 if a.worker:worker(a)
 else:raise SystemExit(main(a))
