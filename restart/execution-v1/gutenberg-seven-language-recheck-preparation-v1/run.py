"""One offline seven-chapter language diagnostic; frozen strict policy, no tokenizer."""
import pathlib,json,hashlib,subprocess,sys,os,time,signal,importlib.util
HERE=pathlib.Path(__file__).resolve().parent;BASE=HERE.parent;OUT=BASE/'m2-intake/gutenberg-seven-language-recheck-v1';SOURCE=BASE/'m2-intake/gutenberg-novel-prose-seven-joins-v2';CH=[3,14,22,30,36,46,48];CAP=5000000
FAST=pathlib.Path('/Users/navneetprabhakar/Documents/git/image/inference-history-20261021/data/language-detector-v4/fasttext');MODEL=FAST.parent/'lid.176.ftz';RULES=BASE/'wikibooks-language-token-preparation-v1/rules.py'
def clk():return time.clock_gettime(time.CLOCK_MONOTONIC)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def size():return sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())
def write(name,b):
 if size()+len(b)>CAP-65536:raise ValueError('output_cap')
 with (OUT/name).open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
def js(name,x):write(name,(json.dumps(x,indent=2,ensure_ascii=False)+'\n').encode())
def verify():
 p=json.loads((HERE/'profile.json').read_text())
 for f,h in p['pins'].items():
  if sha(pathlib.Path(f))!=h:raise ValueError('input_pin:'+f)
 return p

def worker(start):
 profile=verify();spec=importlib.util.spec_from_file_location('frozen_language_rules',RULES);r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
 inputs=[];mapping=[];docs=[]
 for ch in CH:
  path=SOURCE/f'chapters/chapter_{ch:02}.txt';text=path.read_bytes().decode('utf8');rows=[]
  for i,(w,raw) in enumerate(r.windows(text)):
   projection=r.projection(raw);rec=dict(w,window_ordinal=i,chapter_number=ch,raw_utf8_sha256=hashlib.sha256(raw.encode()).hexdigest(),projected_utf8_sha256=hashlib.sha256(projection.encode()).hexdigest())
   if w['scored']:rec['prediction_line_ordinal']=len(inputs);inputs.append(projection);mapping.append(rec)
   rows.append(rec)
  docs.append({'chapter_number':ch,'path':str(path),'sha256':sha(path),'characters':len(text),'UTF8_bytes':path.stat().st_size,'windows':rows})
 stream=('\n'.join(inputs)+'\n').encode();write('detector-input.txt',stream)
 remain=25-(clk()-start)
 if remain<=0:raise TimeoutError('work_deadline')
 result=subprocess.run([str(FAST),'predict-prob',str(MODEL),'-','1'],input=stream,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=remain)
 write('predictions.raw',result.stdout);write('detector-stderr.raw',result.stderr)
 if result.returncode:raise ValueError('detector_exit_'+str(result.returncode))
 if len(result.stdout)>1000000 or len(result.stderr)>100000:raise ValueError('native_output_bound')
 lines=result.stdout.decode('utf8').splitlines()
 if len(lines)!=len(inputs):raise ValueError('score_count')
 for rec,line in zip(mapping,lines):
  label,rawp,top,english,passed=r.prediction(line);rec.update(label=label,raw_probability=rawp,top_probability=top,english_probability=english,policy_pass=passed,exact_prediction_line=line)
 for doc in docs:
  doc['scored_lines']=sum(w['scored'] for w in doc['windows']);doc['skipped_chunks']=sum(not w['scored'] for w in doc['windows']);doc['language_pass']=all(w['policy_pass'] for w in doc['windows'] if w['scored'])
  assert doc['scored_lines']+doc['skipped_chunks']==len(doc['windows'])
 verify()
 js('result.json',{'status':'COMPLETE_SEVEN_CHANGED_CHAPTER_LANGUAGE_RECHECK_NO_ADMISSION','profile_sha256':sha(HERE/'profile.json'),'documents':docs,'summary':{'changed_chapters':7,'raw_policy_pass':sum(d['language_pass'] for d in docs),'raw_policy_fail':sum(not d['language_pass'] for d in docs),'scored_lines':len(lines),'explicit_skipped_chunks':sum(d['skipped_chunks'] for d in docs)},'unchanged_chapter45':{'new_v2_sha256':sha(SOURCE/'chapters/chapter_45.txt'),'old_v1_sha256':sha(BASE/'gutenberg-novel-prose-v1/chapters/chapter_45.txt'),'rescored':False,'existing_failed_tail_probability':0.78168,'existing_threshold':0.8,'hold':'FAIL_RETAINED_NO_WAIVER; this seven-chapter pass cannot resolve it'},'elapsed_seconds':clk()-start,'source_text_or_policy_changed':False,'tokenizer_used':False,'new_admitted_documents':0,'new_admitted_tokens':0,'models_initialized':0,'training_updates':0})

def main():
 if len(sys.argv)>1:return worker(float(sys.argv[1]))
 start=clk();verify();OUT.mkdir(exist_ok=False);child=None;peak=0;reason=None
 try:
  with (OUT/'worker.log').open('xb') as log:child=subprocess.Popen([sys.executable,str(HERE/'run.py'),str(start)],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  while child.poll() is None:
   if clk()-start>=25:reason='work25seconds';break
   ps=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,timeout=min(1,max(.01,25-(clk()-start))),check=True);rows=[tuple(map(int,l.split())) for l in ps.stdout.splitlines() if len(l.split())==3];owned={os.getpid()}
   while True:
    nxt=owned|{p for p,q,r in rows if q in owned}
    if nxt==owned:break
    owned=nxt
   rss=sum(r*1024 for p,q,r in rows if p in owned);peak=max(peak,rss)
   if rss>1000000000:reason='observed_RSS1GB';break
   if size()>CAP-65536:reason='output5MB';break
   time.sleep(.05)
  if reason:os.killpg(child.pid,signal.SIGKILL)
  code=child.wait(timeout=2);result=json.loads((OUT/'result.json').read_text()) if (OUT/'result.json').exists() else {}
  if clk()-start>=30:reason='external30seconds'
  ok=code==0 and reason is None and result.get('status')=='COMPLETE_SEVEN_CHANGED_CHAPTER_LANGUAGE_RECHECK_NO_ADMISSION'
  js('supervisor.json',{'status':'PASS_OFFLINE_SEVEN_RECHECK_NO_ADMISSION' if ok else 'TERMINAL_PARTIAL_NO_RETRY','reason':reason,'worker_exit_code':code,'peak_observed_process_tree_RSS_bytes':peak,'elapsed_seconds':clk()-start,'actual_output_bytes_before_supervisor':size(),'result_sha256':sha(OUT/'result.json') if (OUT/'result.json').exists() else None,'new_admitted_documents':0,'new_admitted_tokens':0})
  if not ok:raise RuntimeError('terminal_no_retry')
  print(json.dumps(result['summary']))
 finally:
  if child is not None and child.poll() is None:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=2)
if __name__=='__main__':main()
