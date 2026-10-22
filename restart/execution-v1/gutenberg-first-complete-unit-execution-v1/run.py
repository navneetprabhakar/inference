"""Exact18 complete units; frozen tokenizer/language diagnostics. No admission/training."""
import argparse,hashlib,importlib.util,json,os,pathlib,signal,subprocess,sys,time
HERE=pathlib.Path(__file__).resolve().parent;BASE=HERE.parent;ROOT=BASE/'m2-intake';OUT=ROOT/'gutenberg-first-complete-units-v1';PROP=ROOT/'gutenberg-first-complete-unit-proposal-v1/proposal.json';PROP_SHA='488a9fb787a416975a81b4aa64b1cacbf6db409450adebf0c367534c56661a01';RULES=BASE/'wikibooks-language-token-preparation-v1/rules.py';TOKEN=BASE/'tokenizer-8192';FAST=pathlib.Path('/Users/navneetprabhakar/Documents/git/image/inference-history-20261021/data/language-detector-v4/fasttext');MODEL=FAST.parent/'lid.176.ftz';CAPS={'external_seconds':60,'worker_seconds':55,'output_bytes':8000000,'observed_RSS_bytes':1000000000,'main_units':18,'supplemental_prefaces':0,'held_work_replacements':0};SLOT=32768

def clk():return time.clock_gettime(time.CLOCK_MONOTONIC)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def size():return sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())
def inventory():
 if sha(PROP)!=PROP_SHA:raise ValueError('reviewed_proposal_pin')
 p=json.loads(PROP.read_text());return {str(x.resolve()) for x in [HERE/n for n in ['run.py','code_guard.py','profile.json','parent-authorization.json','preflight.py']]+[PROP,RULES,TOKEN/'manifest.json',TOKEN/'core.json',FAST,MODEL]+[pathlib.Path(x) for x in p['input_pins']]}
def verify(code,prof):
 import code_guard;code_guard.verify(code)
 if sha(HERE/'profile.json')!=prof:raise ValueError('profile_digest')
 p=json.loads((HERE/'profile.json').read_text())
 if p['limits']!=CAPS or p['proposal_sha256']!=PROP_SHA:raise ValueError('fixed_profile')
 return p

def runtime(p):
 from importlib.metadata import version
 if version('tokenizers')!='0.22.2':raise ValueError('tokenizers_runtime')
 spec=importlib.util.spec_from_file_location('frozen_language_rules',RULES);r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r);t=r.load_tokenizer(p)
 return r,t

def write(name,b):
 if size()+len(b)>8000000-65536:raise ValueError('output_cap')
 path=OUT/name;path.parent.mkdir(exist_ok=True)
 with path.open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
