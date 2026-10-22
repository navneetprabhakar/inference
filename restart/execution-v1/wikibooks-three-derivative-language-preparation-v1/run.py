"""One parent-authorized exact-three offline language check, no tokenizer/training."""
from pathlib import Path
import sys,json,hashlib,subprocess,os,time,signal,importlib.util
P=Path(__file__).resolve().parent;B=P.parent;OUT=B/'m2-intake/wikibooks-three-derivative-language-v1';CAP=16000000;SLOTS={'result.json':262144,'supervisor.json':32768};FAST=Path('/Users/navneetprabhakar/Documents/git/image/inference-history-20261021/data/language-detector-v4/fasttext');MODEL=FAST.parent/'lid.176.ftz';RULE=B/'wikibooks-language-token-preparation-v1/rules.py'
CLOCK=lambda:time.clock_gettime(time.CLOCK_MONOTONIC)
H=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def size():return sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())
def checkpins():
 p=json.loads((P/'profile.json').read_text())
 for name,h in p['pins'].items():
  if H(name)!=h:raise ValueError('pin_changed:'+name)
 return p
def rules():
 spec=importlib.util.spec_from_file_location('frozen_strict_rules',RULE);r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r);return r
def put(name,b):
 if size()+len(b)>CAP-1048576:raise ValueError('output16MB')
 with (OUT/name).open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
def terminal(name,obj):
 b=(json.dumps(obj,indent=2)+'\n').encode();n=SLOTS[name]
 if len(b)>n:raise ValueError('terminal_slot_cap')
 with (OUT/name).open('r+b') as f:f.write(b+b' '*(n-len(b)));f.flush();os.fsync(f.fileno())
def worker(start):
 signal.signal(signal.SIGALRM,lambda s,f:(_ for _ in ()).throw(TimeoutError('worker55sec')));signal.setitimer(signal.ITIMER_REAL,max(.001,55-(CLOCK()-start)))
 try:
  profile=checkpins();r=rules();inputs=[];scored=[];docs=[]
  for c in profile['candidates']:
   path=Path(c['file']);raw=path.read_bytes();assert H(path)==c['text_SHA256'];text=raw.decode();windows=[]
   for i,(w,chunk) in enumerate(r.windows(text)):
    proj=r.projection(chunk);item={**w,'window_ordinal':i,'raw_SHA256':hashlib.sha256(chunk.encode()).hexdigest(),'projection_SHA256':hashlib.sha256(proj.encode()).hexdigest()}
    if item['scored']:item['prediction_line_ordinal']=len(inputs);inputs.append(proj);scored.append(item)
    windows.append(item)
   docs.append({'source_ordinal':c['source_ordinal'],'text_SHA256':c['text_SHA256'],'UTF8_bytes':len(raw),'characters':len(text),'windows':windows})
  stream=('\n'.join(inputs)+'\n').encode();put('detector.input',stream)
  q=subprocess.run([str(FAST),'predict-prob',str(MODEL),'-','1'],input=stream,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=max(.001,55-(CLOCK()-start)))
  put('detector.predictions',q.stdout);put('detector.stderr',q.stderr)
  if q.returncode or len(q.stdout)>100000 or len(q.stderr)>100000:raise ValueError('native_detector_exit_or_output')
  lines=q.stdout.decode().splitlines()
  if len(lines)!=len(inputs):raise ValueError('score_count_exact')
  for w,line in zip(scored,lines):
   label,rawp,top,en,passed=r.prediction(line);w.update(label=label,raw_probability=rawp,top_probability=top,english_probability=en,policy_pass=passed,exact_prediction_line=line)
  for d in docs:
   d['scored_lines']=sum(w['scored'] for w in d['windows']);d['skipped_chunks']=sum(not w['scored'] for w in d['windows']);d['language_pass']=all(w['policy_pass'] for w in d['windows'] if w['scored']);assert d['scored_lines']+d['skipped_chunks']==len(d['windows'])
  checkpins();terminal('result.json',{'status':'COMPLETE_EXACT_THREE_DERIVATIVE_STRICT_LANGUAGE_NO_ADMISSION','documents':docs,'scored_lines':len(lines),'passes':sum(d['language_pass'] for d in docs),'failures':sum(not d['language_pass'] for d in docs),'profile_SHA256':H(P/'profile.json'),'input_SHA256':H(OUT/'detector.input'),'predictions_SHA256':H(OUT/'detector.predictions'),'source_and_policy_unchanged':True,'tokenizer_or_student_model_used':False,'new_admitted_documents':0})
 except BaseException as e:terminal('result.json',{'status':'PARTIAL_NO_RETRY','error':type(e).__name__+':'+str(e),'new_admitted_documents':0});raise
 finally:signal.setitimer(signal.ITIMER_REAL,0)
