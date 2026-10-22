"""One bounded application of two reviewed literal recipes; no generic renderer."""
import argparse,hashlib,json,os,pathlib,re,shutil,signal,subprocess,sys,time
import literal_core as core
HERE=pathlib.Path(__file__).resolve().parent;BASE=HERE.parent;ROOT=BASE/'m2-intake';SOURCE=ROOT/'enwiki-native-20row-capture-v1';OUT=ROOT/'enwiki-two-source-literal-prose-development-v1';FREE=53474836480
LIMITS={'worker_seconds':55,'external_seconds':60,'output_bytes':16000000,'observed_RSS_bytes':1000000000,'source_files':2,'models_initialized':0,'network_requests':0,'tokenization':False}
SLOTS={'result.json':65536,'supervisor.json':16384}
def clk():return time.clock_gettime(time.CLOCK_MONOTONIC)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def size(p):return sum(f.stat().st_size for f in p.rglob('*') if f.is_file())
def inventory():
 paths=[HERE/n for n in ['render.py','literal_core.py','build_recipe.py','checks.py','profile.json','code_guard.py','literal-recipes.json','all20-original-decisions.json']]+[SOURCE/'all20-native-decisions.json',SOURCE/'result.json',SOURCE/'supervisor.json',BASE/'enwiki-native20-source-review-v1/summary.json',BASE/'disk-budget.json']
 paths += [SOURCE/f'row-{row}.{suffix}' for row in [4481523,17544253] for suffix in ['source-text.utf8','native-page.xml','json']]
 return {str(p.resolve()) for p in paths}
