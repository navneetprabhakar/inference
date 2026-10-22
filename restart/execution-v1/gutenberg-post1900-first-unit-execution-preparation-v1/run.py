"""Exact18 complete units; frozen tokenizer/language diagnostics. No admission/training."""
import argparse,hashlib,importlib.util,json,os,pathlib,signal,subprocess,sys,time
HERE=pathlib.Path(__file__).resolve().parent;BASE=HERE.parent;ROOT=BASE/'m2-intake';OUT=ROOT/'gutenberg-post1900-first-complete-units-v1';PROP=ROOT/'gutenberg-post1900-component-manual-review-v1/first-unit-proposal.json';PROP_SHA='bdb7ecefb40244df81769b9b1d3787133b684d3328f253d7af106865a89bb14f';RULES=BASE/'wikibooks-language-token-preparation-v1/rules.py';TOKEN=BASE/'tokenizer-8192';FAST=pathlib.Path('/Users/navneetprabhakar/Documents/git/image/inference-history-20261021/data/language-detector-v4/fasttext');MODEL=FAST.parent/'lid.176.ftz';CAPS={'external_seconds': 60, 'worker_seconds': 55, 'output_bytes': 16000000, 'observed_RSS_bytes': 1000000000, 'main_units': 19, 'external_notes': 10, 'unit_bytes': 262144, 'combined_source_bytes_exclusive': 4000000, 'held_work_replacements': 0};SLOT=32768

def clk():return time.clock_gettime(time.CLOCK_MONOTONIC)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def size():return sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())
def inventory():
 if sha(PROP)!=PROP_SHA:raise ValueError('reviewed_proposal_pin')
 p=json.loads(PROP.read_text());return {str(x.resolve()) for x in [HERE/n for n in ['run.py','code_guard.py','profile.json','parent-authorization.json','preflight.py','controls.py']]+[PROP,RULES,TOKEN/'manifest.json',TOKEN/'core.json',FAST,MODEL]+[pathlib.Path(x) for x in json.loads((HERE/'profile.json').read_text())['input_pins']]}
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
 if size()+len(b)>16000000-65536:raise ValueError('output_cap')
 path=OUT/name;path.parent.mkdir(exist_ok=True)
 with path.open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