def rss():
 q=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=1);rows={}
 for line in q.stdout.splitlines():
  a=line.split()
  if len(a)!=3:raise ValueError('RSS_schema')
  pid,parent,kb=map(int,a)
  if pid<=0 or parent<0 or kb<0 or pid==parent or pid in rows:raise ValueError('RSS_invalid')
  rows[pid]=(parent,kb)
 if os.getpid() not in rows or rows[os.getpid()][1]<=0:raise ValueError('RSS_root_missing')
 owned={os.getpid()}
 while True:
  nxt=owned|{pid for pid,(parent,kb) in rows.items() if parent in owned}
  if nxt==owned:break
  owned=nxt
 return sum(rows[pid][1]*1024 for pid in owned)
def main():
 if len(sys.argv)>1:return worker(float(sys.argv[1]))
 start=CLOCK();child=None;created=False;peak=0
 def stop(s,f):raise TimeoutError('external60sec_or_signal')
 old={s:signal.signal(s,stop) for s in [signal.SIGALRM,signal.SIGTERM,signal.SIGINT]};signal.setitimer(signal.ITIMER_REAL,60)
 def kill():
  if child is not None:
   if child.poll() is None:
    try:os.killpg(child.pid,signal.SIGKILL)
    except ProcessLookupError:pass
   child.wait(timeout=2)
 try:
  checkpins();r=rules();assert r.prediction('__label__en 0.8')[-1] and not r.prediction('__label__en 0.7999')[-1];assert len(list(r.windows('Synthetic English sentence.')))==2
  if OUT.exists():raise ValueError('existing_output_no_retry')
  OUT.mkdir();created=True
  for name,n in SLOTS.items():(OUT/name).write_bytes(b' '*n)
  with (OUT/'worker.log').open('xb') as log:child=subprocess.Popen([sys.executable,'-I','-B',str(P/'run.py'),str(start)],stdout=log,stderr=log,start_new_session=True)
  put('ownership.json',(json.dumps({'supervisor_PID':os.getpid(),'worker_PID':child.pid,'shared_start':start})+'\n').encode())
  while child.poll() is None:
   if CLOCK()-start>=55:raise TimeoutError('worker55sec')
   peak=max(peak,rss())
   if peak>1000000000 or size()>CAP:raise ValueError('RSS_or_output_limit')
   time.sleep(.025)
  child.wait(timeout=2);result=json.loads((OUT/'result.json').read_text());okay=child.returncode==0 and result['status']=='COMPLETE_EXACT_THREE_DERIVATIVE_STRICT_LANGUAGE_NO_ADMISSION';terminal('supervisor.json',{'status':'COMPLETE' if okay else 'PARTIAL_NO_RETRY','worker_exit':child.returncode,'child_reaped':True,'result_SHA256':H(OUT/'result.json'),'peak_tree_RSS_bytes':peak,'elapsed_seconds':CLOCK()-start,'output_bytes':size(),'new_admitted_documents':0})
  if not okay:raise RuntimeError('worker_terminal_failure')
  print(json.dumps({'passes':result['passes'],'failures':result['failures'],'scored_lines':result['scored_lines']}))
 except BaseException as e:
  kill()
  if created:terminal('supervisor.json',{'status':'PARTIAL_NO_RETRY','error':type(e).__name__+':'+str(e),'child_reaped':child is not None,'new_admitted_documents':0})
  raise
 finally:kill();signal.setitimer(signal.ITIMER_REAL,0)
if __name__=='__main__':main()
