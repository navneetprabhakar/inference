"""External900s/1GB observed process-tree/1GB disk supervisor, no retry."""
import argparse,json,os,pathlib,signal,subprocess,sys,time
import finalize as f
HERE=pathlib.Path(__file__).resolve().parent
SLOT=32768

def write(out,r):
 p=out/'supervisor-result.json';b=(json.dumps(r,sort_keys=True,indent=2)+'\n').encode()
 if len(b)>SLOT:raise RuntimeError('supervisor_terminal_slot')
 if not p.exists():
  with p.open('xb') as x:x.write(b' '*SLOT)
 with p.open('r+b') as x:x.write(b+b' '*(SLOT-len(b)));x.flush();os.fsync(x.fileno())
def tree(snapshot,root):
 parents={};rss={}
 for line in snapshot.splitlines():
  x=line.split()
  if len(x)!=3:continue
  try:pid,ppid,kib=map(int,x)
  except ValueError:continue
  parents[pid]=ppid;rss[pid]=kib*1024
 if root not in rss:raise RuntimeError('supervisor_missing_from_process_snapshot')
 owned={root}
 while True:
  more=owned|{p for p,q in parents.items() if q in owned}
  if more==owned:break
  owned=more
 return sum(rss[p] for p in owned)
def decision(elapsed,rss,output,free):
 if elapsed>=895:return 'elapsed_time_cap_cleanup_reserve'
 if rss>1_000_000_000:return 'observed_process_tree_RSS_cap'
 if output>1_000_000_000-f.TERMINAL:return 'output_byte_cap'
 if free<f.CAPS['free_floor_bytes']+f.CAPS['weights_bytes']:return 'free_floor_weights_reserve'
 return None
def kill(p):
 if p.poll() is not None:return
 try:os.killpg(p.pid,signal.SIGTERM)
 except ProcessLookupError:pass
 try:p.wait(timeout=2)
 except subprocess.TimeoutExpired:
  try:os.killpg(p.pid,signal.SIGKILL)
  except ProcessLookupError:pass
  p.wait(timeout=3)
def run(recipe,out,code_pins_sha,recipe_sha):
 start=f.clk();import code_guard
 pins=code_guard.verify(code_pins_sha)
 if f.sha(recipe)!=recipe_sha:raise RuntimeError('parent_reviewed_recipe_digest_mismatch')
 if out.exists():raise RuntimeError('existing_output_no_retry')
 if not out.resolve().is_relative_to((f.BASE/'m2-intake').resolve()):raise RuntimeError('output_outside_intake')
 if f.size(f.BASE/'m2-intake')+f.CAPS['output_bytes']>f.CAPS['processed_bytes']:raise RuntimeError('processed_intake64GB')
 if f.shutil.disk_usage(out.parent).free<f.CAPS['free_floor_bytes']+f.CAPS['weights_bytes']+f.CAPS['output_bytes']:raise RuntimeError('preflight_disk_reservation')
 out.mkdir();write(out,{'status':'RUNNING_NOT_COMPLETE_NO_ADMISSION'});p=None;peak=0;reason=None
 def stop(signum,frame):raise RuntimeError('external_signal:'+str(signum))
 handlers={s:signal.signal(s,stop) for s in [signal.SIGTERM,signal.SIGINT]}
 try:
  with (out/'worker.log').open('xb') as log:
   p=subprocess.Popen([sys.executable,str(HERE/'finalize.py'),'--recipe',str(recipe.resolve()),'--output',str(out.resolve()),'--supervisor-pid',str(os.getpid()),'--start-shared-monotonic',str(start),'--code-pins-sha256',code_pins_sha,'--recipe-sha256',recipe_sha],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
   (out/'ownership.json').write_text(json.dumps({'supervisor_pid':os.getpid(),'worker_pid':p.pid,'start_shared_monotonic':start})+'\n')
   while p.poll() is None:
    remaining=895-(f.clk()-start)
    if remaining<=0:reason='elapsed_time_cap_cleanup_reserve';kill(p);break
    ps=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=min(1,remaining));rss=tree(ps.stdout,os.getpid());peak=max(peak,rss)
    reason=decision(f.clk()-start,rss,f.size(out),f.shutil.disk_usage(out).free)
    if reason is None and f.size(f.BASE/'m2-intake')>f.CAPS['processed_bytes']:reason='processed_intake64GB'
    if reason:kill(p);break
    time.sleep(min(.5,max(0,895-(f.clk()-start))))
   p.wait(timeout=3)
  result=json.loads((out/'result.json').read_text()) if (out/'result.json').exists() else {}
  complete=p.returncode==0 and reason is None and result.get('status')=='COMPLETE_GLOBAL_STRUCTURAL_RECONCILIATION_PROVISIONAL_NO_ADMISSION' and f.clk()-start<=900
  if complete and f.sha(out/'finalized.sqlite3')!=result['output_sha256']:complete=False;reason='output_hash_mismatch'
  if f.clk()-start>900:complete=False;reason=reason or 'terminal_wall_over900'
  write(out,{'status':'COMPLETE_GLOBAL_FINALIZER_NO_ADMISSION' if complete else 'PARTIAL_GLOBAL_FINALIZER_NO_ADMISSION','reason':reason,'worker_exit_code':p.returncode,'peak_observed_process_tree_RSS_bytes':peak,'elapsed_seconds':f.clk()-start,'worker_receipt_sha256':f.sha(out/'result.json') if (out/'result.json').exists() else None,'limits':f.CAPS,'new_admitted_documents':0,'new_admitted_tokens':0});return 0 if complete else 1
 except BaseException as exc:
  if p is not None:kill(p)
  write(out,{'status':'PARTIAL_GLOBAL_FINALIZER_NO_ADMISSION','reason':str(exc)[:2000],'elapsed_seconds':f.clk()-start,'peak_observed_process_tree_RSS_bytes':peak,'new_admitted_documents':0,'new_admitted_tokens':0});raise
 finally:
  for s,h in handlers.items():signal.signal(s,h)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--recipe',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--code-pins-sha256',required=True);p.add_argument('--recipe-sha256',required=True);a=p.parse_args();raise SystemExit(run(a.recipe,a.output,a.code_pins_sha256,a.recipe_sha256))