def js(name,x):write(name,(json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())
def terminal(name,obj):
 b=(json.dumps(obj,indent=2)+'\n').encode()
 if len(b)>SLOT:raise ValueError('terminal_slot')
 with (OUT/name).open('r+b') as f:f.write(b+b' '*(SLOT-len(b)));f.flush();os.fsync(f.fileno())
def kill(child):
 if child.poll() is None:
  try:os.killpg(child.pid,signal.SIGKILL)
  except ProcessLookupError:pass
 child.wait(timeout=2)
def selected(rows):
 chosen=[r for r in rows if r['status'] in ['PROPOSE_EXACT_FIRST_COMPLETE_MAIN_UNIT_NO_COPY_YET','PROPOSE_COMPLETE_FIRST_CHAPTER_LONG127814B_REVIEW_COST_EXPLICIT_NO_TRUNCATION']]
 if len(chosen)!=19 or [r['ebook_ID'] for r in rows if r not in chosen]!=[26107]:raise ValueError('exact19_plus26107hold')
 if sum(r['UTF8_bytes'] for r in chosen)!=602810 or sum(n['UTF8_bytes'] for r in chosen for n in r['external_note_dependencies'])!=4512:raise ValueError('frozen_total_bytes')
 return chosen

def exact(source,r):
 a,b=r['source_start_byte'],r['source_end_byte']
 if not 0<=a<b<=len(source) or b-a!=r['UTF8_bytes'] or b-a>262144:raise ValueError('unit_bound')
 raw=source[a:b]
 if hashlib.sha256(raw).hexdigest()!=r['SHA256']:raise ValueError('interval_hash')
 if source[:a]+raw+source[b:]!=source:raise ValueError('inverse_reconstruction')
 raw.decode('utf8',errors='strict');return raw

def assign_predictions(rules,maps,lines):
 if len(maps)!=len(lines):raise ValueError('exact_prediction_count')
 for rec,line in zip(maps,lines):
  label,rawp,top,en,passed=rules.prediction(line);rec.update(label=label,raw_probability=rawp,top_probability=top,english_probability=en,policy_pass=passed,exact_prediction_line=line)

def worker(a):
 docs=[]
 try:
  p=verify(a.code_pins_sha256,a.profile_sha256);rules,tokenizer=runtime(p);start=float(a.start)
  if os.getppid()!=a.supervisor_pid:raise ValueError('parent_identity')
  rows=json.loads(PROP.read_text())['records'];chosen=selected(rows);lines=[];maps=[];combined=0
  for r in chosen:
   if clk()-start>=55:raise TimeoutError('work55sec')
   eid=r['ebook_ID'];source=(ROOT/'gutenberg-post1900-cohort-raw-v3'/f'pg{eid}.raw').read_bytes()
   if hashlib.sha256(source).hexdigest()!=r['source_SHA256']:raise ValueError('source_pin')
   items=[('main',None,r)]+[('external_note',n['label'],n) for n in r['external_note_dependencies']]
   for kind,label,item in items:
    raw=exact(source,item);combined+=len(raw)
    if combined>=4000000:raise ValueError('combined_source_cap')
    text=raw.decode('utf8');key=f'pg{eid}' if kind=='main' else f'pg{eid}-note{label}';file=('units/' if kind=='main' else 'external-notes/')+key+'.txt';write(file,raw)
    d={'document_key':key,'kind':kind,'ebook_ID':eid,'note_label':label,'file':file,'native_family_component_ID':r['family_component_ID'],'source_SHA256':r['source_SHA256'],'source_start_byte':item['source_start_byte'],'source_end_byte':item['source_end_byte'],'unit_SHA256':item['SHA256'],'UTF8_bytes':len(raw),'characters':len(text),'M1_content_tokens':len(tokenizer.encode(text,add_special_tokens=False).ids),'one_EOS_separate':1,'original_proposal_record_preserved':r,'bytes_unchanged_and_inverse_verified':True,'all_original_source_quality_rights_language_leakage_holds_retained':True,'new_admitted_documents':0,'windows':[]}
    for ordinal,(w,chunk) in enumerate(rules.windows(text)):
     projected=rules.projection(chunk);rec=dict(w,window_ordinal=ordinal,document_key=key,raw_SHA256=hashlib.sha256(chunk.encode()).hexdigest(),projection_SHA256=hashlib.sha256(projected.encode()).hexdigest())
     if w['scored']:rec['prediction_line_ordinal']=len(lines);lines.append(projected);maps.append(rec)
     d['windows'].append(rec)
    expected=1+(len(text)+1023)//1024
    if len(d['windows'])!=expected:raise ValueError('exact_whole_chunk_coverage')
    docs.append(d)
  if len(docs)!=29 or combined!=607322:raise ValueError('exact19_10_coverage')
  stream=('\n'.join(lines)+'\n').encode();write('detector-input.txt',stream);remaining=55-(clk()-start)
  if remaining<=0:raise TimeoutError('work55sec')
  result=subprocess.run([str(FAST),'predict-prob',str(MODEL),'-','1'],input=stream,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=remaining)
  write('predictions.raw',result.stdout);write('detector-stderr.raw',result.stderr)
  if result.returncode:raise ValueError('classifier_exit')
  assign_predictions(rules,maps,result.stdout.decode('utf8').splitlines())
  for d in docs:
   d['scored_lines']=sum(w['scored'] for w in d['windows']);d['skipped_chunks']=sum(not w['scored'] for w in d['windows']);d['raw_language_policy_pass']=all(w['policy_pass'] for w in d['windows'] if w['scored']);js('receipts/'+d['document_key']+'.json',d)
  summary={}
  for kind in ['main','external_note']:
   ds=[d for d in docs if d['kind']==kind];summary[kind]={'count':len(ds),'UTF8_bytes':sum(d['UTF8_bytes'] for d in ds),'M1_content_tokens':sum(d['M1_content_tokens'] for d in ds),'EOS_separate':len(ds),'language_pass':sum(d['raw_language_policy_pass'] for d in ds),'language_fail':sum(not d['raw_language_policy_pass'] for d in ds),'scored_lines':sum(d['scored_lines'] for d in ds),'skipped_chunks':sum(d['skipped_chunks'] for d in ds)}
  summary.update(new_admitted_documents=0,new_admitted_tokens=0,held_26107_unchanged=True,notes_inserted_into_main=0)
  verify(a.code_pins_sha256,a.profile_sha256)
  js('documents.json',{'status':'COMPLETE_EXACT19_AND10_SEPARATE_NOTES_PROVISIONAL_NO_ADMISSION','profile_sha256':a.profile_sha256,'documents':docs,'summary':summary,'source_component_review':p['input_pins'],'usable_counts_claimed':False})
  terminal('result.json',{'status':'COMPLETE_EXACT19_AND10_SEPARATE_NOTES_PROVISIONAL_NO_ADMISSION','summary':summary,'documents_sha256':sha(OUT/'documents.json'),'elapsed_seconds':clk()-start})
 except BaseException as e:
  terminal('result.json',{'status':'PARTIAL_NO_RETRY_NO_ADMISSION','error':type(e).__name__+':'+str(e)[:1500],'documents_copied':len(docs),'new_admitted_documents':0});raise

def main(a):
 start=clk();child=None;created=False;reason=None;peak=0
 def stop(signum,frame):raise TimeoutError('external_signal_'+str(signum))
 signals=[signal.SIGALRM,signal.SIGTERM,signal.SIGINT];handlers={s:signal.signal(s,stop) for s in signals}
 signal.setitimer(signal.ITIMER_REAL,max(.001,60-(clk()-start)))
 try:
  verify(a.code_pins_sha256,a.profile_sha256)
  pre=json.loads((HERE/'preflight-result.json').read_text())
  if pre['status']!='PASS_ACTUAL_PROJECT_RUNTIME_SYNTHETIC_ONLY' or pre['code_pins_sha256']!=a.code_pins_sha256 or pre['profile_sha256']!=a.profile_sha256:raise ValueError('preflight_required')
  if OUT.exists():raise ValueError('existing_output_no_retry')
  OUT.mkdir();created=True
  for n in ['result.json','supervisor.json']:
   with (OUT/n).open('xb') as f:f.write(b' '*SLOT);f.flush();os.fsync(f.fileno())
  with (OUT/'worker.log').open('xb') as log:child=subprocess.Popen([sys.executable,str(HERE/'run.py'),'--worker','--supervisor-pid',str(os.getpid()),'--start',str(start),'--code-pins-sha256',a.code_pins_sha256,'--profile-sha256',a.profile_sha256],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  js('ownership.json',{'parent_pid':os.getpid(),'worker_pid':child.pid,'shared_start':start,'code_pins_sha256':a.code_pins_sha256,'profile_sha256':a.profile_sha256})
  while child.poll() is None:
   if clk()-start>=55:reason='work55seconds';break
   ps=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,timeout=min(1,max(.01,60-(clk()-start))),check=True);rows=[tuple(map(int,l.split())) for l in ps.stdout.splitlines() if len(l.split())==3];owned={os.getpid()}
   while True:
    more=owned|{p for p,q,r in rows if q in owned}
    if more==owned:break
    owned=more
   rss=sum(r*1024 for p,q,r in rows if p in owned);peak=max(peak,rss)
   if rss>1000000000:reason='observed_RSS1GB';break
   if size()>16000000:reason='output16MB';break
   time.sleep(.05)
  if reason:kill(child)
  else:child.wait(timeout=2)
  r=json.loads((OUT/'result.json').read_text()) if (OUT/'result.json').read_text().strip() else {};ok=child.returncode==0 and reason is None and r.get('status')=='COMPLETE_EXACT19_AND10_SEPARATE_NOTES_PROVISIONAL_NO_ADMISSION' and clk()-start<60
  terminal('supervisor.json',{'status':'PASS_EXACT19_AND10_DIAGNOSTICS_NO_ADMISSION' if ok else 'TERMINAL_PARTIAL_NO_RETRY','reason':reason,'worker_exit_code':child.returncode,'elapsed_seconds':clk()-start,'peak_observed_process_tree_RSS_bytes':peak,'output_bytes':size(),'result_sha256':sha(OUT/'result.json'),'new_admitted_documents':0});print(json.dumps(r));return 0 if ok else 1
 except BaseException as e:
  if child is not None:kill(child)
  if created:
   for n in ['result.json','supervisor.json']:
    if not (OUT/n).exists():
     with (OUT/n).open('xb') as f:f.write(b' '*SLOT)
   terminal('supervisor.json',{'status':'TERMINAL_PARTIAL_NO_RETRY','error':type(e).__name__+':'+str(e)[:1000],'elapsed_seconds':clk()-start,'new_admitted_documents':0})
  raise
 finally:
  if child is not None and child.poll() is None:kill(child)
  signal.setitimer(signal.ITIMER_REAL,0)
  for s,h in handlers.items():signal.signal(s,h)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--worker',action='store_true');ap.add_argument('--supervisor-pid',type=int);ap.add_argument('--start');ap.add_argument('--code-pins-sha256',required=True);ap.add_argument('--profile-sha256',required=True);a=ap.parse_args()
 if a.worker:worker(a)
 else:raise SystemExit(main(a))
