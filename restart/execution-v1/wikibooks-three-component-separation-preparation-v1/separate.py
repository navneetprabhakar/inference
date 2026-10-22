"""Exact three-source component partition; no generic extraction or admission."""
import argparse, hashlib, json, os, pathlib, platform, shutil, signal, subprocess, sys, time

HERE=pathlib.Path(__file__).resolve().parent
ORDINALS=[61485,40765,72377]
LIMITS={'worker_seconds':55,'external_seconds':60,'output_bytes':5000000,'tree_RSS_bytes':1000000000,'source_bytes':100000}
SLOTS={'result.json':32768,'supervisor.json':32768}
def sha(p):
 h=hashlib.sha256()
 with pathlib.Path(p).open('rb') as f:
  for b in iter(lambda:f.read(65536),b''):h.update(b)
 return h.hexdigest()
def digest(b):return hashlib.sha256(b).hexdigest()
def runtime():return {'python':sys.version,'executable':str(pathlib.Path(sys.executable).resolve()),'platform':platform.platform()}
def partition(raw, start, end):
 """Pure bytes operation; gaps and every original byte remain recoverable."""
 if type(start)is not int or type(end)is not int or not 0<=start<end<=len(raw):raise ValueError('range')
 text=raw.decode('utf8');raw[:start].decode('utf8');raw[start:end].decode('utf8');raw[end:].decode('utf8')
 main=raw[start:end]
 spans=[]
 for a,b,role in [(0,start,'presentation'),(start,end,'main'),(end,len(raw),'presentation')]:
  if a==b:continue
  spans.append({'source_UTF8_range':[a,b],'role':role,'SHA256':digest(raw[a:b]),'text':raw[a:b].decode('utf8') if role=='presentation' else None,'derivative_UTF8_range':[0,len(main)] if role=='main' else None})
 if inverse(main,spans)!=raw:raise ValueError('inverse')
 return main,spans
def inverse(main,spans):
 chunks=[];cursor=0
 for s in spans:
  a,b=s['source_UTF8_range']
  if a!=cursor or b<=a:raise ValueError('nonpartition')
  if s['role']=='main':
   lo,hi=s['derivative_UTF8_range'];chunk=main[lo:hi]
   if lo!=0 or hi!=len(main):raise ValueError('main_range')
  elif s['role']=='presentation':chunk=s['text'].encode('utf8')
  else:raise ValueError('unknown_role')
  if len(chunk)!=b-a or digest(chunk)!=s['SHA256']:raise ValueError('span_hash')
  chunks.append(chunk);cursor=b
 return b''.join(chunks)
def verify(args):
 pins=HERE/'code-pins.json'
 if sha(pins)!=args.code_pins_sha256:raise ValueError('external_codepins_digest')
 obj=json.loads(pins.read_text());profile=json.loads((HERE/'profile.json').read_text())
 expected={str((HERE/x).resolve()) for x in ['separate.py','checks.py','profile.json','runtime.json']}
 expected|={profile['clarification']['path'],profile['original_review']['path']}
 for r in profile['sources']:expected|={r['path'],r['receipt_path']}
 expected.add(str(pathlib.Path(sys.executable).resolve()))
 for m in [argparse,hashlib,json,os,pathlib,platform,shutil,signal,subprocess,time]:
  if getattr(m,'__file__',None):expected.add(str(pathlib.Path(m.__file__).resolve()))
 if set(obj['input_code_SHA256'])!=expected:raise ValueError('exact_pin_inventory')
 for p,h in obj['input_code_SHA256'].items():
  if sha(p)!=h:raise ValueError('input_hash:'+p)
 if sha(HERE/'profile.json')!=args.profile_sha256 or profile['limits']!=LIMITS or json.loads((HERE/'runtime.json').read_text())!=runtime():raise ValueError('profile_runtime')
 if [r['source_ordinal'] for r in profile['sources']]!=ORDINALS:raise ValueError('exact_three')
 return profile
def outsize(out):return sum(p.stat().st_size for p in out.rglob('*') if p.is_file())
def write(out,name,raw):
 if outsize(out)+len(raw)>LIMITS['output_bytes']-65536:raise ValueError('prewrite_output_cap')
 with (out/name).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