def js(name,x):write(name,(json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())
def terminal(name,obj):
 b=(json.dumps(obj,indent=2)+'\n').encode()
 if len(b)>SLOT:raise ValueError('terminal_slot')
 with (OUT/name).open('r+b') as f:f.write(b+b' '*(SLOT-len(b)));f.flush();os.fsync(f.fileno())
def worker(a):
 p=verify(a.code_pins_sha256,a.profile_sha256);rules,tokenizer=runtime(p);start=float(a.start)
 if os.getppid()!=a.supervisor_pid:raise ValueError('parent_identity')
 rows=json.loads(PROP.read_text())['records'];chosen=[r for r in rows if r['decision']=='PROPOSE_FIRST_COMPLETE_MAIN_UNIT_FOR_DISCOVERY'];assert len(chosen)==18
 docs=[];lines=[];maps=[]
 try:
  for r in chosen:
   if clk()-start>=55:raise TimeoutError('work55sec')
   path=pathlib.Path(r['source_path']);source=path.read_bytes();assert hashlib.sha256(source).hexdigest()==r['source_SHA256'];a0,b0=r['source_start_byte'],r['source_end_byte'];raw=source[a0:b0]
   if hashlib.sha256(raw).hexdigest()!=r['exact_unit_sha256'] or len(raw)!=r['exact_unit_bytes'] or not raw.startswith(r['literal_heading_included'].encode()):raise ValueError('exact_unit_binding')
   if hashlib.sha256(source[:a0]+raw+source[b0:]).hexdigest()!=r['source_SHA256']:raise ValueError('inverse_source_reconstruction')
   text=raw.decode('utf8',errors='strict');eid=r['ebook_ID'];file=f'units/pg{eid}-first-complete.txt';write(file,raw);doc={'ebook_ID':eid,'file':file,'native_family_component_ID':r['native_family_component_ID'],'source_SHA256':r['source_SHA256'],'source_start_byte':a0,'source_end_byte':b0,'unit_SHA256':r['exact_unit_sha256'],'UTF8_bytes':len(raw),'characters':len(text),'main_unit_kind':r['unit_kind'],'literal_heading_retained':True,'in_unit_bytes_unchanged':True,'inverse_source_reconstruction':True,'M1_content_tokens':len(tokenizer.encode(text,add_special_tokens=False).ids),'one_EOS_separate':1,'known_component_flags_preserved':r['known_component_flags'],'book_component_assessment_preserved':r['book_component_assessment'],'book_dependencies_preserved':r['book_dependencies_and_limits'],'rights_quality_leakage_admission':'NOT_APPROVED; language/token diagnostics do not remove original flags/holds','windows':[],'new_admitted_documents':0}
   for ordinal,(w,chunk) in enumerate(rules.windows(text)):
    projection=rules.projection(chunk);rec=dict(w,window_ordinal=ordinal,ebook_ID=eid,raw_SHA256=hashlib.sha256(chunk.encode()).hexdigest(),projection_SHA256=hashlib.sha256(projection.encode()).hexdigest())
    if w['scored']:rec['prediction_line_ordinal']=len(lines);lines.append(projection);maps.append(rec)
    doc['windows'].append(rec)
   docs.append(doc)
  stream=('\n'.join(lines)+'\n').encode();write('detector-input.txt',stream)
  timeout=55-(clk()-start)
  if timeout<=0:raise TimeoutError('work55sec')
  result=subprocess.run([str(FAST),'predict-prob',str(MODEL),'-','1'],input=stream,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
  write('predictions.raw',result.stdout);write('detector-stderr.raw',result.stderr)
  if result.returncode:raise ValueError('classifier_exit')
  predictions=result.stdout.decode().splitlines()
  if len(predictions)!=len(lines):raise ValueError('exact_window_score_count')
  for rec,line in zip(maps,predictions):
   label,rawp,top,en,passed=rules.prediction(line);rec.update(label=label,raw_probability=rawp,top_probability=top,english_probability=en,policy_pass=passed,exact_prediction_line=line)
  for d in docs:
   d['raw_language_policy_pass']=all(w['policy_pass'] for w in d['windows'] if w['scored']);d['scored_lines']=sum(w['scored'] for w in d['windows']);d['skipped_chunks']=sum(not w['scored'] for w in d['windows']);js('receipts/pg'+str(d['ebook_ID'])+'.json',d)
  verify(a.code_pins_sha256,a.profile_sha256)
  summary={'complete_main_units':18,'raw_language_pass_units':sum(d['raw_language_policy_pass'] for d in docs),'raw_language_fail_units':sum(not d['raw_language_policy_pass'] for d in docs),'M1_content_tokens_all18':sum(d['M1_content_tokens'] for d in docs),'M1_content_plus_one_EOS_each':sum(d['M1_content_tokens']+1 for d in docs),'M1_content_tokens_language_pass_only_provisional':sum(d['M1_content_tokens'] for d in docs if d['raw_language_policy_pass']),'source_exact_unit_UTF8_bytes':sum(d['UTF8_bytes'] for d in docs),'scored_lines':len(lines),'skipped_chunks':sum(d['skipped_chunks'] for d in docs),'unique_native_metadata_family_components_in18':len({d['native_family_component_ID'] for d in docs}),'additional_prefaces_copied':0,'held_works_copied':0,'new_admitted_documents':0,'new_admitted_tokens':0}
  js('documents.json',{'status':'COMPLETE_EXACT18_UNITS_DIAGNOSTICS_PROVISIONAL_COUNTS_NOT_ADMITTED','profile_sha256':a.profile_sha256,'parent_authorization_sha256':sha(HERE/'parent-authorization.json'),'documents':docs,'held_unchanged':[r['ebook_ID'] for r in rows if r['decision'].startswith('HOLD')],'summary':summary,'language_policy':'Frozenwhole+1024Unicodechar chunks eligible>=40alphabetics top1Englishp>=.8, exactCR/LF projection, shorttail failures retained.','corpus_usable_counts_claimed':False})
  terminal('result.json',{'status':'COMPLETE_EXACT18_UNITS_PROVISIONAL_DIAGNOSTICS_NO_ADMISSION','summary':summary,'documents_sha256':sha(OUT/'documents.json'),'elapsed_seconds':clk()-start,'original20sources_and_provenance_unchanged':True,'models_initialized':0,'training_updates':0})
 except BaseException as e:terminal('result.json',{'status':'PARTIAL_NO_RETRY_NO_ADMISSION','error':type(e).__name__+':'+str(e)[:1500],'units_copied':len(docs),'new_admitted_documents':0});raise

def kill(child):
 if child.poll() is None:
  try:os.killpg(child.pid,signal.SIGKILL)
  except ProcessLookupError:pass
 child.wait(timeout=2)
def main(a):
 start=clk();verify(a.code_pins_sha256,a.profile_sha256)
 preflight=json.loads((HERE/'preflight-result.json').read_text())
 if preflight['status']!='PASS_ACTUAL_PROJECT_RUNTIME_SYNTHETIC_ONLY' or preflight['code_pins_sha256']!=a.code_pins_sha256 or preflight['profile_sha256']!=a.profile_sha256:raise ValueError('preflight_required')
 if OUT.exists():raise ValueError('existing_output_no_retry')
 OUT.mkdir()
 for n in ['result.json','supervisor.json']:
  with (OUT/n).open('xb') as f:f.write(b' '*SLOT);f.flush();os.fsync(f.fileno())
 child=None;reason=None;peak=0
 def stop(signum,frame):raise RuntimeError('external_signal_'+str(signum))
 handlers={s:signal.signal(s,stop) for s in [signal.SIGTERM,signal.SIGINT]}
 try:
  with (OUT/'worker.log').open('xb') as log:child=subprocess.Popen([sys.executable,str(HERE/'run.py'),'--worker','--supervisor-pid',str(os.getpid()),'--start',str(start),'--code-pins-sha256',a.code_pins_sha256,'--profile-sha256',a.profile_sha256],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  js('ownership.json',{'parent_pid':os.getpid(),'worker_pid':child.pid,'start':start,'code_pins_sha256':a.code_pins_sha256,'profile_sha256':a.profile_sha256})
  while child.poll() is None:
   if clk()-start>=55:reason='work55seconds';break
   ps=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,timeout=1,check=True);rows=[tuple(map(int,l.split())) for l in ps.stdout.splitlines() if len(l.split())==3];owned={os.getpid()}
   while True:
    more=owned|{p for p,q,r in rows if q in owned}
    if more==owned:break
    owned=more
   rss=sum(r*1024 for p,q,r in rows if p in owned);peak=max(peak,rss)
   if rss>1000000000:reason='observed_RSS1GB';break
   if size()>8000000:reason='output8MB';break
   time.sleep(.05)
  if reason:kill(child)
  else:child.wait(timeout=2)
  text=(OUT/'result.json').read_text();r=json.loads(text) if text.strip() else {};ok=child.returncode==0 and reason is None and r.get('status')=='COMPLETE_EXACT18_UNITS_PROVISIONAL_DIAGNOSTICS_NO_ADMISSION' and clk()-start<60
  terminal('supervisor.json',{'status':'PASS_EXACT18_COPY_AND_DIAGNOSTICS_NO_ADMISSION' if ok else 'TERMINAL_PARTIAL_NO_RETRY','reason':reason,'worker_exit_code':child.returncode,'elapsed_seconds':clk()-start,'peak_observed_process_tree_RSS_bytes':peak,'output_bytes':size(),'result_sha256':sha(OUT/'result.json'),'new_admitted_documents':0})
  print(json.dumps(r));return 0 if ok else 1
 except BaseException as e:
  if child is not None:kill(child)
  terminal('supervisor.json',{'status':'TERMINAL_PARTIAL_NO_RETRY','error':type(e).__name__+':'+str(e)[:1000],'elapsed_seconds':clk()-start,'new_admitted_documents':0});raise
 finally:
  if child is not None and child.poll() is None:kill(child)
  for s,h in handlers.items():signal.signal(s,h)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--worker',action='store_true');ap.add_argument('--supervisor-pid',type=int);ap.add_argument('--start');ap.add_argument('--code-pins-sha256',required=True);ap.add_argument('--profile-sha256',required=True);a=ap.parse_args()
 if a.worker:worker(a)
 else:raise SystemExit(main(a))
