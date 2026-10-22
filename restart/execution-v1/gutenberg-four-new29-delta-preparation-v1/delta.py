"""One finite4vs29 custody delta; exact source bytes, existing fixed matcher only."""
import argparse,hashlib,importlib.util,json,os,pathlib,signal,subprocess,sys,time
HERE=pathlib.Path(__file__).resolve().parent;SLOT=16384;OUT=HERE.parent/'m2-intake/gutenberg-four-new29-delta-v1';LIMITS={'external_seconds':10,'worker_seconds':8,'output_bytes':4000000,'observed_RSS_bytes':256000000}
def clk():return time.clock_gettime(time.CLOCK_MONOTONIC)
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def inventory():
 p=json.loads((HERE/'profile.json').read_text());return {str(HERE/n) for n in ['delta.py','controls.py','profile.json']}|set(p['inputs_SHA256'])
def verify(code,profile):
 if sha(HERE/'code-pins.json')!=code or sha(HERE/'profile.json')!=profile:raise ValueError('external_code_or_profile_pin')
 p=json.loads((HERE/'profile.json').read_text());m=json.loads((HERE/'code-pins.json').read_text())
 if set(m['SHA256'])!=inventory() or m['runtime']!={'python':sys.version,'executable':str(pathlib.Path(sys.executable).resolve())}:raise ValueError('inventory_runtime')
 if p['limits']!=LIMITS or p['candidate_ids']!=[3028,34616,2521,8530] or p['source_main_count']!=19 or p['source_external_note_count']!=10 or p['source_total_exact_bytes']!=607322 or p['output']!=str(OUT):raise ValueError('fixed_profile')
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
 if size()+len(raw)>4000000-2*SLOT:raise ValueError('output_prewrite4MB')
 with (OUT/name).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
def terminal(name,obj):
 raw=(json.dumps(obj,indent=2)+'\n').encode()
 if len(raw)>SLOT:raise ValueError('terminal_bound')
 with (OUT/name).open('r+b') as f:f.write(raw+b' '*(SLOT-len(raw)));f.flush();os.fsync(f.fileno())
def validate_docs(ds):
 if len(ds)!=29 or len({d['document_key'] for d in ds})!=29 or sum(d['kind']=='main' for d in ds)!=19 or sum(d['kind']=='external_note' for d in ds)!=10 or sum(d['UTF8_bytes'] for d in ds)!=607322:raise ValueError('exact29_required_coverage')
def worker(a):
 results=[]
 try:
  p=verify(a.code_pins_sha256,a.profile_sha256);core=load_core(p);cs=json.loads(pathlib.Path(p['candidate_manifest']).read_text());ds=json.loads(pathlib.Path(p['documents_manifest']).read_text())['documents'];validate_docs(ds)
  if [x['ebook_ID'] for x in cs]!=[3028,34616,2521,8530] or os.getppid()!=a.parent_pid:raise ValueError('candidate_or_parent_identity')
  texts=[]
  for c in cs:
   raw=pathlib.Path(c['file']).read_bytes()
   if hashlib.sha256(raw).hexdigest()!=c['text_SHA256']:raise ValueError('candidate_hash')
   texts.append(raw.decode('utf8'))
  idx=core.Index(texts);base=pathlib.Path(p['documents_manifest']).parent
  for d in ds:
   if clk()-a.start>=8:raise TimeoutError('worker8seconds')
   raw=(base/d['file']).read_bytes();src=base.parent/'gutenberg-post1900-cohort-raw-v3'/('pg'+str(d['ebook_ID'])+'.raw');original=src.read_bytes()
   if hashlib.sha256(raw).hexdigest()!=d['unit_SHA256'] or hashlib.sha256(original).hexdigest()!=d['source_SHA256'] or original[d['source_start_byte']:d['source_end_byte']]!=raw or len(raw)!=d['UTF8_bytes']:raise ValueError('exact_source_interval_inverse')
   norm=core.normalized(raw.decode('utf8'));hits=idx.compare(norm);results.append({'document_key':d['document_key'],'kind':d['kind'],'ebook_ID':d['ebook_ID'],'native_family_component_ID':d['native_family_component_ID'],'current_text_SHA256':d['unit_SHA256'],'source_SHA256':d['source_SHA256'],'source_path':str(src),'source_start_byte':d['source_start_byte'],'source_end_byte':d['source_end_byte'],'UTF8_bytes':len(raw),'source_inverse_verified':True,'raw_language_policy_pass_preserved':d['raw_language_policy_pass'],'all_original_holds_retained':True,'normalized_SHA256':core.sha(norm.encode()),'candidate_comparisons':[{'candidate_ebook_ID':c['ebook_ID'],'candidate_text_SHA256':c['text_SHA256'],'candidate_family_component_ID':c['family_component_ID'],'match':hits.get(i,{}),'disposition':'BODY_MATCH_REQUIRES_CUSTODY_REVIEW' if i in hits else 'NO_MATCH_UNDER_EXACT_FROZEN_LITERAL_POLICIES_ONLY'} for i,c in enumerate(cs)]})
  verify(a.code_pins_sha256,a.profile_sha256);write('comparisons.json',{'status':'COMPLETE_EXACT4_VS29_DELTA_NOT_ADMISSION','profile_SHA256':a.profile_sha256,'candidates':cs,'documents':results,'scope':p['scope']});terminal('result.json',{'status':'COMPLETE_EXACT4_VS29_DELTA_NOT_ADMISSION','main_units':19,'separate_notes':10,'candidate_document_pairs':116,'matched_pairs':sum(bool(c['match']) for d in results for c in d['candidate_comparisons']),'comparisons_SHA256':sha(OUT/'comparisons.json'),'elapsed_seconds':clk()-a.start,'new_admitted_documents':0})
 except BaseException as e:terminal('result.json',{'status':'PARTIAL_NO_RETRY_NO_ZERO_CLAIM','documents_completed':len(results),'error':type(e).__name__+':'+str(e)[:1000]});raise