def data(obj):return (json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode()
def slot(out,name,obj):
 raw=data(obj);n=SLOTS[name]
 if len(raw)>n:raise ValueError('terminal_slot')
 with (out/name).open('r+b') as f:f.write(raw+b' '*(n-len(raw)));f.flush();os.fsync(f.fileno())
def arm(seconds):
 def stop(s,f):raise TimeoutError('deadline_or_signal')
 for s in [signal.SIGALRM,signal.SIGTERM,signal.SIGINT]:signal.signal(s,stop)
 if seconds<=0:raise TimeoutError('already_expired')
 signal.setitimer(signal.ITIMER_REAL,seconds)
def worker(args):
 arm(LIMITS['worker_seconds']-(time.monotonic()-args.start));out=pathlib.Path(args.output)
 try:
  p=verify(args)
  if str(out)!=p['output'] or os.getppid()!=args.supervisor_pid:raise ValueError('owned_output_parent')
  done=[]
  for r in p['sources']:
   src=pathlib.Path(r['path'])
   if src.stat().st_size>LIMITS['source_bytes']:raise ValueError('body_cap')
   raw=src.read_bytes();receipt=json.loads(pathlib.Path(r['receipt_path']).read_text())
   if digest(raw)!=r['SHA256'] or receipt['body_SHA256']!=r['SHA256'] or receipt['source_ordinal']!=r['source_ordinal'] or receipt['selection']!=r['selection']:raise ValueError('source_identity')
   main,spans=partition(raw,*r['main_UTF8_range'])
   for s in spans:
    a,b=s['source_UTF8_range'];s['source_Unicode_range']=[len(raw[:a].decode()),len(raw[:b].decode())]
   side={'source_ordinal':r['source_ordinal'],'selection':r['selection'],'source_path':r['path'],'source_SHA256':r['SHA256'],'source_receipt_SHA256':r['receipt_SHA256'],'partition':spans,'derivative_SHA256':digest(main),'derivative_bytes':len(main),'reconstruction_SHA256':digest(inverse(main,spans)),'all_original_holds_preserved':True,'source_receipt':receipt,'separate_review':r['review'],'new_admitted_documents':0,'not_acceptance':True}
   prefix=str(r['source_ordinal']);write(out,prefix+'.main.txt',main);write(out,prefix+'.components.json',data(side));done.append({'source_ordinal':r['source_ordinal'],'derivative_SHA256':digest(main),'main_bytes':len(main),'sidecar_SHA256':sha(out/(prefix+'.components.json'))})
  verify(args)
  slot(out,'result.json',{'status':'COMPLETE_DIAGNOSTIC_COMPONENT_SEPARATION','sources':done,'source_inputs_after_unchanged':True,'new_admitted_documents':0,'no_tokenization_network_training':True})
 except BaseException as e:
  slot(out,'result.json',{'status':'PARTIAL_NO_RETRY','error':type(e).__name__+':'+str(e),'new_admitted_documents':0});raise
 finally:signal.setitimer(signal.ITIMER_REAL,0)
def tree_rss(pid):
 v=subprocess.run(['ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=2).stdout
 rows={}
 for line in v.splitlines():
  f=line.split()
  if len(f)!=3:raise ValueError('RSS_malformed')
  i,parent,rss=map(int,f)
  if i in rows or i<=0 or parent<0 or rss<0 or i==parent:raise ValueError('RSS_invalid')
  rows[i]=(parent,rss)
 if pid not in rows or rows[pid][1]<=0:raise ValueError('RSS_root_missing')
 found={pid}
 while True:
  more={i for i,(parent,rss) in rows.items() if parent in found}
  if more<=found:break
  found|=more
 return sum(rows[i][1]*1024 for i in found)
def supervise(out,command,preflight=None,started=None):
 start=time.monotonic() if started is None else started;child=None;peak=0;arm(LIMITS['external_seconds']-(time.monotonic()-start))
 try:
  if preflight:preflight()
  out.mkdir(exist_ok=False)
  for name,n in SLOTS.items():(out/name).write_bytes(b' '*n)
  if shutil.disk_usage(out).free<53474836480+LIMITS['output_bytes']:raise ValueError('weights_scratch_freefloor')
  cmd=command(start)
  with (out/'worker.log').open('xb') as log:
   child=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
   while child.poll()is None:
    try:peak=max(peak,tree_rss(child.pid))
    except BaseException:
     if child.poll()is None:raise
    if peak>LIMITS['tree_RSS_bytes'] or outsize(out)>LIMITS['output_bytes']:raise ValueError('resource_bound')
    time.sleep(.05)
   rc=child.wait()
  result=json.loads((out/'result.json').read_text())
  if rc or not result['status'].startswith('COMPLETE'):raise ValueError('worker_not_complete')
  slot(out,'supervisor.json',{'status':'COMPLETE','child_reaped':True,'child_pid':child.pid,'returncode':rc,'peak_tree_RSS_bytes':peak,'elapsed_seconds':time.monotonic()-start,'output_bytes':outsize(out)})
 except BaseException as e:
  if child is not None and child.poll()is None:
   os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=3)
  if (out/'supervisor.json').exists():slot(out,'supervisor.json',{'status':'PARTIAL_NO_RETRY','child_reaped':child is None or child.poll()is not None,'error':type(e).__name__+':'+str(e)})
  raise
 finally:signal.setitimer(signal.ITIMER_REAL,0)
def main():
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--worker',action='store_true');p.add_argument('--code-pins-sha256',required=True);p.add_argument('--profile-sha256',required=True);p.add_argument('--start',type=float);p.add_argument('--supervisor-pid',type=int);p.add_argument('--output');a=p.parse_args()
 if a.worker:worker(a)
 elif a.execute:
  start=time.monotonic();arm(LIMITS['external_seconds'])
  out=pathlib.Path(json.loads((HERE/'profile.json').read_text())['output'])
  supervise(out,lambda start:[sys.executable,'-I','-B',str(HERE/'separate.py'),'--worker','--code-pins-sha256',a.code_pins_sha256,'--profile-sha256',a.profile_sha256,'--start',str(start),'--supervisor-pid',str(os.getpid()),'--output',str(out)],lambda:verify(a),started=start)
 else:arm(55);verify(a);signal.setitimer(signal.ITIMER_REAL,0);print('READY_NO_DERIVATION')
if __name__=='__main__':main()