def verify(code,prof):
 import code_guard;code_guard.verify(code)
 if sha(HERE/'profile.json')!=prof:raise ValueError('external_profile_pin')
 p=json.loads((HERE/'profile.json').read_text());package=json.loads((HERE/'literal-recipes.json').read_text())
 if p['limits']!=LIMITS or p['output']!=str(OUT) or len(package['recipes'])!=2:raise ValueError('fixed_limits_two_sources')
 if (HERE/'all20-original-decisions.json').read_bytes()!=(SOURCE/'all20-native-decisions.json').read_bytes():raise ValueError('all20_decisions_must_remain_exact')
 if [(r['title'],r['index_row_ordinal']) for r in package['recipes']]!=[('WUKS',4481523),('Unikili',17544253)]:raise ValueError('exact_source_recipe_order')
 for r in package['recipes']:
  path=SOURCE/f"row-{r['index_row_ordinal']}.source-text.utf8";raw=path.read_bytes()
  if r['source_text_path']!=str(path) or sha(path)!=r['source_text_SHA256'] or len(raw)!=r['source_text_bytes']:raise ValueError('source_identity')
  previous=0
  for op in r['operations']:
   a=op['start_byte'];b=op['end_exclusive_byte'];old=bytes.fromhex(op['original_hex'])
   if type(a)is not int or type(b)is not int or not previous<=a<b<=len(raw) or raw[a:b]!=old or core.sha(old)!=op['original_SHA256']:raise ValueError('frozen_span_guard')
   previous=b
 return package

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
 package=verify(a.code_pins_sha256,a.profile_sha256);start=float(a.start);results=[]
 if os.getppid()!=a.supervisor_pid:raise ValueError('parent_identity')
 def check():
  if clk()-start>=55:raise TimeoutError('work55seconds')
 try:
  write('all20-original-decisions.json',(HERE/'all20-original-decisions.json').read_bytes());write('frozen-literal-recipes.json',(HERE/'literal-recipes.json').read_bytes())
  for r in package['recipes']:
   check();raw=pathlib.Path(r['source_text_path']).read_bytes();preview,inverse=core.apply(raw,r);unit_positions=[]
   for u in r['complete_native_units']:
    a=core.mapped_boundary(u['source_start_byte'],r);b=core.mapped_boundary(u['source_end_exclusive_byte'],r)
    if u['status']=='HELD_COMPLETE_DEPENDENT_UNIT_NO_RENDER' and a!=b:raise ValueError('unsupported_unit_must_be_wholly_absent')
    unit_positions.append({'source_unit_ordinal':u['ordinal'],'source_start_byte':u['source_start_byte'],'source_end_exclusive_byte':u['source_end_exclusive_byte'],'preview_start_byte':a,'preview_end_exclusive_byte':b,'preview_SHA256':core.sha(preview[a:b]),'status':u['status'],'dependency_holds':u['dependency_holds'],'admitted':False})
   stem='row-'+str(r['index_row_ordinal']);write(stem+'.development-preview.utf8',preview)
   write(stem+'.ancestry.json',{'source_path':r['source_text_path'],'source_SHA256':core.sha(raw),'source_native_XML_SHA256':r['source_native_XML_SHA256'],'preview_SHA256':core.sha(preview),'preview_bytes':len(preview),'inverse_exact_source_verified':core.restore(preview,inverse)==raw,'inverse_operations':inverse,'units':unit_positions,'citation_markers_are_generated_provenance_not_source_wording':True,'not_usable_or_accepted':True})
   write(stem+'.omissions-and-dependencies.json',{'omitted_exact_source_spans':[op for op in r['operations'] if op['replacement_hex']==''],'complete_native_units':r['complete_native_units'],'native_reference_occurrences':r['reference_occurrences'],'native_reference_definitions':r['native_citation_definitions'],'all_unsupported_or_component_dependencies_remain_held':True,'template_values_inferred':False,'manual_semantic_mapping_scope':'Only parent-approved Unikili literal {{As of|2011}} to As of 2011; not certified same-snapshot expansion'})
   results.append({'title':r['title'],'index_row_ordinal':r['index_row_ordinal'],'preview_file':stem+'.development-preview.utf8','source_SHA256':core.sha(raw),'preview_SHA256':core.sha(preview),'preview_bytes':len(preview),'inverse_exact':True,'literal_operations':len(inverse),'held_complete_units_no_render':sum(u['status']=='HELD_COMPLETE_DEPENDENT_UNIT_NO_RENDER' for u in r['complete_native_units']),'admitted':False})
  verify(a.code_pins_sha256,a.profile_sha256)
  write('manifest.json',{'artifacts_SHA256':{p.name:sha(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name not in [*SLOTS,'worker.log','ownership.json']},'new_admitted_documents':0,'new_admitted_tokens':0})
  terminal('result.json',{'status':'COMPLETE_TWO_SOURCE_REVERSIBLE_DEVELOPMENT_PREVIEWS_ONLY','source_inputs_unchanged':True,'all20original_decisions_unchanged':True,'sources':results,'elapsed_seconds':clk()-start,'manifest_SHA256':sha(OUT/'manifest.json'),'template_values_inferred':False,'manual_semantic_mapping_scope':'Only parent-approved Unikili literal {{As of|2011}} to As of 2011','generalizable_renderer_claimed':False,'network_requests':0,'models_initialized':0,'tokenization_performed':False,'new_admitted_documents':0,'new_admitted_tokens':0})
 except BaseException as e:
  terminal('result.json',{'status':'TERMINAL_PARTIAL_TWO_SOURCE_DEVELOPMENT_NO_RETRY','error':type(e).__name__+':'+str(e)[:1500],'completed_previews':results,'new_admitted_documents':0,'new_admitted_tokens':0});raise

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
  with (OUT/'worker.log').open('xb') as log:child=subprocess.Popen([sys.executable,str(HERE/'render.py'),'--worker','--supervisor-pid',str(os.getpid()),'--start',str(start),'--code-pins-sha256',a.code_pins_sha256,'--profile-sha256',a.profile_sha256],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
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
  text=(OUT/'result.json').read_text();r=json.loads(text) if text.strip() else {};ok=child.returncode==0 and reason is None and r.get('status')=='COMPLETE_TWO_SOURCE_REVERSIBLE_DEVELOPMENT_PREVIEWS_ONLY' and clk()-start<60
  terminal('supervisor.json',{'status':'COMPLETE_TWO_SOURCE_DEVELOPMENT_NO_ADMISSION' if ok else 'PARTIAL_TWO_SOURCE_DEVELOPMENT_NO_RETRY','reason':reason,'worker_exit_code':child.returncode,'elapsed_seconds':clk()-start,'peak_observed_process_tree_RSS_bytes':peak,'output_bytes':size(OUT),'result_sha256':sha(OUT/'result.json'),'new_admitted_documents':0,'new_admitted_tokens':0});return 0 if ok else 1
 except BaseException as e:
  if child is not None:kill(child)
  terminal('supervisor.json',{'status':'PARTIAL_TWO_SOURCE_DEVELOPMENT_NO_RETRY','reason':type(e).__name__+':'+str(e)[:1500],'elapsed_seconds':clk()-start,'new_admitted_documents':0});raise
 finally:
  for s,h in old.items():signal.signal(s,h)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--execute',action='store_true');ap.add_argument('--worker',action='store_true');ap.add_argument('--supervisor-pid',type=int);ap.add_argument('--start');ap.add_argument('--code-pins-sha256',required=True);ap.add_argument('--profile-sha256',required=True);a=ap.parse_args()
 if a.worker:worker(a)
 elif a.execute:raise SystemExit(supervise(a))
 else:verify(a.code_pins_sha256,a.profile_sha256);print('PINNED_TWO_SOURCE_RECIPE_PREPARED_NO_DERIVATIVE')