def kill(c):
 try:os.killpg(c.pid,signal.SIGKILL)
 except ProcessLookupError:pass
 c.wait(timeout=1)
def main(a):
 start=clk();child=None;created=False;peak=0;reason=None
 def stop(sig,frame):raise TimeoutError('external10seconds_or_signal')
 old={s:signal.signal(s,stop) for s in [signal.SIGALRM,signal.SIGINT,signal.SIGTERM]};signal.setitimer(signal.ITIMER_REAL,max(.001,10-(clk()-start)))
 try:
  verify(a.code_pins_sha256,a.profile_sha256)
  if OUT.exists() or OUT.is_symlink():raise ValueError('existing_output_no_rerun')
  OUT.mkdir();created=True
  for n in ['result.json','supervisor.json']:
   with (OUT/n).open('xb') as f:f.write(b' '*SLOT)
  with (OUT/'worker.log').open('xb') as log:child=subprocess.Popen([sys.executable,str(HERE/'delta.py'),'--worker','--parent-pid',str(os.getpid()),'--start',str(start),'--code-pins-sha256',a.code_pins_sha256,'--profile-sha256',a.profile_sha256],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  write('ownership.json',{'parent_pid':os.getpid(),'worker_pid':child.pid,'start':start})
  while child.poll() is None:
   if clk()-start>=8:reason='worker8seconds';break
   ps=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=1);rows=[tuple(map(int,l.split())) for l in ps.stdout.splitlines() if len(l.split())==3];owned={os.getpid()}
   if os.getpid() not in {x[0] for x in rows}:raise ValueError('missing_RSS_observation')
   while True:
    more=owned|{pid for pid,ppid,rss in rows if ppid in owned}
    if more==owned:break
    owned=more
   peak=max(peak,sum(rss*1024 for pid,ppid,rss in rows if pid in owned))
   if peak>256000000:reason='observed_RSS256MB';break
   if size()>4000000:reason='output4MB';break
   time.sleep(.025)
  if reason:kill(child)
  else:child.wait(timeout=1)
  raw=(OUT/'result.json').read_text();r=json.loads(raw) if raw.strip() else {};ok=child.returncode==0 and reason is None and r.get('status')=='COMPLETE_EXACT4_VS29_DELTA_NOT_ADMISSION' and clk()-start<10
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
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--worker',action='store_true');ap.add_argument('--parent-pid',type=int);ap.add_argument('--start',type=float);ap.add_argument('--code-pins-sha256',required=True);ap.add_argument('--profile-sha256',required=True);a=ap.parse_args()
 if a.worker:worker(a)
 else:raise SystemExit(main(a))
